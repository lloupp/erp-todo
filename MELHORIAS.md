# Melhorias Propostas — ERP Estágios Médicos

Levantamento completo de melhorias após auditoria de todo o código (app.py 2.580 linhas, ai.py, 5 JS, 13 templates, CSS, scripts auxiliares). As melhorias estão agrupadas por módulo e priorizadas por impacto.

Prioridade: A (alta) = melhora diretamente o trabalho diário da equipe; B (média) = robustez/segurança; C (baixa) = nice-to-have.

---

## 1. Dashboard — Funil de Conversão (prioridade A)

### Hoje
O dashboard mostra status como donut isolado (`chart-res-status` em `dashboard.js`:257-264). Cada status é um número absoluto sem relação entre eles. Não há noção de "de X interessados, quantos chegam a Confirmado?".

### Problema
Sem funil, a equipe não enxerga gargalos. Se 70 chegam a Deferido mas só 20 a Confirmado, isso é invisível no donut. Não há como responder "onde a gente perde mais gente no pipeline?"

### Proposta
- **Funil de conversão visual** (Chart.js funnel ou barras horizontais decrescentes) mostrando:
  ```
  Interessado (120) ──── 100%
       ↓ 83%
  Em andamento (100) ─── 83%
       ↓ 70%
  Deferido (84) ──────── 70%
       ↓ 60%
  Confirmado (72) ────── 60%
       ↓ 55%
  Concluído (66) ─────── 55%
  ```
- **Taxa de conversão entre cada etapa** exibida sobre as setas (83%, 70%, etc.)
- **Tempo médio por etapa** (em dias): média de dias entre a entrada em cada status e a saída (calculado via `historico_residentes.ts`). Mostra que etapa demora mais (ex: etapa 3 — chefe demora 12 dias em média; etapa 7 — cliente 18 dias).
- **Cards de destaque**: pior etapa em conversão (ex: "Deferido → Confirmado perde 30% — maior gargalo") e etapa mais lenta.

### Onde mexer
- `app.py:965` (`/api/dashboard`): adicionar queries de conversão (contar status sequenciais) e tempo médio (julianday entre timestamps de `historico_residentes`).
- `dashboard.js:256` (`renderCharts`): adicionar `funilChart()`.
- `dashboard.html`: adicionar chart-card para o funil.

### Novos dados da API
```
GET /api/dashboard → somar ao JSON atual:
  "funil": {
    "interessado": 120, "em_andamento": 100, "deferido": 84,
    "confirmado": 72, "concluido": 66,
    "taxas": {"int→and": 83, "and→def": 84, "def→conf": 86, "conf→conc": 92},
    "tempo_medio_dias": {"int→and": 3, "and→def": 12, "def→conf": 18, "conf→conc": 30}
  }
```

---

## 2. Dashboard — Heatmap Especialidade x Status (prioridade A)

### Hoje
Bar chart com top 10 especialidades (`dashboard.js:276-283`). Mostra volume total por especialidade, sem cruzar com status. Não há como ver "Cardiologia tem 5 em andamento e 0 confirmados — problema".

### Problema
A equipe não consegue identificar gargalos por especialidade. Um chefe de serviço que demora a deferir fica invisível até a badge de dias-parado aparecer no registro individual.

### Proposta
- **Matriz cruzada**: linhas = especialidades (top 15), colunas = status (Interessado, Em andamento, Deferido, Confirmado, Concluído).
  ```
                  Int.  And.  Def.  Conf.  Conc.
  Cardiologia      5     3     2     0      0
  Cirurgia Geral   2     4     1     3      1
  Pediatria        0     1     0     2      4
  ```
- **Heatmap visual**: cores mais intensas = mais volume; destaque vermelho para células com alto volume em status intermediário (ex: Cardiologia com 5 em Interessado há semanas).
- **Insights automáticos**: alerta no rodapé: "Cardiologia concentra 40% dos Interessados sem avançar há >14 dias".

### Onde mexer
- `app.py:965` (`/api/dashboard`): adicionar query de contagem cruzada `SELECT especialidade, status, COUNT(*) FROM residentes GROUP BY especialidade, status`.
- `dashboard.js`: adicionar `heatmapChart()` — pode usar Chart.js matrix ou uma tabela HTML estilizada com cores via CSS.
- Considerar agrupar especialidades com `_agrupar_especialidades_residentes` (`app.py:914`) para usar nomes canônicos, não texto livre do Forms.

---

## 3. Dashboard — Financeiro Completo (prioridade A)

### Hoje
Dashboard mostra 3 cards financeiros (`dashboard.js:123-130`): Total Pago, Valor Pendente, e Total (não mostrado explicitamente). Sem quebra temporal, sem ticket médio, sem inadimplência, sem previsão de receita.

### Problema
A gestão não tem visão de receita por mês, não sabe o ticket médio por residente, não tem previsão de caixa, e não enxerga inadimplentes (pendentes há muito tempo).

### Proposta
- **Receita por mês** (bar chart): barras com valor pago por mês, linha overlay com pendente (a cobrar).
- **Ticket médio**: `SUM(valor) / COUNT(confirmados)` por período. Card KPI novo.
- **Inadimplência**: residentes com `status_pagamento=Pendente` E `dias_no_status > 30`. Card KPI com alerta vermelho, com link para a lista filtrada.
- **Previsão de receita**: soma de `valor` de todos os `Deferidos` e `Confirmados` com `status_pagamento=Pendente` — "R$ X a receber nos próximos 60 dias".
- **Conversão financeira**: % de `Confirmados` que pagaram vs. pendentes.

### Onde mexer
- `app.py:965` (`/api/dashboard`): adicionar queries de receita por mês (`SELECT mes_ano, SUM(CASE WHEN status_pagamento='Pago' THEN valor ELSE 0 END), SUM(CASE WHEN status_pagamento='Pendente' THEN valor ELSE 0 END) FROM residentes GROUP BY mes_ano`), ticket médio, inadimplência (`WHERE status_pagamento='Pendente' AND dias > 30`), previsão.
- `dashboard.js`: adicionar `financeiroChart()` (bar+line combinado) e 4 novos KPI cards.

### Novos dados da API
```
"financeiro_avancado": {
  "por_mes": [{"mes_ano": "2026-06", "pago": 15000, "pendente": 3000}, ...],
  "ticket_medio": 850.00,
  "inadimplentes": 7,
  "inadimplentes_valor": 5950.00,
  "previsao_receita": 12000.00,
  "conversao_fin": 85.0
}
```

---

## 4. Dashboard — Ações do Dia / Painel Privado (prioridade A)

### Hoje
O `welcome-banner` em `residentes.js:105-146` mostra pendências genéricas (novos, em andamento, deferidos, pagamentos pendentes). Não há noção de "o que EU preciso fazer hoje" nem de prazos próximos.

### Problema
A equipe precisa clicar em cada registro para saber o que pendencia. Não há um "hoje, fazer X" — a equipe depende de lembrar ou de navegar manualmente pelos filtros.

### Proposta
- **Card "Hoje" no topo do dashboard** (ou na tela `/residentes`):
  - Orientações a enviar hoje/semana (etapa 8 com `T = inicio - 7 dias`, vencendo nos próximos 7 dias)
  - Respostas de chefe pendentes (etapa 3 sem ação 4 há >7 dias)
  - Clientes demorados (etapa 7 sem retorno >7 dias)
  - Pagamentos para confirmar (link enviado, comprovante aguardando)
- **Personalização por responsável**: se houver mais de um admin, mostrar apenas ações atribuídas ao admin logado (requer campo `responsavel_id` em `pipeline_acoes` ou filtro por quem criou a última ação).
- **Links diretos**: cada item do card "Hoje" clica direto no modal de ação do residente.

### Onde mexer
- `app.py`: nova rota `GET /api/pipeline/hoje` que retorna as 4 categorias acima.
- `dashboard.js` ou `residentes.js`: `renderAcoesHoje()` que renderiza o card.
- `dashboard.html`: adicionar div `#acoes-hoje` no topo, antes dos KPI cards.

---

## 5. Dashboard — Filtro de Período Melhorado (prioridade A)

### Hoje
Filtro único por mês/ano (`dashboard.html:19`, `dashboard.js:71-80`). Um `<select>` com meses disponíveis. Sem período customizado, sem filtro por responsável, sem filtro por tipo.

### Problema
A equipe não pode responder "como foi o trimestre?" ou "quantos doutorandos vs. residentes neste período?" ou "o que o admin A triangulou este mês?"

### Proposta
- **Período customizado**: dois `<input type="date">` (início e fim) além do select de mês rápido.
- **Filtro por tipo**: Residente / Doutorando / Todos.
- **Filtro por responsável**: select com usuários admin (para ver o trabalho de cada um).
- **Filtro por modalidade**: Optativo / Convênio.
- **Botões rápidos**: "Este mês", "Trimestre", "Ano", "Tudo".
- **Comparação período vs. período** (bônus): "+25% vs mês anterior" nos KPI cards.

### Onde mexer
- `app.py:965` (`/api/dashboard`): aceitar `data_inicio`, `data_fim`, `tipo`, `responsavel`, `modalidade` como query params, ajustando a cláusula `WHERE` de todas as subqueries.
- `dashboard.html:19`: substituir o select único por um painel de filtros.
- `dashboard.js:57-69` (`loadDashboard`): montar a URL com os novos params.

---

## 6. Segurança (prioridade B)

### 6a. CSRF Protection
**Hoje**: Nenhuma proteção CSRF. `app.py` não usa Flask-WTF nem CSRFProtect.
**Risco**: Um site malicioso pode forjar POST para `/api/residentes` ou `/api/usuarios` se o admin tiver sessão ativa.
**Proposta**: Adicionar `flask-wtf` ou `Flask-CSRFProtect`. Token em meta tag e injetado nos headers do `apiFetch` (`residentes.js:160`, `app.js`).

### 6b. Rate Limiting
**Hoje**: Nenhuma limitação de taxa. `/api/ai/chat` (`app.py:1126`) pode ser chamado sem freio — custo de API OpenRouter sem controle.
**Proposta**: Limitar `/api/ai/chat` a 20 req/min por usuário (usar `flask-limiter` ou contador em memória simples). Limitar `/login` a 5 tentativas/min por IP (proteção contra brute-force — hoje `app.py:416` loga falha mas não bloqueia).

### 6c. SQL f-string (potencial injection)
**Hoje**: 7 ocorrências de f-string em SQL (`app.py:975, 979, 984, 989, 994, 2029, 2223`). As revisadas (`{where_mes}`, `{where}`) usam params separados e a string interpolada vem de código, não de input do usuário — então não é injection ativa hoje, mas é frágil: se alguém adicionar um filtro customizado e montar a string errada, vira brecha.
**Proposta**: Trocar por queries parametrizadas puras. Em vez de `f"SELECT ... {where}"`, usar `SELECT ... " + " AND ".join(conds)` com `params` já separados — que é o padrão usado em `api_get_residentes` (`app.py:2028`). Uniformizar.

### 6d. Silent except (erros engolidos)
**Hoje**: 4 ocorrências de `except Exception:` seguidas de `pass` ou nada (`app.py:1661` na importação Excel, `app.py:767` no PDF, `app.py:798` no certificado, `app.py:2164` no PDF do residente). Erros são silenciados sem log.
**Proposta**: Logar com `app.logger.warning(f'...')` em cada Except silencioso. No mínimo para auditoria — o PDF que falha hoje fica invisível.

### 6e. Senhas hardcoded no seed
**Hoje**: `init_db()` (`app.py:380-385`) cria `admin/admin` e `user/user`. O bloco `__main__` (`app.py:2572-2576`) também cria `admin/admin` se a tabela estiver vazia. Em produção, `CLAUDE.md` diz que as credenciais são `admin/admin`.
**Proposta**: Forçar troca de senha no primeiro login (flag `must_change_password` na tabela `usuarios`). Sem isso, `admin/admin` fica para sempre.

---

## 7. Arquitetura / Manutenibilidade (prioridade B)

### 7a. app.py monolítico — 2.580 linhas
**Hoje**: Todo o backend em um arquivo: rotas, lógica de negócio, parsers de Excel, migrações, auth. Impossível testar isoladamente.
**Proposta**: Dividir em módulos:
```
app.py        → Factory + __main__ (apenas app = Flask(__name__) e run)
routes/
  estagios.py
  residentes.py
  pipeline.py    (novo, do pipeline)
  dashboard.py
  admin.py       (usuarios, vagas, area_medica, mensagens_modelo)
  auth.py
  relatorios.py
models.py     → funções de DB (get_db, init_db, migrações)
parsers.py    → _parse_aba_xlsx, _parse_inscricoes_residentes_xlsx, helpers
```
Importar via `from routes import residentes; residentes.register(app)`. Reduz `app.py` a ~200 linhas.

### 7b. Migrações inline
**Hoje**: 120+ linhas de `ALTER TABLE IF NOT EXISTS` em `__main__` (`app.py:2437-2578`). Sem versionamento, sem rollback. Cada nova coluna é um `if col not in cols: db.execute(ALTER)` manual.
**Proposta**: Adotar um mini-migration runner (não precisa de framework — um `migrations/` com arquivos numerados `001_add_cpf.py`, `002_add_pipeline.py`, etc., executados em sequência com tabela `schema_version`).

### 7c. Sem testes
**Hoje**: Zero testes (`tests/` não existe, `pytest` não está em `requirements.txt`).
**Proposta**: Mínimo viável — testes de integração com `pytest` + `pytest-flask` cobrindo: login/logout, CRUD de residentes, importação Excel (com planilha de teste), avançar status, dashboard KPIs. Meta: 60% das rotas principais.

### 7d. Duplicação de funções JS
**Hoje**: `loadTheme`, `toggleTheme`, `toggleSidebar`, `apiFetch`, `showToast`, `esc` duplicados entre `app.js` (732 linhas) e `residentes.js` (777 linhas). `CLAUDE.md:155` já alerta: "manter ambas em sincronia".
**Proposta**: Extrair para `static/js/common.js` importado por todas as páginas. Reduz ~150 linhas de duplicata.

---

## 8. Importação / Integração (prioridade B)

### 8a. sync_forms.py citado mas não existe no repo
**Hoje**: `CLAUDE.md:90` menciona "Sync Microsoft Forms: `sync_forms.py` (Task horária) importa planilhas do OneDrive para a tabela `residentes`." Mas o arquivo não está no repo (busca por `sync_forms` retorna 0 ocorrências).
**Proposta**: Recriar `sync_forms.py` usando Microsoft Graph API (ou pelo menos Baileta/ requests para OneDrive). Deve: baixar planilha do OneDrive, rodar `_parse_inscricoes_residentes_xlsx`, deduplicar e inserir. Logar cada execução em `pipeline_log` (nova tabela).

### 8b. Importar_consolidado.py com path hardcoded
**Hoje**: `importar_consolidado.py:13` tem `XLSX = r'C:\Users\eduardo.dantas\Downloads\Observership_2025_Consolidado.xlsx'` — path Windows fixo de um usuário específico.
**Proposta**: Aceitar path como argumento: `python importar_consolidado.py <caminho> [--confirmar]`. Ou mover para o endpoint `/api/importar-excel` que já existe e funciona via upload web.

### 8c. Parser não rejeita linhas inválidas
**Hoje**: `_parse_inscricoes_residentes_xlsx` (`app.py:2302`) faz fallback `mes_ano = '2026-01'` quando não encontra o mês — cria registros com mês errado que o admin precisa corrigir manualmente.
**Proposta**: Retornar erros em vez de criar com fallback. O preview da importação (`/api/residentes/importar-excel` com `confirmar=0`) deve mostrar "5 linhas com mês inválido — corrigir na planilha antes de importar".

---

## 9. UX / Frontend (prioridade C)

### 9a. Residentes sem ordenar por dias parado
**Hoje**: `ORDENACOES` em `app.py:2021-2025` suporta `recentes`, `nome`, `mes_ano`. Não há "mais parado" (ordenar por `dias_no_status DESC`).
**Proposta**: Adicionar `parados` como opção de ordenação — útil para triagem rápida de quem está esquecido.

### 9b. Sem busca global
**Hoje**: Busca em `/residentes` só busca dentro dos campos da tabela (`nome`, `email`, `cpf`, etc.). Não há busca em histórico nem em observações de ações do pipeline.
**Proposta**: Busca global que retorna residentes + estagios + ações do pipeline com o termo.

### 9c. Toasts não persistem
**Hoje**: `showToast` em `residentes.js:172` some em 4 segundos. Se a página recarrega, mensagens de sucesso/falha se perdem.
**Proposta**: Para ações importantes (importação, avançar status em lote), usar flash messages do Flask (persistem uma redireção) ou um banner de status.

### 9d. Sem atalhos de teclado
**Hoje**: Navegação 100% por mouse.
**Proposta**: `/` foca busca, `n` novo residente, `Esc` fecha modal, setas navegam paginação. Reduz cliques na operação diária.

### 9e. Dark mode incompleto
**Hoje**: 6 seletores `[data-theme="dark"]` no CSS (linhas 29, 177, 268, 344, 345) — alguns componentes como relatorios.html e configuracoes.html não são testados em dark.
**Proposta**: Auditoria visual completa em dark mode em todas as telas. Padronizar via CSS variables (já parcialmente em `:root`).

---

## 10. Busca / Observabilidade (prioridade C)

### 10a. Sem log de auditoria de ações
**Hoje**: `historico_residentes` grava mudança de status, mas não grava edições de campos (ex: corrigir especialidade, alterar valor). `app.py:2081` (`api_update_residente`) faz UPDATE silencioso sem log.
**Proposta**: Antes do UPDATE, diff com o registro anterior e gravar campos alterados em `historico_residentes` (ou tabela `auditoria` separada).

### 10b. Erro do WeasyPrint silenciado
**Hoje**: `app.py:767` (`api_estagio_pdf`) tem `except Exception: return html` — se o PDF falha, retorna HTML puro sem log. O usuário acha que baixou PDF mas recebeu HTML.
**Proposta**: Logar o erro (`app.logger.warning(f'PDF falhou para estagio {estagio_id}: {e}')`) e mostrar toast no frontend "PDF indisponível, exibindo HTML".

### 10c. Sem health check do banco
**Hoje**: `/health` (`app.py:449`) faz `SELECT 1` — só verifica que o SQLite responde. Não verifica integridade referencial, tamanho do WAL, ou tabelas esperadas.
**Proposta**: Health check estendido que também verifica: tabelas esperadas existem, contagem de linhas em cada uma, tamanho do arquivo `.db` + `.db-wal`, últimas N linhas de `erp.log`.

---

## 11. IA / Assistente (prioridade C)

### 11a. Snapshot stale em sessão longa
**Hoje**: `montar_snapshot` (`ai.py:69`) é chamado a cada request de chat (`app.py:1138`). Mas se o admin fica com o chat aberto e outra pessoa altera dados, o snapshot atualiza so no próximo request (não em tempo real).
**Proposta**: Aceitável para o volume atual. Documentar que o snapshot é point-in-time e o FAB tem tooltip "dados de HH:MM".

### 11b. Sem streaming
**Hoje**: `chamar_openrouter` (`ai.py:140`) usa `stream: False`. O usuário espera a resposta completa chegar de uma vez (pode levar 5-10s com o modelo `hy3:free` que raciocina).
**Proposta**: Implementar Server-Sent Events para streaming de tokens (`stream: True` na API, `Response(generator, mimetype='text/event-stream')` no Flask). Melhora UX perceptível.

### 11c. Sem contexto do pipeline
**Hoje**: O snapshot da IA (`ai.py:69`) inclui agregados de residentes mas não inclui pipeline_acoes (porque a tabela ainda não existe).
**Proposta**: Após criar `pipeline_acoes`, incluir no snapshot: pendentes por etapa, atrasos, ações do dia. A IA passa a responder "quantos estão aguardando chefe?" sem a equipe precisar abrir o sistema.

---

## Priorização sugerida para implementação

Fase 1 (maior impacto, 1-2 dias):
- Dashboard item 1 (funil de conversão)
- Dashboard item 5 (filtro de período melhorado)
- Dashboard item 4 (ações do dia)

Fase 2 (impacto alto, 1-2 dias):
- Dashboard item 2 (heatmap especialidade x status)
- Dashboard item 3 (financeiro completo)

Fase 3 (robustez, 2-3 dias):
- Segurança 6a (CSRF) e 6b (rate limiting)
- Arquitetura 7d (common.js)

Fase 4 (qualidade, contínuo):
- Arquitetura 7a (dividir app.py) e 7c (testes)
- Importação 8a (sync_forms.py)
- UX 9 e observabilidade 10

---

## Observações de auditoria

- 26 rotas em `app.py`, 24 com `@login_required`, 15 com check de `role != 'admin'`. As 2 sem login (`/health`, `/login`) são legítimas. Nenhuma rota admin exposta sem check.
- 7 f-strings em SQL — não há injection ativa hoje (todas interpolam `where` construído internamente), mas é frágil.
- 4 `except Exception: pass` silenciam erros sem log — PDF e importação.
- Zero testes no projeto.
- `sync_forms.py` referenciado em `CLAUDE.md` mas não existe no repo.
- `importar_consolidado.py` tem path Windows hardcoded de um usuário específico.
- Funções JS duplicadas entre `app.js` e `residentes.js` (~150 linhas de duplicata).
- `init_db` cria `admin/admin` e `user/user` sem forçar troca.
- Dark mode cobre ~6 seletores — relatorios e configuracoes não foram auditados.
