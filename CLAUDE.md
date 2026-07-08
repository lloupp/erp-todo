# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run (debug mode, porta 5000)
python app.py

# Produção (Gunicorn)
gunicorn -c gunicorn.conf.py app:app

# Reset do banco (apaga e recria com dados de exemplo)
rm estagios.db && python app.py

# Backup manual do SQLite
./backup.sh
```

Default credentials: `admin/admin` (role: admin) e `user/user` (role: user).

## Architecture

Single-file Flask backend (`app.py`) + vanilla JS frontend, sem build step.

**Backend** (`app.py`): Todas as rotas, inicialização do banco, lógica de negócio e constantes em um único arquivo. Conexão com banco gerenciada via Flask `g` — `get_db()` abre, `@app.teardown_appcontext` fecha. Rows do SQLite usam `sqlite3.Row` para acesso dict-like.

**Frontend**: Quatro templates (`login.html`, `index.html`, `dashboard.html`, `usuarios.html`) servidos pelo Flask. Lógica client-side em `static/js/app.js` (CRUD principal, modais, filtros) e `static/js/dashboard.js` (gráficos/stats do dashboard). Sem framework JS — vanilla ES6 com manipulação direta do DOM. Chamadas API passam por `apiFetch(url, options)` que trata JSON e exibe toasts de erro.

**Auth**: `flask-login` com session cookies. Role-based: `admin` gerencia usuários (`/usuarios`); `user` não acessa. Hashing de senha com SHA-256 + salt aleatório. `last_login` gravado a cada login bem-sucedido.

**PDF export**: `flask-weasyprint` renderiza `templates/pdf_ficha.html` server-side; fallback para HTML imprimível se WeasyPrint falhar.

**Importação Excel**: `openpyxl` parseia a planilha de controle de vagas. Endpoint `POST /api/importar-excel` — `confirmar=0` retorna preview (sem gravar), `confirmar=1` grava. Deduplicação por `(nome.lower(), especialidade.lower(), mes_ano)` usando Python (não SQLite, que não trata acentos corretamente com `lower()`).

**Alertas de prazo**: Campo `dias_na_etapa` calculado via subquery `julianday()` no SQLite contra `historico_etapas`. Na tabela principal, badge laranja (⚠ Xd) após 7 dias e vermelho após 14 dias na mesma etapa.

**Backup**: `backup.sh` copia o SQLite para `backups/` com retenção de 7 dias. Crontab sugerido: `0 2 * * * /path/to/erp-todo/backup.sh`.

## Database Schema

```sql
tipo_estagio(id, nome)          -- 1=Observership, 2=Obrigatorio, 3=Optativo
usuarios(id, username, password_hash, nome, role, last_login)
estagios(id, tipo_id, mes_ano, semana, nome, cpf, especialidade, cracha,
         valor, forma_pagamento, status_pagamento, comprovante_pagamento,
         inicio, termino, email, telefone, observacao, documentos,
         envio_certificado, etapa, created_at, updated_at)
historico_etapas(id, estagio_id, etapa, observacao, responsavel, ts)
notificacoes(id, estagio_id, tipo, mensagem, email_destino, enviado, ts)
residentes(id, nome, email, telefone, cpf, tipo, modalidade, especialidade,
           subespecialidade, instituicao_origem, programa_ano, mes_ano,
           inicio, termino, status, valor, forma_pagamento, status_pagamento,
           comprovante_pagamento, observacao, data_inscricao, periodo_desejado,
           mes_desejado, created_at, updated_at)
historico_residentes(id, residente_id, status, observacao, responsavel, ts)
limite_especialidade(id, especialidade, limite_semanal)          -- limites semanais (módulo Vagas)
area_medica(id, especialidade, nome, celular, email, obs_internato, obs_residencia)
mensagens_modelo(id, chave, titulo, texto, placeholders)         -- templates de mensagem WhatsApp editáveis
pipeline_acoes(id, residente_id, etapa, acao_tipo, situacao, responsavel,
               observacao, reagendado_para, criado_em, concluido_em)
```

Módulo **Residentes & Doutorandos** (`/residentes`): público distinto dos estágios, com fluxo baseado em **status** (não etapas numeradas): Interessado → Em andamento → Deferido → Confirmado → Concluído (+ Trocado, Indeferido, Desistente, Cancelado, Nao veio). Constantes `STATUS_RESIDENTE`, `STATUS_RESIDENTE_COLORS`, `TIPOS_RESIDENTE`, `MODALIDADES_RESIDENTE` em `app.py`. JS em `static/js/residentes.js`, template `residentes.html`. É o **módulo prioritário** do ERP (tela inicial padrão pós-login).

- `ordenar` (`GET /api/residentes`): `recentes` (padrão no front, `created_at DESC`) | `nome` | `mes_ano`.
- `dias_no_status`: campo calculado (subquery `julianday()` contra `historico_residentes`, mesmo padrão de `dias_na_etapa` do Observership) — badge ⚠ no front (7d/14d) só para status "em aberto" (`Interessado`, `Em andamento`, `Deferido`; ver `STATUS_PENDENTES` em `residentes.js`).
- `GET /api/residentes/<id>/pdf`: ficha em PDF (WeasyPrint, `templates/pdf_ficha_residente.html`), mesmo padrão do PDF de estágio.
- **Botão WhatsApp (aluno)**: por registro, usa `telefone` cadastrado, abre `wa.me` com saudação padrão.
- **Botão Área Médica**: por registro, contata o chefe de serviço da especialidade (não o aluno). Contatos ficam na tabela `area_medica` (CRUD via `/api/area-medica`, aberto a qualquer usuário logado); `data/area_medica.json` é usado só como seed inicial (`INSERT OR IGNORE`, uma vez, no bloco `__main__`) — para atualizar contatos em produção, editar pela tela de Configurações, não o JSON. O front (`residentes.js`) sugere automaticamente o contato mais provável comparando a especialidade em texto livre do formulário com a lista oficial (`melhorMatchAreaMedica`, scoring por palavras), mas **sempre abre um modal de confirmação** com select manual + mensagem editável antes de enviar — a especialidade digitada pelo candidato é texto livre não normalizado, então o match automático é só uma sugestão.
- **Mensagens de template (WhatsApp)**: textos editáveis via tela de Configurações, tabela `mensagens_modelo` (chaves `whatsapp_aluno`, `whatsapp_area_medica`; seed em `MENSAGENS_MODELO_SEED` em `app.py`). Endpoints `GET /api/mensagens-modelo` e `PUT /api/mensagens-modelo/<chave>`, ambos abertos a qualquer usuário logado. Placeholders tipo `{{nome}}` são substituídos no client antes de abrir o `wa.me`.

### Pipeline de atendimento (Residentes)

Ver `PIPELINE.md` para o desenho funcional completo (8 etapas, do cadastro à conclusão). **Princípio central: nada é enviado automaticamente** — cada etapa exige um clique humano que abre WhatsApp/e-mail com mensagem pré-preenchida e editável antes do envio.

- Tabela `pipeline_acoes`: cada residente tem no máximo **uma ação `pendente` por vez** (a etapa corrente do seu atendimento). `situacao` é `pendente` | `feita` | `pulado`.
- Constantes em `app.py`: `PIPELINE_ETAPAS` (nome de cada etapa) e `PIPELINE_TRANSICOES` (mapa `etapa -> {resultado: (novo_status_residente|None, proxima_etapa|None)}`).
- Função central `avancar_pipeline(db, residente_id, etapa_atual, resultado, responsavel, observacao)` — marca a ação da etapa atual, muda `residentes.status` quando aplicável (gravando em `historico_residentes`, mesmo padrão de `api_avancar_residente`) e cria a próxima ação pendente. É o único ponto que sabe a tabela de transições — rotas nunca implementam a lógica de estado diretamente.
- Ação `pendente` inicial (etapa 1, "triagem") é criada automaticamente ao cadastrar (`POST /api/residentes`) ou importar (`POST /api/residentes/importar-excel`) um residente, via `criar_acao_pipeline`.
- Endpoints (todos abertos a qualquer usuário logado, sem restrição de role): `POST /api/residentes/<id>/acao` (body `{etapa, resultado, observacao}`, chama `avancar_pipeline`), `GET /api/pipeline/fila` (lista ações pendentes com dados do residente e dias parado), `GET /api/pipeline/fila/<etapa>`, `GET /api/pipeline/residente/<id>` (histórico completo do pipeline de um residente), `GET /api/pipeline/dashboard` (KPIs: pendentes por etapa, críticos >14d, feitos).
- **Entrega 1** (etapas 1-4: triagem → confirmação do aluno → acionamento do chefe → deferimento/indeferimento/troca) e **Entrega 2** (etapas 5-8: financeiro → conclusão) estão implementadas. Ver `PIPELINE.md` para o desenho funcional completo e as divergências já mapeadas entre a especificação e o código.
- **Etapas 5-8** (`solicitar_link_financeiro`, `enviar_link_docs`, `analisar_comprovante`, `orientacoes_1o_dia`): contato do financeiro é uma linha em `area_medica` com `especialidade='Financeiro'` (cadastro manual pela tela de Configurações — **não vem em nenhum seed**, o admin precisa criar antes de usar a etapa 5; se ausente, o modal avisa e desabilita o botão de WhatsApp). Etapa 7 tem dois desfechos: `comprovante_ok` (status → `Confirmado`, avança para etapa 8) ou `falta_documento` (sem mudar status, volta para etapa 6 pendente). Etapa 8 muda o status para `Concluído` e encerra o pipeline do residente.
- **Agendamento da etapa 8** (`reagendado_para`): calculado em `avancar_pipeline` no momento em que a etapa 7 é concluída com `comprovante_ok`, como `residentes.inicio - 7 dias`. Sem `inicio` preenchido, a ação fica pendente sem data-alvo (cai na fila manual, sem destaque). Na fila (`GET /api/pipeline/fila*`), a etapa 8 só aparece destacada em vermelho ("Enviar hoje!") quando `reagendado_para <= hoje`; antes disso mostra a data agendada, sem alarde.
- **3 mensagens-modelo novas** (Entrega 2, mesmo padrão de `MENSAGENS_MODELO_SEED`): `whatsapp_financeiro_link` (etapa 5, enviada ao contato Financeiro, não ao aluno), `whatsapp_cliente_link_docs` (etapa 6, campos `link` e `documentos` preenchidos manualmente no modal — não vêm do cadastro do residente), `whatsapp_cliente_orientacoes` (etapa 8, campos `local` e `orientacoes` preenchidos manualmente no modal).
- Frontend: painel "Fila de Atendimento" em `residentes.html`/`residentes.js` (`carregarPipelineFila`, `#pipeline-fila-panel`), visível para qualquer usuário logado, com modal genérico de ação (`abrirModalPipelineAcao`, `#modal-pipeline-acao`) que monta a mensagem (reaproveitando `montarMensagemAreaMedica`/`montarPeriodoTexto`/`preencherTemplate`) e chama `POST /api/residentes/<id>/acao` ao confirmar um resultado. Etapas com campos que não vêm do cadastro (6 e 8) renderizam inputs extras em `#pa-extra-campos` e recalculam a mensagem via `recalcularMensagemPipeline`. Ao confirmar, o modal fecha e a fila/lista são recarregadas — cada ação é tratada individualmente, sem encadeamento automático entre pendências.
- Status `'Concluído'` foi adicionado a `STATUS_RESIDENTE`/`STATUS_RESIDENTE_COLORS` para o desfecho da etapa 8 — não confundir com a etapa `Concluido` do módulo antigo de Estágios (conceito diferente, desativado).
- **Saída do pipeline por fora do fluxo**: se o status do residente for alterado sem passar pelo modal de ação (edição direta do cadastro via `PUT /api/residentes/<id>`, ou o botão antigo "Avançar Status" via `POST /api/residentes/<id>/avancar`), `fechar_pipeline_pendente(db, residente_id, motivo, responsavel)` marca qualquer ação `pendente` daquele residente como `pulado` — assim ele sai da Fila de Atendimento em vez de ficar com uma ação desatualizada parada lá. Só dispara quando o status realmente muda (comparado ao valor anterior); editar outros campos sem mudar o status não mexe no pipeline.
- **Ações do pipeline refletidas no histórico do residente** (mão inversa da anterior): nem toda ação de pipeline muda `residentes.status` (ex.: etapa 3 "enviado ao chefe", etapa 5 "solicitado ao financeiro" não mudam status), então essas ações nunca apareciam em `historico_residentes`. `GET /api/residentes/<id>/historico` agora mescla `historico_residentes` com as linhas de `pipeline_acoes` já concluídas (`situacao != 'pendente'`), ordenadas por timestamp, cada uma marcada com `tipo: 'status'` ou `tipo: 'pipeline'` — o modal de Histórico em `residentes.js` (`abrirHistorico`) renderiza os dois tipos com badges diferentes. Isso é só para exibição: a ação pendente atual continua vindo só da Fila de Atendimento, e o cálculo de `dias_no_status` continua baseado só em `historico_residentes` (não em `pipeline_acoes`), para não resetar o alerta de dias parado toda vez que uma sub-ação do pipeline acontece dentro do mesmo status.

Migrações de schema são feitas inline no bloco `__main__` do `app.py` via `ALTER TABLE IF NOT EXISTS` — não há framework de migração.

## Observership (desativado no ERP)

O módulo Observership (`tipo_id=1` em `estagios`) é **gerenciado externamente pela e-commerce** e foi desativado no ERP: `/` redireciona para `/residentes`, e o link sumiu da sidebar (junto com "Vagas", que só existia para o limite semanal do Observership). **Os dados não foram apagados** — a tabela `estagios` e as rotas `/api/estagios*` continuam intactas e alimentam o Dashboard e o Assistente IA. Reativar exigiria restaurar a rota `/` (`app.py`) e o link na sidebar (`templates/_sidebar.html`).

## Produção (Windows)

- Servidor: **Waitress** (`start_erp.bat` → `waitress app:app`, 8 threads). `.env` é carregado automaticamente no topo de `app.py` (cobre todos os pontos de entrada). `SECRET_KEY` é **obrigatória** (sem fallback); ausência derruba o boot, exceto com `FLASK_DEBUG=1`.
- SQLite em **WAL mode** (`get_db()`), com `busy_timeout=5000` — necessário para múltiplas threads. Backups devem usar a API de backup (ver `backup_db.py`), nunca `copy` do `.db` cru (perde dados do `-wal`).
- Backup: `backup_erp.bat` → `backup_db.py` (backup consistente WAL-safe + cópia off-site automática para OneDrive quando instalado + retenção 7 dias). Agendado no Task Scheduler (`ERP-Todo-Backup`, diário 02h).
- Auto-start: Task `ERP-Todo-Server` (gatilho no logon). Endpoint `/health` (sem auth) para monitoramento.
- Logging: `erp.log` com `RotatingFileHandler` (5 MB × 5). Registra login OK/falho com IP e usuário.
- Sync Microsoft Forms: `sync_forms.py` (Task horária) importa planilhas do OneDrive para a tabela `residentes`.

## Assistente IA (OpenRouter)

Botão flutuante global (FAB) presente em todas as telas via `templates/_sidebar.html`, que carrega `static/js/ai.js`. Backend em `ai.py` (módulo separado para não inchar `app.py`).

- **Config (.env)**: `AI_ENABLED`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `tencent/hy3:free`, um modelo gratuito da OpenRouter), `OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`). Sem chave, `ai.is_enabled()` é falso e o FAB não aparece.
- **HTTP**: `urllib.request` da stdlib (sem nova dependência). Endpoint OpenAI-compatible `chat/completions`, `stream:false`.
- **Segurança**: a IA **não gera nem executa SQL**. `ai.montar_snapshot(db)` pré-computa agregações read-only (reusa as queries de `/api/dashboard` e `/api/pendencias`) + listas de registros recentes. **Política de PII**: o snapshot inclui nome/especialidade/status, mas **nunca CPF, e-mail ou telefone**.
- **Endpoints** (`@login_required`): `GET /api/ai/status` → `{enabled}`; `POST /api/ai/chat` (body `{messages:[...]}`, histórico limitado a 12); `GET /api/ai/insights` (resumo executivo). Erros viram `AIError` com mensagem amigável (HTTP 502).

## Workflow Stages

Observership começa na etapa 1; Obrigatório/Optativo na etapa 0. Todos compartilham etapas 1–7.

| Etapa | Observership | Obrigatório/Optativo |
|-------|--------------|---------------------|
| 0 | — | Verificação de vaga |
| 1–6 | (etapas compartilhadas) | (etapas compartilhadas) |
| 7 | Concluído | Concluído |

Constantes de etapa: `ETAPAS_OBS`, `ETAPAS_OBR_OPT`, `ETAPA_COLORS` em `app.py`.

## Key API Endpoints

Todos os endpoints exigem login (`@login_required`). Endpoints admin-only verificam `current_user.role != 'admin'`.

- `GET /api/me` — dados do usuário logado (`nome`, `role`)
- `GET /api/estagios` — lista paginada (15/pág); filtros: `tipo_id`, `especialidade`, `etapa`, `mes_ano`, `busca`, `status_pagamento`. Busca abrange: nome, email, crachá, CPF, especialidade, observação. Inclui `dias_na_etapa` calculado.
- `POST /api/estagios` — cria novo estágio
- `PUT /api/estagios/<id>` — atualiza estágio
- `DELETE /api/estagios/<id>` — remove estágio
- `POST /api/estagios/<id>/avancar` — avança etapa, loga em `historico_etapas`, envia email opcionalmente
- `GET /api/estagios/<id>/historico` — histórico de etapas
- `GET /api/estagios/<id>/pdf` — PDF WeasyPrint da ficha
- `GET /api/exportar-csv` — exportação CSV/TSV (mesmos filtros da lista, param `separador`)
- `GET /api/dashboard` — stats agregadas para o dashboard
- `POST /api/importar-excel` — importação de planilha; `confirmar=0` preview, `confirmar=1` grava
- `GET /api/relatorios/exportar` — relatórios de re-contato (`relatorio=egressos|pendentes|parados|especialidade`, `preview=1` para JSON)
- `GET /api/usuarios` — lista usuários (admin)
- `POST /api/usuarios` — cria usuário (admin)
- `PUT /api/usuarios/<id>` — edita usuário (admin)
- `DELETE /api/usuarios/<id>` — remove usuário (admin)
- `GET/POST/PUT/DELETE /api/limites` — limites semanais por especialidade, módulo **Vagas** (`/vagas`, admin-only, sem link na sidebar — acesso só por URL direta); `GET /api/vagas-semana?mes_ano=&semana=` calcula vagas usadas/livres
- `GET/POST/PUT/DELETE /api/area-medica` — contatos de chefes de serviço por especialidade (tela **Configurações**, `/configuracoes`, aberta a qualquer usuário logado)
- `GET /api/mensagens-modelo`, `PUT /api/mensagens-modelo/<chave>` — templates de mensagem WhatsApp editáveis (tela Configurações, aberta a qualquer usuário logado)
- `POST /api/residentes/<id>/acao` — avança uma etapa do pipeline de atendimento (aberto a qualquer usuário logado); body `{etapa, resultado, observacao}`, ver seção "Pipeline de atendimento (Residentes)"
- `GET /api/pipeline/fila`, `GET /api/pipeline/fila/<etapa>` — fila de ações pendentes do pipeline (aberto a qualquer usuário logado)
- `GET /api/pipeline/residente/<id>` — histórico completo do pipeline de um residente (aberto a qualquer usuário logado)
- `GET /api/pipeline/dashboard` — KPIs do pipeline (pendentes por etapa, críticos, feitos)

## Email Notifications

Desabilitado por padrão. Habilitar via variáveis de ambiente:

```bash
SMTP_ENABLED=true SMTP_HOST=smtp.gmail.com SMTP_PORT=587 \
SMTP_USER=you@gmail.com SMTP_PASS=app-password SMTP_FROM=you@gmail.com \
python app.py
```

Notificações são sempre gravadas na tabela `notificacoes` independente do SMTP estar ativo.

## CSS Conventions

Custom properties CSS definidas em `:root` (`--color-primary`, `--color-border`, etc.). Classes de botão: `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`, `.btn-sm`. Badges de etapa usam `.badge-tipo` combinado com classes por tipo. Breakpoint responsivo em `max-width: 900px`. Tema (light/dark) salvo em `localStorage` como `theme`.

Modais usam a classe `.open` para exibição (ex: `modal-overlay.open`) em todas as páginas.

A sidebar é um partial único `templates/_sidebar.html` incluído via `{% include %}`; cada página define `{% set active_page = '...' %}` antes do include para marcar o item ativo. Links admin-only (Usuários/Vagas) ficam `display:none` por padrão e são revelados por um script no próprio partial que consulta `/api/me`. Funções utilitárias de tema/sidebar/toast estão duplicadas entre `app.js` e `residentes.js` — manter ambas em sincronia (ex.: `loadTheme` usa `document.documentElement`).

## Known Quirks

- SQLite `lower()` não trata acentos (`CLÍNICA` → `clÍnica`). Toda deduplicação case-insensitive com acentos deve usar Python `.lower()`, nunca SQL `lower()`.
- `cracha` vem como `0` ou `"Devolvido"` em algumas abas da planilha — o parser converte para `NULL`.
- A aba "2026" da planilha contém múltiplos meses em sequência com linhas de cabeçalho de mês intercaladas; o parser detecta essas linhas por regex.
