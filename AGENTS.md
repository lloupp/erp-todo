# Repository Guidelines

## Project Overview

Medical internship management system for Santa Casa / UFCSPA built with Flask + SQLite. Tracks internships (Observership, Obrigatório, Optativo) through a 9-stage workflow with filtering, history tracking, certificate generation, contact reports, and CSV export compatible with Microsoft tools.

## Architecture & Data Flow

- **Backend**: Single-file Flask app (`app.py`) — all routes, DB init, constants, and business logic
- **Frontend**: Vanilla JS + CSS served via Flask templates; no build step
- **Auth**: `flask-login` with session cookies; role-based (admin/user)
- **PDF**: `flask-weasyprint` for internship forms and certificates
- **Excel import**: `openpyxl` with preview/confirm pattern
- **Production server**: Waitress (Windows) via `run_prod.py`; Gunicorn (Linux) via `gunicorn.conf.py`

## Key Files

| Path | Purpose |
|------|---------|
| `app.py` | Flask app, all routes, DB init, ETAPAS constants, business logic |
| `templates/index.html` | Main internship list + modals |
| `templates/dashboard.html` | Stats and charts |
| `templates/relatorios.html` | Contact report templates (4 types) |
| `templates/usuarios.html` | User management (admin) |
| `templates/certificado.html` | Certificate PDF template (WeasyPrint) |
| `templates/pdf_ficha.html` | Internship form PDF template |
| `static/js/app.js` | Main client logic: CRUD, modals, filters, welcome banner |
| `static/js/dashboard.js` | Dashboard chart rendering |
| `static/css/style.css` | All styling, CSS variables, responsive |
| `run_prod.py` | Production startup (Waitress + dotenv + SECRET_KEY validation) |
| `backup.py` | Windows-compatible backup script |
| `backup.sh` | Linux backup script |
| `.env.example` | Environment variable reference |
| `estagios.db` | SQLite database (gitignored) |

## Development Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Development (debug=True, auto-reload)
python app.py

# Production (Waitress, Windows VPS)
copy .env.example .env   # fill SECRET_KEY
python run_prod.py

# Reset database
rm estagios.db && python app.py

# Backup
python backup.py          # Windows
./backup.sh               # Linux
```

Default credentials: `admin/admin` (role: admin), `user/user` (role: user).

## Database Schema

```sql
tipo_estagio(id, nome)            -- 1=Observership, 2=Obrigatorio, 3=Optativo
usuarios(id, username, password_hash, nome, role, last_login)
estagios(id, tipo_id, mes_ano, semana, nome, cpf, especialidade, cracha,
         valor, forma_pagamento, status_pagamento, comprovante_pagamento,
         inicio, termino, email, telefone, observacao, documentos,
         envio_certificado, etapa, carga_horaria, created_at, updated_at)
historico_etapas(id, estagio_id, etapa, observacao, responsavel, ts)
notificacoes(id, estagio_id, tipo, mensagem, email_destino, enviado, ts)
limite_especialidade(id, especialidade, limite_semanal)
```

Schema migrations are inline in the `if __name__ == '__main__':` block via `ALTER TABLE` — no migration framework. Migrations only run when starting with `python app.py`, not with Waitress/Gunicorn.

## Workflow Stages

Observership starts at stage 1; Obrigatório/Optativo starts at stage 0. All share stages 1–8.

| Stage | Observership | Obrigatório/Optativo |
|-------|---|---|
| 0 | — | Verificação de vaga |
| 1 | Venda realizada | Venda realizada |
| 2 | Pagamento confirmado ★ | Pagamento confirmado ★ |
| 3 | Docs enviados | Docs enviados |
| 4 | Docs validados | Docs validados |
| 5 | Vaga confirmada | Vaga confirmada |
| 6 | Orientações enviadas | Orientações enviadas |
| 7 | Comprovante recebido | Comprovante recebido |
| 8 | Concluído | Concluído |

★ Advancing to stage 2 automatically sets `status_pagamento = 'Pago'`.  
Certificate PDF is unlocked from stage 7.

Constants: `ETAPAS_OBS`, `ETAPAS_OBR_OPT`, `ETAPA_COLORS` in `app.py`.

## Key API Endpoints

All require login (`@login_required`). Admin-only endpoints check `current_user.role`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/estagios` | Paginated list (15/page); filters: `tipo_id`, `especialidade`, `etapa`, `mes_ano`, `semana`, `busca`, `status_pagamento` |
| POST | `/api/estagios` | Create internship |
| PUT | `/api/estagios/<id>` | Update internship |
| DELETE | `/api/estagios/<id>` | Delete (cascades notificacoes → historico_etapas → estagios) |
| POST | `/api/estagios/<id>/avancar` | Advance stage; sets Pago if new stage=2 |
| POST | `/api/estagios/<id>/pago` | Quick-mark as Pago; returns 404 if id not found |
| GET | `/api/estagios/<id>/historico` | Stage history |
| GET | `/api/estagios/<id>/pdf` | WeasyPrint internship form |
| GET | `/api/estagios/<id>/certificado` | Certificate PDF (requires stage ≥ 7) |
| GET | `/api/exportar-csv` | CSV export (BOM UTF-8, `;` separator, CRLF — Excel-ready) |
| GET | `/api/relatorios/exportar` | Contact reports; params: `relatorio`, `preview=1` for JSON |
| POST | `/api/importar-excel` | Excel import; `confirmar=0` preview, `confirmar=1` commit |
| GET | `/api/dashboard` | Aggregated stats |
| GET | `/api/pendencias` | Pending items for welcome banner |
| GET | `/api/vagas` | Weekly capacity by specialty |

## Code Conventions

### Python (Flask)
- DB access via `get_db()` returning connection from Flask `g`; closed by `@app.teardown_appcontext`
- `sqlite3.Row` factory for dict-like access
- SQLite `lower()` does NOT handle accented characters — use Python `.lower()` for case-insensitive dedup
- `dias_na_etapa` computed via `julianday()` subquery against `historico_etapas`
- CSV responses: always include UTF-8 BOM (`﻿`), `\r\n` line endings, `Content-Type: text/csv; charset=utf-8`

### JavaScript (Vanilla ES6)
- `apiFetch(url, options)` wraps fetch + JSON parsing + error toasts
- Modals use `.open` class for visibility (except `usuarios.html` which uses `.active` — do not change without updating both HTML and JS)
- `loadEstagios()` re-renders the full table after any mutation
- Stage progress bar renders `Array.from({length: 9 - minEtapa}, ...)` (9 stages total)

### CSS
- Custom properties in `:root`: `--color-primary`, `--color-border`, etc.
- Button classes: `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`, `.btn-sm`
- Responsive breakpoint: `max-width: 900px`
- Theme (light/dark) saved in `localStorage` as `theme`

## Known Quirks

- SQLite `lower()` doesn't handle accents (`CLÍNICA` → `clÍnica`). All case-insensitive comparisons with accented strings must use Python `.lower()`, never SQL `lower()`.
- `cracha` values `0` or `"Devolvido"` from spreadsheet are converted to `NULL` by the parser.
- The 2026 spreadsheet tab has multiple months in sequence with month-header rows detected by regex.
- Migrations only run in `if __name__ == '__main__':` — must run `python app.py` once before switching to Waitress/Gunicorn on a fresh deploy.
- Modal visibility: `index.html`/`dashboard.html`/`relatorios.html` use `.open`; `usuarios.html` uses `.active`.

## Environment Variables

See `.env.example`. Required in production:

| Variable | Default | Required |
|---|---|---|
| `SECRET_KEY` | `chave-super-secreta-...` | Yes (production) |
| `PORT` | `5000` | No |
| `SMTP_ENABLED` | `false` | No |
| `SMTP_HOST` | `smtp.gmail.com` | If SMTP enabled |
| `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` | — | If SMTP enabled |

`run_prod.py` loads `.env` automatically via `python-dotenv` and exits with a clear error if `SECRET_KEY` is unset or still the default.
