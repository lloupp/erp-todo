"""Shared validation and audit helpers for incremental SGE modules."""
import json
import math
import unicodedata
from datetime import date
from flask_login import current_user


def normalizar(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').strip().casefold())
                   if not unicodedata.combining(c))


def data_iso(value, campo):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{campo}: informe uma data valida (AAAA-MM-DD).') from exc


def numero(value, campo, maximo=None):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{campo}: valor numerico obrigatorio.') from exc
    if not math.isfinite(number) or number < 0 or (maximo is not None and number > maximo):
        raise ValueError(f'{campo}: valor fora do intervalo permitido.')
    return number


def auditar(db, entidade, entidade_id, acao, detalhes=None):
    db.execute('INSERT INTO sge_auditoria(entidade,entidade_id,acao,responsavel,detalhes) VALUES (?,?,?,?,?)',
               (entidade, entidade_id, acao, current_user.nome,
                json.dumps(detalhes, ensure_ascii=False) if detalhes is not None else None))


def iniciar_escrita(db):
    if not db.in_transaction:
        db.execute('BEGIN IMMEDIATE')
