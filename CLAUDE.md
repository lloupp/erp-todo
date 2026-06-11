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
```

Módulo **Residentes & Doutorandos** (`/residentes`): público distinto dos estágios, com fluxo baseado em **status** (não etapas numeradas): Interessado → Em andamento → Deferido → Confirmado (+ Trocado, Indeferido, Desistente, Cancelado, Nao veio). Constantes `STATUS_RESIDENTE`, `STATUS_RESIDENTE_COLORS`, `TIPOS_RESIDENTE`, `MODALIDADES_RESIDENTE` em `app.py`. JS em `static/js/residentes.js`, template `residentes.html`.

Migrações de schema são feitas inline no bloco `__main__` do `app.py` via `ALTER TABLE IF NOT EXISTS` — não há framework de migração.

## Produção (Windows)

- Servidor: **Waitress** (`start_erp.bat` → `waitress app:app`, 8 threads). `.env` é carregado automaticamente no topo de `app.py` (cobre todos os pontos de entrada). `SECRET_KEY` é **obrigatória** (sem fallback); ausência derruba o boot, exceto com `FLASK_DEBUG=1`.
- SQLite em **WAL mode** (`get_db()`), com `busy_timeout=5000` — necessário para múltiplas threads. Backups devem usar a API de backup (ver `backup_db.py`), nunca `copy` do `.db` cru (perde dados do `-wal`).
- Backup: `backup_erp.bat` → `backup_db.py` (backup consistente WAL-safe + cópia off-site automática para OneDrive quando instalado + retenção 7 dias). Agendado no Task Scheduler (`ERP-Todo-Backup`, diário 02h).
- Auto-start: Task `ERP-Todo-Server` (gatilho no logon). Endpoint `/health` (sem auth) para monitoramento.
- Logging: `erp.log` com `RotatingFileHandler` (5 MB × 5). Registra login OK/falho com IP e usuário.
- Sync Microsoft Forms: `sync_forms.py` (Task horária) importa planilhas do OneDrive para a tabela `residentes`.

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
- `GET /api/usuarios` — lista usuários (admin)
- `POST /api/usuarios` — cria usuário (admin)
- `PUT /api/usuarios/<id>` — edita usuário (admin)
- `DELETE /api/usuarios/<id>` — remove usuário (admin)

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
