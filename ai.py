"""
Assistente IA do ERP via OpenRouter (OpenAI-compatible).

Princípio de segurança:
- A IA NUNCA gera nem executa SQL. O backend pré-computa um *snapshot* read-only
  (agregações + lista enxuta de registros) e injeta como contexto.
- Política de PII: o snapshot inclui agregados, nomes e especialidades, mas
  NUNCA CPF, e-mail ou telefone.

Configuração via variaveis de ambiente (.env):
    AI_ENABLED=true
    OPENROUTER_API_KEY=<chave>
    OPENROUTER_MODEL=tencent/hy3:free
    OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
"""

import os
import json
import urllib.request
import urllib.error


# ── Configuração ──────────────────────────────────────────────
def _enabled():
    return (
        os.environ.get('AI_ENABLED', 'false').lower() == 'true'
        and bool(os.environ.get('OPENROUTER_API_KEY', '').strip())
    )


def is_enabled():
    """Recurso de IA ativo? (flag ligada + chave presente)."""
    return _enabled()


def _config():
    return {
        'api_key': os.environ.get('OPENROUTER_API_KEY', '').strip(),
        'model': os.environ.get('OPENROUTER_MODEL', 'tencent/hy3:free').strip(),
        'base_url': os.environ.get(
            'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'
        ).strip().rstrip('/'),
    }


SYSTEM_PROMPT = (
    "Você é o assistente do ERP da Santa Casa/UFCSPA, focado no módulo de "
    "Residentes & Doutorandos (o módulo ativo do sistema). Ajuda a equipe "
    "administrativa a entender inscrições, status (Interessado, Em andamento, "
    "Deferido, Confirmado, etc.), pagamentos e especialidades.\n\n"
    "O antigo módulo de Estágios/Observership foi desativado neste ERP e é "
    "gerenciado externamente por outro sistema — você NÃO tem esses dados e "
    "não deve comentar sobre ele; se perguntarem, diga que esse módulo não é "
    "mais gerenciado por aqui.\n\n"
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
    """Monta um resumo estruturado dos dados de Residentes & Doutorandos, SEM CPF/e-mail/telefone.

    O módulo de Estágios/Observership foi desativado no ERP (gerenciado externamente)
    e por isso não entra no snapshot da IA. Reaproveita as mesmas agregações de
    /api/dashboard e /api/pendencias. Retorna um dict serializável em JSON.
    """
    def rows(sql, params=()):
        return db.execute(sql, params).fetchall()

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
    res_recentes = rows('''
        SELECT nome, COALESCE(tipo,'') AS tipo, COALESCE(especialidade,'') AS especialidade,
               status, COALESCE(mes_ano,'') AS mes_ano
        FROM residentes ORDER BY updated_at DESC LIMIT 15
    ''')

    return {
        'residentes': {
            'total': total_res,
            'por_status': [dict(r) for r in res_por_status],
            'por_tipo': [dict(r) for r in res_por_tipo],
            'por_especialidade': [dict(r) for r in res_por_esp],
            'pendencias': dict(res_pend) if res_pend else {},
            'recentes': [dict(r) for r in res_recentes],
        },
        'observacoes': (
            'Status possíveis: Interessado, Em andamento, Deferido, Confirmado, '
            'Trocado, Indeferido, Desistente, Cancelado, Nao veio. '
            'pendencias.novos/em_andamento/deferidos/confirmados contam por status atual. '
            'pendencias.pag_pendente conta pagamentos pendentes (exclui status encerrados). Valores em R$.'
        ),
    }


def _snapshot_msg(snapshot):
    return (
        "SNAPSHOT DOS DADOS ATUAIS (gerado pelo sistema, fonte da verdade):\n"
        + json.dumps(snapshot, ensure_ascii=False, default=str)
    )


# ── Chamada à API OpenRouter ───────────────────────────────────
class AIError(Exception):
    pass


def chamar_openrouter(messages, temperature=0.3, max_tokens=2048, timeout=60):
    """Faz POST para o endpoint chat/completions da OpenRouter.

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
    # Headers recomendados pela OpenRouter para atribuição/rankings (opcionais).
    req.add_header('HTTP-Referer', 'https://github.com/erp-todo')
    req.add_header('X-Title', 'ERP Estagios - Assistente IA')

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
            raise AIError('Chave de API da OpenRouter inválida ou sem permissão.')
        if e.code == 429:
            raise AIError('Limite de uso da API da OpenRouter atingido. Tente mais tarde.')
        raise AIError(f'Erro da API da OpenRouter (HTTP {e.code}). {detalhe}')
    except urllib.error.URLError as e:
        raise AIError(f'Falha de conexão com a API da OpenRouter: {e.reason}')
    except Exception as e:
        raise AIError(f'Erro inesperado ao chamar a IA: {e}')

    try:
        msg = body['choices'][0]['message']
    except (KeyError, IndexError, TypeError):
        raise AIError('Resposta inesperada da API da OpenRouter.')

    conteudo = msg.get('content')
    if not conteudo:
        # Modelos de raciocínio (como o hy3:free) podem gastar todo o max_tokens
        # pensando internamente e nunca escrever a resposta final (finish_reason=length).
        raise AIError('A IA ficou sem espaço de resposta antes de concluir. Tente novamente ou faça uma pergunta mais objetiva.')
    return conteudo.strip()


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
