"""Student detail modal and audited pipeline-stage correction.

This module restores a single operational view per student on the Residents
list. Stage correction is explicit, justified and audited; it never bypasses
capacity checks when a correction moves a student into a confirmed stage.
"""

from __future__ import annotations

from flask import jsonify, request
from flask_login import current_user, login_required

from sge_common import auditar, iniciar_escrita
from sge_vagas import OCUPANTES, validar_vaga


EDIT_ROLES = {"admin", "user", "atendimento", "coordenacao"}
TERMINAL_STATUSES = {"Concluído", "Indeferido", "Desistente", "Cancelado", "Nao veio"}
STAGE_STATUS = {
    1: "Interessado",
    2: "Interessado",
    3: "Em andamento",
    4: "Em andamento",
    5: "Deferido",
    6: "Deferido",
    7: "Deferido",
    8: "Confirmado",
    9: "Confirmado",
}


def register_student_modal(app, get_db, criar_acao_pipeline, pipeline_etapas):
    @app.route("/api/residentes/<int:rid>/resumo", methods=["GET"])
    @login_required
    def api_residente_resumo(rid):
        db = get_db()
        residente = db.execute(
            """SELECT id,nome,email,telefone,cpf,tipo,modalidade,especialidade,
                      subespecialidade,instituicao_origem,programa_ano,mes_ano,
                      inicio,termino,status,status_pagamento,valor,
                      data_inscricao,periodo_desejado,mes_desejado,observacao,
                      origem,created_at,updated_at
               FROM residentes WHERE id=?""",
            (rid,),
        ).fetchone()
        if not residente:
            return jsonify({"erro": "Aluno nao encontrado"}), 404

        acao = db.execute(
            """SELECT id as acao_id, etapa, acao_tipo, situacao, prioridade,
                      prazo_em, bloqueado, bloqueio_motivo, atribuido_a,
                      criado_em, atualizado_em
               FROM pipeline_acoes
               WHERE residente_id=? AND situacao='pendente'
               ORDER BY id DESC LIMIT 1""",
            (rid,),
        ).fetchone()

        historico = db.execute(
            """SELECT etapa,situacao,observacao,responsavel,
                      COALESCE(concluido_em,criado_em) as ts
               FROM pipeline_acoes
               WHERE residente_id=? AND situacao!='pendente'
               ORDER BY COALESCE(concluido_em,criado_em) DESC,id DESC
               LIMIT 5""",
            (rid,),
        ).fetchall()

        data = dict(residente)
        data["pipeline"] = dict(acao) if acao else None
        if data["pipeline"]:
            data["pipeline"]["etapa_nome"] = pipeline_etapas.get(
                data["pipeline"]["etapa"], data["pipeline"]["acao_tipo"]
            )
        data["pipeline_historico"] = [dict(row) for row in historico]
        data["pode_ajustar_etapa"] = (
            current_user.role in EDIT_ROLES and residente["status"] not in TERMINAL_STATUSES
        )
        data["etapas"] = [
            {"id": etapa, "nome": nome}
            for etapa, nome in sorted(pipeline_etapas.items())
        ]
        return jsonify(data)

    @app.route("/api/pipeline/residente/<int:rid>/etapa", methods=["PUT"])
    @login_required
    def api_pipeline_corrigir_etapa(rid):
        if current_user.role not in EDIT_ROLES:
            return jsonify({"erro": "Seu perfil nao pode alterar a etapa do pipeline."}), 403

        d = request.get_json(silent=True) or {}
        try:
            etapa_destino = int(d.get("etapa"))
        except (TypeError, ValueError):
            return jsonify({"erro": "Etapa invalida."}), 400

        if etapa_destino not in pipeline_etapas or etapa_destino not in STAGE_STATUS:
            return jsonify({"erro": "Etapa invalida."}), 400

        justificativa = str(d.get("justificativa") or "").strip()
        if len(justificativa) < 5:
            return jsonify({"erro": "Informe uma justificativa para alterar a etapa."}), 400

        db = get_db()
        try:
            iniciar_escrita(db)
            residente = db.execute(
                "SELECT * FROM residentes WHERE id=?",
                (rid,),
            ).fetchone()
            if not residente:
                db.rollback()
                return jsonify({"erro": "Aluno nao encontrado"}), 404

            if residente["status"] in TERMINAL_STATUSES:
                db.rollback()
                return jsonify({
                    "erro": (
                        "Este processo ja esta encerrado. Reabertura exige uma "
                        "correcao administrativa especifica."
                    )
                }), 409

            atual = db.execute(
                """SELECT * FROM pipeline_acoes
                   WHERE residente_id=? AND situacao='pendente'
                   ORDER BY id DESC LIMIT 1""",
                (rid,),
            ).fetchone()

            if atual and atual["etapa"] == etapa_destino:
                db.rollback()
                return jsonify({
                    "erro": f"O aluno ja esta na etapa {etapa_destino}."
                }), 409

            novo_status = STAGE_STATUS[etapa_destino]

            # Moving into confirmed operational stages must obey the same
            # capacity rule as the normal stage-7 transition.
            if novo_status in OCUPANTES and residente["status"] not in OCUPANTES:
                validar_vaga(
                    db,
                    dict(residente),
                    "residentes",
                    d.get("override_capacidade") is True,
                    d.get("motivo_capacidade"),
                )

            status_anterior = residente["status"]
            etapa_anterior = atual["etapa"] if atual else None
            acao_anterior = atual["id"] if atual else None

            if atual:
                db.execute(
                    """UPDATE pipeline_acoes
                       SET situacao='pulado',
                           responsavel=?,
                           observacao=?,
                           concluido_em=CURRENT_TIMESTAMP,
                           atualizado_em=CURRENT_TIMESTAMP
                       WHERE id=? AND situacao='pendente'""",
                    (
                        current_user.nome,
                        f"[Correcao de etapa] {justificativa}",
                        atual["id"],
                    ),
                )

            if novo_status != status_anterior:
                db.execute(
                    """UPDATE residentes
                       SET status=?, updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (novo_status, rid),
                )
                db.execute(
                    """INSERT INTO historico_residentes
                       (residente_id,status,observacao,responsavel)
                       VALUES (?,?,?,?)""",
                    (
                        rid,
                        novo_status,
                        (
                            f"[Correcao de etapa {etapa_anterior or '-'} -> "
                            f"{etapa_destino}] {justificativa}"
                        ),
                        current_user.nome,
                    ),
                )

            criar_acao_pipeline(db, rid, etapa_destino)
            nova = db.execute(
                """SELECT id as acao_id,etapa,acao_tipo,prazo_em,prioridade,
                          bloqueado,bloqueio_motivo,atribuido_a,criado_em
                   FROM pipeline_acoes
                   WHERE residente_id=? AND situacao='pendente'
                   ORDER BY id DESC LIMIT 1""",
                (rid,),
            ).fetchone()

            auditar(
                db,
                "pipeline_acoes",
                nova["acao_id"],
                "corrigir_etapa",
                {
                    "residente_id": rid,
                    "acao_anterior": acao_anterior,
                    "etapa_anterior": etapa_anterior,
                    "etapa_destino": etapa_destino,
                    "status_anterior": status_anterior,
                    "status_novo": novo_status,
                    "justificativa": justificativa,
                },
            )
            db.commit()
            return jsonify({
                "ok": True,
                "status": novo_status,
                "etapa_anterior": etapa_anterior,
                "etapa": etapa_destino,
                "acao": dict(nova),
            })
        except ValueError as exc:
            db.rollback()
            return jsonify({"erro": str(exc)}), 409
        except Exception:
            db.rollback()
            raise
