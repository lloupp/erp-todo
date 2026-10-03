"""Microsoft Forms + Outlook integration for the SGE.

Forms enters through a normalized webhook (typically Power Automate:
"When a new response is submitted" -> "Get response details" -> HTTP POST).
Outlook uses Microsoft Graph with application credentials. Every outbound
message requires an explicit user action in the SGE and is audited.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime
from urllib import error, parse, request as urlrequest

from flask import jsonify, request
from flask_login import current_user, login_required


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _graph_config() -> dict:
    return {
        "enabled": _env_bool("OUTLOOK_GRAPH_ENABLED"),
        "tenant_id": os.environ.get("MICROSOFT_TENANT_ID", "").strip(),
        "client_id": os.environ.get("MICROSOFT_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("MICROSOFT_CLIENT_SECRET", "").strip(),
        "sender": os.environ.get("OUTLOOK_SENDER", "").strip(),
        "authority_host": os.environ.get(
            "MICROSOFT_AUTHORITY_HOST", "https://login.microsoftonline.com"
        ).rstrip("/"),
        "graph_base": os.environ.get(
            "MICROSOFT_GRAPH_BASE", "https://graph.microsoft.com/v1.0"
        ).rstrip("/"),
    }


def _forms_config() -> dict:
    return {
        "enabled": _env_bool("FORMS_WEBHOOK_ENABLED"),
        "secret": os.environ.get("FORMS_WEBHOOK_SECRET", "").strip(),
    }


def _fetch_graph_token(config: dict) -> str:
    token_url = (
        f"{config['authority_host']}/{parse.quote(config['tenant_id'], safe='')}"
        "/oauth2/v2.0/token"
    )
    body = parse.urlencode(
        {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")
    req = urlrequest.Request(
        token_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlrequest.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(f"Falha ao autenticar no Microsoft Graph (HTTP {exc.code}).") from exc
    except error.URLError as exc:
        raise RuntimeError("Falha de rede ao autenticar no Microsoft Graph.") from exc

    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Microsoft Graph nao retornou access_token.")
    return token


def _send_graph_mail(config: dict, *, to: str, subject: str, body: str) -> None:
    token = _fetch_graph_token(config)
    sender = parse.quote(config["sender"], safe="@._-")
    endpoint = f"{config['graph_base']}/users/{sender}/sendMail"
    payload = _safe_json_dumps(
        {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": True,
        }
    ).encode("utf-8")
    req = urlrequest.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=20) as response:
            if response.status not in {200, 202}:
                raise RuntimeError(f"Microsoft Graph retornou HTTP {response.status}.")
    except error.HTTPError as exc:
        raise RuntimeError(f"Falha ao enviar e-mail pelo Outlook (HTTP {exc.code}).") from exc
    except error.URLError as exc:
        raise RuntimeError("Falha de rede ao enviar e-mail pelo Outlook.") from exc


def _normalize_month(value: str | None, inicio: str | None) -> str | None:
    value = (value or "").strip()
    if len(value) >= 7 and value[4] == "-":
        return value[:7]

    if inicio:
        inicio = str(inicio).strip()
        if len(inicio) >= 7 and inicio[4] == "-":
            return inicio[:7]

    lower = value.lower()
    months = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
        "outubro": 10, "novembro": 11, "dezembro": 12,
    }
    for name, month in months.items():
        if name in lower:
            digits = "".join(ch if ch.isdigit() else " " for ch in lower).split()
            years = [int(x) for x in digits if len(x) == 4]
            if years:
                return f"{years[-1]:04d}-{month:02d}"
    return None


def _forms_signature_ok(secret: str, raw_body: bytes, supplied: str) -> bool:
    if not secret or not supplied:
        return False
    # Supports either the plain shared secret or an HMAC-SHA256 signature.
    if hmac.compare_digest(secret.encode("utf-8"), supplied.encode("utf-8")):
        return True
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    candidate = supplied.removeprefix("sha256=").strip()
    return hmac.compare_digest(expected.encode("ascii"), candidate.encode("utf-8"))


def register_microsoft_integrations(app, get_db, criar_acao_pipeline):
    if getattr(app, "_microsoft_integrations_registered", False):
        return
    app._microsoft_integrations_registered = True

    def audit(
        db,
        *,
        provider,
        event_type,
        direction,
        status,
        residente_id=None,
        external_id=None,
        payload=None,
        error_message=None,
        actor=None,
    ):
        db.execute(
            """INSERT INTO integracao_eventos
               (provider, event_type, direction, status, residente_id, external_id,
                payload_json, erro, responsavel)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                provider,
                event_type,
                direction,
                status,
                residente_id,
                external_id,
                _safe_json_dumps(payload) if payload is not None else None,
                error_message,
                actor,
            ),
        )

    @app.route("/api/integracoes/status", methods=["GET"])
    @login_required
    def api_integracoes_status():
        forms = _forms_config()
        outlook = _graph_config()
        return jsonify(
            {
                "microsoft_forms": {
                    "enabled": forms["enabled"],
                    "configured": bool(forms["secret"]),
                    "endpoint": "/api/integracoes/forms/inscricao",
                },
                "outlook": {
                    "enabled": outlook["enabled"],
                    "configured": all(
                        outlook[k]
                        for k in ("tenant_id", "client_id", "client_secret", "sender")
                    ),
                    "sender": outlook["sender"] or None,
                },
            }
        )

    @app.route("/api/integracoes/forms/inscricao", methods=["POST"])
    def api_forms_inscricao():
        config = _forms_config()
        if not config["enabled"]:
            return jsonify({"erro": "Integracao Microsoft Forms desabilitada."}), 503
        if not config["secret"]:
            return jsonify({"erro": "FORMS_WEBHOOK_SECRET nao configurado."}), 503

        raw = request.get_data(cache=True) or b""
        supplied = request.headers.get("X-Forms-Webhook-Secret", "")
        if not _forms_signature_ok(config["secret"], raw, supplied):
            return jsonify({"erro": "Assinatura do Microsoft Forms invalida."}), 401

        data = request.get_json(silent=True) or {}
        form_id = str(data.get("form_id") or "forms").strip()
        response_id = str(data.get("response_id") or "").strip()
        if not response_id:
            return jsonify({"erro": "response_id e obrigatorio."}), 400

        external_id = f"{form_id}:{response_id}"
        db = get_db()
        existing = db.execute(
            """SELECT id FROM residentes
               WHERE origem='microsoft_forms' AND origem_ref=?""",
            (external_id,),
        ).fetchone()
        if existing:
            return jsonify({"ok": True, "duplicado": True, "id": existing["id"]}), 200

        nome = str(data.get("nome") or "").strip()
        especialidade = str(data.get("especialidade") or "").strip()
        inicio = str(data.get("inicio") or "").strip() or None
        mes_desejado = str(data.get("mes_desejado") or "").strip() or None
        mes_ano = _normalize_month(data.get("mes_ano") or mes_desejado, inicio)
        if not nome or not especialidade or not mes_ano:
            return jsonify(
                {
                    "erro": (
                        "Campos obrigatorios do Forms: nome, especialidade e "
                        "mes_ano (ou inicio/mes_desejado reconhecivel)."
                    )
                }
            ), 400

        try:
            cur = db.execute(
                """INSERT INTO residentes
                   (nome, email, telefone, cpf, tipo, modalidade, especialidade,
                    subespecialidade, instituicao_origem, programa_ano, mes_ano,
                    inicio, termino, status, valor, forma_pagamento,
                    status_pagamento, comprovante_pagamento, observacao,
                    data_inscricao, periodo_desejado, mes_desejado,
                    origem, origem_ref)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    nome,
                    data.get("email"),
                    data.get("telefone"),
                    data.get("cpf"),
                    data.get("tipo") or "Residente",
                    data.get("modalidade") or "Optativo",
                    especialidade,
                    data.get("subespecialidade"),
                    data.get("instituicao_origem"),
                    data.get("programa_ano"),
                    mes_ano,
                    inicio,
                    data.get("termino") or None,
                    "Interessado",
                    data.get("valor") or None,
                    data.get("forma_pagamento"),
                    "Pendente",
                    None,
                    data.get("observacao"),
                    data.get("data_inscricao")
                    or datetime.now().strftime("%d/%m/%Y %H:%M"),
                    data.get("periodo_desejado"),
                    mes_desejado,
                    "microsoft_forms",
                    external_id,
                ),
            )
            rid = cur.lastrowid
            criar_acao_pipeline(db, rid, 1)
            audit(
                db,
                provider="microsoft_forms",
                event_type="new_response",
                direction="inbound",
                status="success",
                residente_id=rid,
                external_id=external_id,
                payload={
                    "form_id": form_id,
                    "response_id": response_id,
                    "fields_received": sorted(data.keys()),
                },
                actor="Microsoft Forms",
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            existing = db.execute(
                """SELECT id FROM residentes
                   WHERE origem='microsoft_forms' AND origem_ref=?""",
                (external_id,),
            ).fetchone()
            if existing:
                return jsonify({"ok": True, "duplicado": True, "id": existing["id"]}), 200
            raise
        except Exception as exc:
            db.rollback()
            app.logger.error("Falha ao importar resposta do Microsoft Forms (%s)", type(exc).__name__)
            return jsonify({"erro": "Falha ao importar resposta."}), 500

        return jsonify({"ok": True, "duplicado": False, "id": rid}), 201

    @app.route("/api/integracoes/outlook/enviar", methods=["POST"])
    @login_required
    def api_outlook_enviar():
        config = _graph_config()
        missing = [
            name
            for name, value in (
                ("MICROSOFT_TENANT_ID", config["tenant_id"]),
                ("MICROSOFT_CLIENT_ID", config["client_id"]),
                ("MICROSOFT_CLIENT_SECRET", config["client_secret"]),
                ("OUTLOOK_SENDER", config["sender"]),
            )
            if not value
        ]
        if not config["enabled"]:
            return jsonify({"erro": "Integracao Outlook desabilitada."}), 503
        if missing:
            return jsonify({"erro": "Configuracao Outlook incompleta: " + ", ".join(missing)}), 503

        data = request.get_json(silent=True) or {}
        recipient = str(data.get("destinatario") or "").strip()
        subject = str(data.get("assunto") or "").strip()
        body = str(data.get("mensagem") or "").strip()
        residente_id = data.get("residente_id")
        etapa = data.get("etapa")

        if not recipient or "@" not in recipient:
            return jsonify({"erro": "Destinatario de e-mail invalido."}), 400
        if not subject:
            return jsonify({"erro": "Assunto e obrigatorio."}), 400
        if not body:
            return jsonify({"erro": "Mensagem e obrigatoria."}), 400

        db = get_db()
        if residente_id is not None:
            try:
                residente_id = int(residente_id)
            except (TypeError, ValueError):
                return jsonify({"erro": "residente_id invalido."}), 400
            if not db.execute("SELECT id FROM residentes WHERE id=?", (residente_id,)).fetchone():
                return jsonify({"erro": "Residente nao encontrado."}), 404

        actor = current_user.nome if current_user.is_authenticated else "Sistema"
        audit_payload = {
            "to": recipient,
            "subject": subject,
            "etapa": etapa,
            "sender": config["sender"],
        }
        try:
            _send_graph_mail(config, to=recipient, subject=subject, body=body)
            audit(
                db,
                provider="outlook",
                event_type="send_mail",
                direction="outbound",
                status="success",
                residente_id=residente_id,
                payload=audit_payload,
                actor=actor,
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            try:
                audit(
                    db,
                    provider="outlook",
                    event_type="send_mail",
                    direction="outbound",
                    status="error",
                    residente_id=residente_id,
                    payload=audit_payload,
                    error_message="Falha no envio. Verifique a configuracao e o status do Microsoft 365.",
                    actor=actor,
                )
                db.commit()
            except Exception:
                db.rollback()
            app.logger.warning("Falha ao enviar Outlook (%s)", type(exc).__name__)
            return jsonify({"erro": "Falha no envio. Verifique a configuracao do Microsoft 365."}), 502

        return jsonify({"ok": True, "enviado": True, "remetente": config["sender"]})
