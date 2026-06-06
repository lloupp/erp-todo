# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run (debug mode, port 5000)
python app.py

# Reset database (wipes and re-seeds with sample data)
rm estagios.db && python app.py
```

Default credentials: `admin/admin` (role: admin) and `user/user` (role: user).

## Architecture

Single-file Flask backend (`app.py`) + vanilla JS frontend, no build step.

**Backend** (`app.py`): All routes, DB initialization, business logic, and constants in one file. Database connection is managed via Flask `g` — `get_db()` opens it, `@app.teardown_appcontext` closes it. SQLite rows use `sqlite3.Row` for dict-like access.

**Frontend**: Three page templates (`login.html`, `index.html`, `dashboard.html`) served by Flask. Client logic lives in `static/js/app.js` (main CRUD, modals, filters) and `static/js/dashboard.js` (dashboard charts/stats). No JS framework — vanilla ES6 with direct DOM manipulation. API calls go through `apiFetch(url, options)` which handles JSON parsing and error toasts.

**Auth**: `flask-login` with session cookies. Role-based: `admin` can manage users (`/usuarios`); `user` cannot. Password hashing uses SHA-256 with a random salt (no bcrypt).

**PDF export**: `flask-weasyprint` renders `templates/pdf_ficha.html` server-side; falls back to printable HTML if WeasyPrint fails.

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
```

Schema migrations are handled inline in `app.py`'s `__main__` block via `ALTER TABLE` — there is no migration framework.

## Workflow Stages

Observership starts at etapa 1; Obrigatório/Optativo start at etapa 0. All types share etapas 1–7.

| Etapa | Observership | Obrigatório/Optativo |
|-------|--------------|---------------------|
| 0 | — | Verificação de vaga |
| 1–6 | (shared stages) | (shared stages) |
| 7 | Concluído | Concluído |

Stage constants: `ETAPAS_OBS`, `ETAPAS_OBR_OPT`, `ETAPA_COLORS` in `app.py`.

## Key API Endpoints

All endpoints require login (`@login_required`). Admin-only endpoints check `current_user.role != 'admin'`.

- `GET /api/estagios` — paginated list (15/page); filters: `tipo_id`, `especialidade`, `etapa`, `mes_ano`, `busca`, `status_pagamento`
- `POST /api/estagios/<id>/avancar` — advances stage, logs to `historico_etapas`, optionally sends email
- `GET /api/estagios/<id>/pdf` — WeasyPrint PDF of internship record
- `GET /api/exportar-csv` — CSV/TSV export (same filters as list, `separador` param)
- `GET /api/dashboard` — aggregate stats for dashboard page

## Email Notifications

Disabled by default. Enable via environment variables:

```bash
SMTP_ENABLED=true SMTP_HOST=smtp.gmail.com SMTP_PORT=587 \
SMTP_USER=you@gmail.com SMTP_PASS=app-password SMTP_FROM=you@gmail.com \
python app.py
```

Notifications are always recorded in the `notificacoes` table regardless of whether SMTP is enabled.

## CSS Conventions

CSS custom properties defined in `:root` (`--color-primary`, `--color-border`, etc.). Button classes: `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`, `.btn-sm`. Stage badges use `.badge-tipo` combined with type-specific classes. Responsive breakpoint at `max-width: 900px`. Theme (light/dark) stored in `localStorage` as `theme`.
