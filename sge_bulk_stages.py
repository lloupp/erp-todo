"""Bulk pipeline-stage reconciliation for imported/historical students."""

from __future__ import annotations

from datetime import date

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from sge_common import auditar, iniciar_escrita
from sge_student_modal import (
    EDIT_ROLES,
    TERMINAL_STATUSES,
    corrigir_etapa_pipeline,
)


def _concluir_historico(db, rid, justificativa, criar_acao_pipeline, avancar_pipeline):
    justificativa = str(justificativa or "").strip()
    if len(justificativa) < 5:
        raise ValueError("Informe uma justificativa para a reconciliacao historica.")

    iniciar_escrita(db)
    residente = db.execute("SELECT * FROM residentes WHERE id=?", (rid,)).fetchone()
    if not residente:
        raise LookupError("Aluno nao encontrado.")
    if residente["status"] == "Concluído":
        db.rollback()
        return {"ok": True, "ignorado": True, "motivo": "Ja estava concluido."}
    if residente["status"] in TERMINAL_STATUSES:
        raise ValueError(f'Processo encerrado como "{residente["status"]}".')

    termino = residente["termino"]
    if not termino:
        raise ValueError("Data de termino obrigatoria para reconciliar como concluido.")
    try:
        termino_data = date.fromisoformat(str(termino)[:10])
    except ValueError as exc:
        raise ValueError("Data de termino invalida.") from exc
    if termino_data > date.today():
        raise ValueError("Nao e possivel concluir historicamente um estagio com termino futuro.")

    atual = db.execute(
        """SELECT * FROM pipeline_acoes
           WHERE residente_id=? AND situacao='pendente'
           ORDER BY id DESC LIMIT 1""",
        (rid,),
    ).fetchone()

    etapa_anterior = atual["etapa"] if atual else None
    if atual and atual["etapa"] != 9:
        db.execute(
            """UPDATE pipeline_acoes
               SET situacao='pulado', responsavel=?, observacao=?,
                   concluido_em=CURRENT_TIMESTAMP, atualizado_em=CURRENT_TIMESTAMP
               WHERE id=? AND situacao='pendente'""",
            (
                current_user.nome,
                f"[Reconciliacao historica] {justificativa}",
                atual["id"],
            ),
        )
        criar_acao_pipeline(db, rid, 9)
    elif not atual:
        criar_acao_pipeline(db, rid, 9)

    # Stage 9 preserves the regular "real completion" guard and status history.
    resultado = avancar_pipeline(
        db,
        rid,
        9,
        "concluido",
        current_user.nome,
        f"[Reconciliacao historica] {justificativa}",
    )
    auditar(
        db,
        "residentes",
        rid,
        "reconciliar_conclusao_historica",
        {
            "etapa_anterior": etapa_anterior,
            "termino": str(termino)[:10],
            "justificativa": justificativa,
        },
    )
    db.commit()
    return {
        "ok": True,
        "status": "Concluído",
        "etapa_anterior": etapa_anterior,
        "resultado": resultado,
    }


def register_bulk_stages(
    app,
    get_db,
    criar_acao_pipeline,
    avancar_pipeline,
    pipeline_etapas,
):
    @app.route("/sge/ajuste-etapas")
    @login_required
    def pagina_ajuste_etapas():
        return render_template("sge_ajuste_etapas.html")

    @app.route("/api/sge/ajuste-etapas/alunos", methods=["GET"])
    @login_required
    def api_ajuste_etapas_alunos():
        db = get_db()
        busca = str(request.args.get("busca") or "").strip()
        status = str(request.args.get("status") or "").strip()
        etapa = str(request.args.get("etapa") or "").strip()
        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(10, int(request.args.get("per_page", 50))))
        except ValueError:
            return jsonify({"erro": "Paginacao invalida."}), 400

        where = ["1=1"]
        params = []
        if busca:
            where.append(
                "(r.nome LIKE ? OR r.email LIKE ? OR r.cpf LIKE ? OR r.especialidade LIKE ?)"
            )
            like = f"%{busca}%"
            params.extend([like, like, like, like])
        if status:
            where.append("r.status=?")
            params.append(status)
        if etapa:
            if etapa == "sem":
                where.append("pa.etapa IS NULL")
            else:
                try:
                    etapa_num = int(etapa)
                except ValueError:
                    return jsonify({"erro": "Etapa invalida."}), 400
                where.append("pa.etapa=?")
                params.append(etapa_num)

        sql_where = " AND ".join(where)
        total = db.execute(
            f"""SELECT COUNT(*)
                FROM residentes r
                LEFT JOIN pipeline_acoes pa
                  ON pa.residente_id=r.id AND pa.situacao='pendente'
                WHERE {sql_where}""",
            params,
        ).fetchone()[0]

        offset = (page - 1) * per_page
        rows = db.execute(
            f"""SELECT r.id,r.nome,r.email,r.tipo,r.modalidade,r.especialidade,
                       r.instituicao_origem,r.inicio,r.termino,r.status,
                       r.mes_ano,r.data_inscricao,
                       pa.id as acao_id,pa.etapa,pa.acao_tipo,pa.prazo_em,
                       pa.bloqueado,pa.bloqueio_motivo
                FROM residentes r
                LEFT JOIN pipeline_acoes pa
                  ON pa.residente_id=r.id AND pa.situacao='pendente'
                WHERE {sql_where}
                ORDER BY
                    CASE WHEN r.status='Concluído' THEN 1 ELSE 0 END,
                    r.nome COLLATE NOCASE
                LIMIT ? OFFSET ?""",
            [*params, per_page, offset],
        ).fetchall()

        data = []
        for row in rows:
            item = dict(row)
            if item["etapa"]:
                item["etapa_nome"] = pipeline_etapas.get(item["etapa"], item["acao_tipo"])
            else:
                item["etapa_nome"] = None
            data.append(item)
        return jsonify({
            "data": data,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, (total + per_page - 1) // per_page),
            "pode_editar": current_user.role in EDIT_ROLES,
        })

    @app.route("/api/sge/ajuste-etapas/aplicar", methods=["POST"])
    @login_required
    def api_ajuste_etapas_aplicar():
        if current_user.role not in EDIT_ROLES:
            return jsonify({"erro": "Somente coordenacao ou administrador pode fazer ajuste em lote."}), 403

        d = request.get_json(silent=True) or {}
        ids = d.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return jsonify({"erro": "Selecione pelo menos um aluno."}), 400
        if len(ids) > 200:
            return jsonify({"erro": "Selecione no maximo 200 alunos por operacao."}), 400

        try:
            ids = list(dict.fromkeys(int(value) for value in ids))
        except (TypeError, ValueError):
            return jsonify({"erro": "Lista de alunos invalida."}), 400

        justificativa = str(d.get("justificativa") or "").strip()
        if len(justificativa) < 5:
            return jsonify({"erro": "Informe uma justificativa para o ajuste em lote."}), 400

        destino = str(d.get("destino") or "").strip()
        etapa_fixa = None
        if destino == "etapa":
            try:
                etapa_fixa = int(d.get("etapa"))
            except (TypeError, ValueError):
                return jsonify({"erro": "Etapa de destino invalida."}), 400
            if etapa_fixa not in pipeline_etapas:
                return jsonify({"erro": "Etapa de destino invalida."}), 400
        elif destino not in {"proxima", "concluido"}:
            return jsonify({"erro": "Destino invalido."}), 400

        resultados = []
        sucessos = 0
        falhas = 0
        ignorados = 0

        for rid in ids:
            db = get_db()
            try:
                residente = db.execute(
                    "SELECT id,nome,status FROM residentes WHERE id=?",
                    (rid,),
                ).fetchone()
                if not residente:
                    raise LookupError("Aluno nao encontrado.")

                if destino == "concluido":
                    result = _concluir_historico(
                        db,
                        rid,
                        justificativa,
                        criar_acao_pipeline,
                        avancar_pipeline,
                    )
                else:
                    if destino == "proxima":
                        atual = db.execute(
                            """SELECT etapa FROM pipeline_acoes
                               WHERE residente_id=? AND situacao='pendente'
                               ORDER BY id DESC LIMIT 1""",
                            (rid,),
                        ).fetchone()
                        if not atual:
                            raise ValueError("Aluno sem etapa pendente; escolha uma etapa de destino.")
                        etapa_destino = int(atual["etapa"]) + 1
                        if etapa_destino not in pipeline_etapas:
                            raise ValueError("Aluno ja esta na ultima etapa do pipeline.")
                    else:
                        etapa_destino = etapa_fixa

                    result = corrigir_etapa_pipeline(
                        db,
                        rid,
                        etapa_destino,
                        justificativa,
                        criar_acao_pipeline,
                        pipeline_etapas,
                        override_capacidade=d.get("override_capacidade") is True,
                        motivo_capacidade=d.get("motivo_capacidade"),
                    )

                if result.get("ignorado"):
                    ignorados += 1
                    resultados.append({
                        "id": rid,
                        "nome": residente["nome"],
                        "ok": True,
                        "ignorado": True,
                        "mensagem": result.get("motivo"),
                    })
                else:
                    sucessos += 1
                    resultados.append({
                        "id": rid,
                        "nome": residente["nome"],
                        "ok": True,
                        "status": result.get("status"),
                        "etapa": result.get("etapa"),
                    })
            except (LookupError, ValueError) as exc:
                try:
                    db.rollback()
                except Exception:
                    pass
                falhas += 1
                resultados.append({
                    "id": rid,
                    "nome": residente["nome"] if "residente" in locals() and residente else f"ID {rid}",
                    "ok": False,
                    "erro": str(exc),
                })
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                raise

        return jsonify({
            "ok": falhas == 0,
            "selecionados": len(ids),
            "sucessos": sucessos,
            "ignorados": ignorados,
            "falhas": falhas,
            "resultados": resultados,
        })
