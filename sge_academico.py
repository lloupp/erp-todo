"""Academic tracking for Residents & Doutorandos.

Keeps operational/pipeline state separate from academic completion state.
Certificate eligibility is derived from objective persisted requirements.
"""

from __future__ import annotations

import math
from datetime import date
from sge_frequencia import horas_realizadas

from flask import jsonify, request
from flask_login import current_user, login_required

DOCUMENT_STATUSES = {"Pendente", "Recebido", "Aprovado", "Rejeitado"}
PAYMENT_OK = {"Pago", "Isento"}


def _number(value, field):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} deve ser numerico") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} nao pode ser negativo")
    return number


def avaliar_certificado(residente, documentos):
    """Return an auditable certificate decision without mutating data."""
    motivos = []

    if residente["status"] != "Concluído":
        motivos.append("Estagio ainda nao esta concluido.")

    if residente["status_pagamento"] not in PAYMENT_OK:
        motivos.append("Pagamento ainda nao esta confirmado ou isento.")

    try:
        if date.fromisoformat(str(residente["termino"])) > date.today():
            raise ValueError()
    except (ValueError, TypeError):
        motivos.append("Termino real do estagio nao informado ou ainda futuro.")

    prevista = float(residente["carga_horaria_prevista"] or 0)
    realizada = float(residente["carga_horaria_realizada"] or 0)
    if not math.isfinite(prevista) or not math.isfinite(realizada):
        motivos.append("Carga horaria invalida.")
    if prevista <= 0:
        motivos.append("Carga horaria prevista nao informada.")
    elif realizada < prevista:
        motivos.append(f"Carga horaria insuficiente: {realizada:g}h de {prevista:g}h.")

    obrigatorios = [d for d in documentos if bool(d["obrigatorio"])]
    if not obrigatorios:
        motivos.append("Checklist de documentos obrigatorios nao configurado.")
    else:
        pendentes = [d["nome"] for d in obrigatorios if d["status"] != "Aprovado"]
        if pendentes:
            motivos.append("Documentos obrigatorios pendentes: " + ", ".join(pendentes) + ".")

    progresso = 0
    if prevista > 0:
        progresso = min(100, round((realizada / prevista) * 100, 1))

    return {
        "apto": not motivos,
        "motivos": motivos,
        "carga_horaria_prevista": prevista,
        "carga_horaria_realizada": realizada,
        "progresso_horas": progresso,
        "documentos_obrigatorios": len(obrigatorios),
        "documentos_obrigatorios_aprovados": sum(
            1 for d in obrigatorios if d["status"] == "Aprovado"
        ),
        "certificado_emitido_em": residente["certificado_emitido_em"],
        "certificado_enviado_em": residente["certificado_enviado_em"],
    }


def register_sge_academico(app, get_db):
    if getattr(app, "_sge_academico_registered", False):
        return
    app._sge_academico_registered = True

    def _residente_e_documentos(rid):
        db = get_db()
        residente = db.execute("SELECT * FROM residentes WHERE id=?", (rid,)).fetchone()
        if not residente:
            return None, []
        documentos = db.execute(
            """SELECT id, residente_id, nome, obrigatorio, status, observacao,
                      atualizado_por, updated_at
               FROM residente_documentos
               WHERE residente_id=?
               ORDER BY obrigatorio DESC, nome COLLATE NOCASE""",
            (rid,),
        ).fetchall()
        residente = dict(residente)
        residente['carga_horaria_realizada'] = horas_realizadas(db,rid)
        return residente, documentos

    @app.route("/api/residentes/<int:rid>/academico", methods=["GET"])
    @login_required
    def api_residente_academico(rid):
        residente, documentos = _residente_e_documentos(rid)
        if not residente:
            return jsonify({"erro": "Nao encontrado"}), 404
        return jsonify({
            "residente": {
                "id": residente["id"],
                "nome": residente["nome"],
                "status": residente["status"],
                "status_pagamento": residente["status_pagamento"],
                "carga_horaria_prevista": residente["carga_horaria_prevista"],
                "carga_horaria_realizada": residente["carga_horaria_realizada"],
            },
            "documentos": [dict(d) for d in documentos],
            "certificado": avaliar_certificado(residente, documentos),
        })

    @app.route("/api/residentes/<int:rid>/academico", methods=["PUT"])
    @login_required
    def api_update_residente_academico(rid):
        db = get_db()
        residente = db.execute("SELECT id FROM residentes WHERE id=?", (rid,)).fetchone()
        if not residente:
            return jsonify({"erro": "Nao encontrado"}), 404

        data = request.get_json() or {}
        try:
            prevista = _number(data.get("carga_horaria_prevista"), "carga_horaria_prevista")
            realizada = _number(data.get("carga_horaria_realizada"), "carga_horaria_realizada")
        except ValueError as exc:
            return jsonify({"erro": str(exc)}), 400

        if "carga_horaria_realizada" in data and realizada != horas_realizadas(db,rid):
            return jsonify({"erro": "Horas realizadas sao calculadas pela frequencia diaria."}),409
        db.execute(
            """UPDATE residentes
               SET carga_horaria_prevista=?,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (prevista, rid),
        )
        db.commit()
        residente, documentos = _residente_e_documentos(rid)
        return jsonify({
            "ok": True,
            "certificado": avaliar_certificado(residente, documentos),
        })

    @app.route("/api/residentes/<int:rid>/documentos", methods=["POST"])
    @login_required
    def api_upsert_residente_documento(rid):
        db = get_db()
        if not db.execute("SELECT id FROM residentes WHERE id=?", (rid,)).fetchone():
            return jsonify({"erro": "Nao encontrado"}), 404

        data = request.get_json() or {}
        nome = str(data.get("nome") or "").strip()
        status = str(data.get("status") or "Pendente").strip()
        obrigatorio = 1 if data.get("obrigatorio", True) else 0
        observacao = str(data.get("observacao") or "").strip() or None
        atualizado_por = current_user.nome if current_user.is_authenticated else "Sistema"

        if not nome:
            return jsonify({"erro": "Nome do documento e obrigatorio"}), 400
        if status not in DOCUMENT_STATUSES:
            return jsonify({"erro": "Status de documento invalido"}), 400

        doc_id = data.get("id")
        if doc_id:
            cur = db.execute(
                """UPDATE residente_documentos
                   SET nome=?, obrigatorio=?, status=?, observacao=?,
                       atualizado_por=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND residente_id=?""",
                (nome, obrigatorio, status, observacao, atualizado_por, doc_id, rid),
            )
            if cur.rowcount == 0:
                return jsonify({"erro": "Documento nao encontrado"}), 404
        else:
            try:
                cur = db.execute(
                    """INSERT INTO residente_documentos
                       (residente_id, nome, obrigatorio, status, observacao, atualizado_por)
                       VALUES (?,?,?,?,?,?)""",
                    (rid, nome, obrigatorio, status, observacao, atualizado_por),
                )
                doc_id = cur.lastrowid
            except Exception as exc:
                if "UNIQUE constraint failed" in str(exc):
                    return jsonify({"erro": "Documento ja cadastrado para este aluno"}), 409
                raise
        db.commit()
        return jsonify({"id": int(doc_id), "ok": True})

    @app.route("/api/residentes/<int:rid>/documentos/<int:doc_id>", methods=["DELETE"])
    @login_required
    def api_delete_residente_documento(rid, doc_id):
        db = get_db()
        cur = db.execute(
            "DELETE FROM residente_documentos WHERE id=? AND residente_id=?",
            (doc_id, rid),
        )
        if cur.rowcount == 0:
            return jsonify({"erro": "Documento nao encontrado"}), 404
        db.commit()
        return jsonify({"ok": True})

    @app.route("/api/residentes/<int:rid>/certificado", methods=["POST"])
    @login_required
    def api_registrar_certificado_residente(rid):
        db = get_db()
        residente, documentos = _residente_e_documentos(rid)
        if not residente:
            return jsonify({"erro": "Nao encontrado"}), 404

        data = request.get_json() or {}
        acao = data.get("acao")
        avaliacao = avaliar_certificado(residente, documentos)

        if acao == "emitir":
            if not avaliacao["apto"]:
                return jsonify({"erro": "Aluno ainda nao esta apto para certificado", "certificado": avaliacao}), 409
            db.execute(
                """UPDATE residentes
                   SET certificado_emitido_em=COALESCE(certificado_emitido_em, CURRENT_TIMESTAMP),
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (rid,),
            )
        elif acao == "enviar":
            if not residente["certificado_emitido_em"]:
                return jsonify({"erro": "Registre a emissao do certificado antes do envio"}), 409
            db.execute(
                """UPDATE residentes
                   SET certificado_enviado_em=COALESCE(certificado_enviado_em, CURRENT_TIMESTAMP),
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (rid,),
            )
        else:
            return jsonify({"erro": "Acao invalida; use emitir ou enviar"}), 400

        db.commit()
        residente, documentos = _residente_e_documentos(rid)
        return jsonify({"ok": True, "certificado": avaliar_certificado(residente, documentos)})
