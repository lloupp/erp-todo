"""
Assistente IA do ERP via NVIDIA NIM (OpenAI-compatible).

Princípio de segurança:
- A IA NUNCA gera nem executa SQL. O backend pré-computa um *snapshot* read-only
  (agregações + lista enxuta de registros) e injeta como contexto.
- Política de PII: o snapshot inclui agregados, nomes e especialidades, mas
  NUNCA CPF, e-mail ou telefone.

Configuração via variaveis de ambiente (.env):
    AI_ENABLED=true
    NVIDIA_API_KEY=<chave>
    NVIDIA_MODEL=meta/llama-3.3-70b-instruct
    NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
"""

import os
import json
import urllib.request
import urllib.error


# ── Configuração ──────────────────────────────────────────────
def _enabled():
    return (
        os.environ.get('AI_ENABLED', 'false').lower() == 'true'
        and bool(os.environ.get('NVIDIA_API_KEY', '').strip())
    )


def is_enabled():
    """Recurso de IA ativo? (flag ligada + chave presente)."""
    return _enabled()


def _config():
    return {
        'api_key': os.environ.get('NVIDIA_API_KEY', '').strip(),
        'model': os.environ.get('NVIDIA_MODEL', 'meta/llama-3.3-70b-instruct').strip(),
        'base_url': os.environ.get(
            'NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1'
        ).strip().rstrip('/'),
    }


SYSTEM_PROMPT = (
    "Você é o assistente do ERP de estágios médicos da Santa Casa/UFCSPA. "
    "Ajuda a equipe administrativa a entender a situação de estágios (Observership, "
    "Obrigatório, Optativo) e de residentes/doutorandos.\n\n"
    "REGRAS IMPORTANTES:\n"
    "- Responda SEMPRE em português do Brasil, de forma clara e objetiva.\n"
    "- Baseie-se EXCLUSIVAMENTE nos dados do SNAPSHOT fornecido abaixo. "
    "Nunca invente números nem registros.\n"
    "- Se a informação pedida não estiver no snapshot, diga claramente que não "
    "tem esse dado disponível e sugira qual filtro a pessoa pode usar no sistema.\n"
    "- Os números do snapshot são a verdade; não recalcule diferente do que está lá.\n"
    "- Não exponha dados sensíveis (CPF, e-mail, telefone) — eles não estão no snapshot "
    "de propósito.\n"
    "- Seja conciso. Use listas curtas quando ajudar."
)


# ── Snapshot dos dados (sem PII) ──────────────────────────────
def montar_snapshot(db):
    """Monta um resumo estruturado dos dados, SEM CPF/e-mail/telefone.

    Reaproveita as mesmas agregações de /api/dashboard e /api/pendencias.
    Retorna um dict serializável em JSON.
    """
    def rows(sql, params=()):
        return db.execute(sql, params).fetchall()

    # ── Estágios: agregações ──
    total_estagios = db.execute('SELECT COUNT(*) FROM estagios').fetchone()[0]

    por_tipo = rows('''
        SELECT t.nome AS nome, COUNT(*) AS cnt
        FROM estagios e JOIN tipo_estagio t ON e.tipo_id = t.id
        GROUP BY e.tipo_id ORDER BY cnt DESC
    ''')
    por_etapa = rows('SELECT etapa, COUNT(*) AS cnt FROM estagios GROUP BY etapa ORDER BY etapa')
    por_especialidade = rows('''
        SELECT especialidade, COUNT(*) AS cnt
        FROM estagios GROUP BY especialidade ORDER BY cnt DESC LIMIT 20
    ''')
    por_status_pag = rows('''
        SELECT status_pagamento, COUNT(*) AS cnt, COALESCE(SUM(valor),0) AS total
        FROM estagios GROUP BY status_pagamento
    ''')
    por_mes = rows('''
        SELECT mes_ano, COUNT(*) AS cnt, COALESCE(SUM(valor),0) AS total
        FROM estagios GROUP BY mes_ano ORDER BY mes_ano DESC LIMIT 18
    ''')
    total_valor = db.execute('SELECT COALESCE(SUM(valor),0) FROM estagios').fetchone()[0]
    valor_pago = db.execute(
        "SELECT COALESCE(SUM(valor),0) FROM estagios WHERE status_pagamento='Pago'"
    ).fetchone()[0]

    # ── Pendências de estágios (Observership = tipo_id 1) ──
    pend = db.execute('''
        SELECT
            COUNT(*) FILTER (WHERE etapa < 7) AS em_andamento,
            COUNT(*) FILTER (WHERE etapa < 7 AND dias > 14) AS criticos,
            COUNT(*) FILTER (WHERE etapa < 7 AND dias > 7 AND dias <= 14) AS alertas,
            COUNT(*) FILTER (WHERE status_pagamento='Pendente' AND etapa < 7) AS pag_pendente
        FROM (
            SELECT e.etapa, e.status_pagamento,
                CAST(julianday('now') - julianday(COALESCE(
                    (SELECT MAX(h.ts) FROM historico_etapas h WHERE h.estagio_id = e.id),
                    e.updated_at, e.created_at)) AS INTEGER) AS dias
            FROM estagios e WHERE e.tipo_id = 1
        )
    ''').fetchone()

    # ── Residentes & doutorandos: agregações ──
    total_res = db.execute('SELECT COUNT(*) FROM residentes').fetchone()[0]
    res_por_status = rows('''
        SELECT status, COUNT(*) AS cnt FROM residentes GROUP BY status ORDER BY cnt DESC
    ''')
    res_por_tipo = rows('''
        SELECT COALESCE(tipo,'(não informado)') AS tipo, COUNT(*) AS cnt
        FROM residentes GROUP BY tipo ORDER BY cnt DESC
    ''')
    res_por_esp = rows('''
        SELECT COALESCE(especialidade,'(não informado)') AS especialidade, COUNT(*) AS cnt
        FROM residentes GROUP BY especialidade ORDER BY cnt DESC LIMIT 20
    ''')
    res_pend = db.execute('''
        SELECT
            COUNT(*) FILTER (WHERE status='Interessado') AS novos,
            COUNT(*) FILTER (WHERE status='Em andamento') AS em_andamento,
            COUNT(*) FILTER (WHERE status='Deferido') AS deferidos,
            COUNT(*) FILTER (WHERE status='Confirmado') AS confirmados,
            COUNT(*) FILTER (WHERE status_pagamento='Pendente'
                AND status NOT IN ('Cancelado','Indeferido','Desistente','Nao veio')) AS pag_pendente
        FROM residentes
    ''').fetchone()

    # ── Registros recentes (SEM PII: nome + tipo + especialidade + status/mes) ──
    estagios_recentes = rows('''
        SELECT e.nome, t.nome AS tipo, e.especialidade, e.etapa, e.mes_ano, e.status_pagamento
        FROM estagios e JOIN tipo_estagio t ON e.tipo_id = t.id
        ORDER BY e.updated_at DESC LIMIT 15
    ''')
    res_recentes = rows('''
        SELECT nome, COALESCE(tipo,'') AS tipo, COALESCE(especialidade,'') AS especialidade,
               status, COALESCE(mes_ano,'') AS mes_ano
        FROM residentes ORDER BY updated_at DESC LIMIT 15
    ''')

    return {
        'estagios': {
            'total': total_estagios,
            'por_tipo': [dict(r) for r in por_tipo],
            'por_etapa': [{'etapa': r['etapa'], 'cnt': r['cnt']} for r in por_etapa],
            'por_especialidade': [dict(r) for r in por_especialidade],
            'por_status_pagamento': [dict(r) for r in por_status_pag],
            'por_mes': [dict(r) for r in por_mes],
            'financeiro': {
                'total': total_valor, 'pago': valor_pago,
                'pendente': (total_valor or 0) - (valor_pago or 0),
            },
            'pendencias_observership': dict(pend) if pend else {},
            'recentes': [dict(r) for r in estagios_recentes],
        },
        'residentes': {
            'total': total_res,
            'por_status': [dict(r) for r in res_por_status],
            'por_tipo': [dict(r) for r in res_por_tipo],
            'por_especialidade': [dict(r) for r in res_por_esp],
            'pendencias': dict(res_pend) if res_pend else {},
            'recentes': [dict(r) for r in res_recentes],
        },
        'observacoes': (
            'Etapas de estágio vão de 0 a 7 (7 = concluído). '
            'Observership é o tipo_id 1. As pendencias_observership referem-se apenas a '
            'estágios do tipo Observership. Valores em R$.'
        ),
    }


def _snapshot_msg(snapshot):
    return (
        "SNAPSHOT DOS DADOS ATUAIS (gerado pelo sistema, fonte da verdade):\n"
        + json.dumps(snapshot, ensure_ascii=False, default=str)
    )


# ── Chamada à API NVIDIA ──────────────────────────────────────
class AIError(Exception):
    pass


def chamar_nvidia(messages, temperature=0.3, max_tokens=1024, timeout=60):
    """Faz POST para o endpoint chat/completions da NVIDIA NIM.

    `messages`: lista [{role, content}]. Retorna o texto da resposta (str).
    Lança AIError com mensagem amigável em caso de falha.
    """
    if not _enabled():
        raise AIError('Assistente de IA não está configurado.')

    cfg = _config()
    url = f"{cfg['base_url']}/chat/completions"
    payload = {
        'model': cfg['model'],
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
        'stream': False,
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f"Bearer {cfg['api_key']}")
    req.add_header('Accept', 'application/json')

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detalhe = ''
        try:
            detalhe = e.read().decode('utf-8')[:500]
        except Exception:
            pass
        if e.code in (401, 403):
            raise AIError('Chave de API da NVIDIA inválida ou sem permissão.')
        if e.code == 429:
            raise AIError('Limite de uso da API da NVIDIA atingido. Tente mais tarde.')
        raise AIError(f'Erro da API da NVIDIA (HTTP {e.code}). {detalhe}')
    except urllib.error.URLError as e:
        raise AIError(f'Falha de conexão com a API da NVIDIA: {e.reason}')
    except Exception as e:
        raise AIError(f'Erro inesperado ao chamar a IA: {e}')

    try:
        return body['choices'][0]['message']['content'].strip()
    except (KeyError, IndexError, TypeError):
        raise AIError('Resposta inesperada da API da NVIDIA.')


def montar_mensagens(snapshot, historico):
    """Monta a lista final de mensagens: system + snapshot + histórico do chat."""
    msgs = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'system', 'content': _snapshot_msg(snapshot)},
    ]
    for m in historico:
        role = m.get('role')
        content = (m.get('content') or '').strip()
        if role in ('user', 'assistant') and content:
            msgs.append({'role': role, 'content': content})
    return msgs
