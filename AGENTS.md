# Repository Guidelines

## Project Overview

Medical internship management system for Santa Casa / UFCSPA built with Flask + SQLite. Tracks internships (Observership, Obrigatório, Optativo) and Residents/Doutorandos through workflow stages, filtering, history, documents, reports and exports.

## Architecture & Data Flow

- **Application entry point**: `app.py` is the supported safe facade. It exposes the Flask application, installs security guards, uses adaptive password hashing and bootstraps the database through `db_migrations.py`.
- **Legacy route implementation**: `legacy_app.py` contains the historical route/business implementation imported by the safe facade. Do not use it as a startup command or migration entry point.
- **Database migrations**: `db_migrations.py` owns additive, idempotent bootstrap/migrations. Supported startup paths must use it; do not add migration SQL to a `__main__` block.
- **Frontend**: Vanilla JS + CSS served via Flask templates; no build step.
- **Auth**: `flask-login` with session cookies; role-based (`admin`/`user`). Sensitive administrative mutations are additionally protected by `production_guards.py`.
- **PDF**: `flask-weasyprint` for internship forms and certificates.
- **Excel import**: `openpyxl` with preview/confirm pattern.
- **Production**: Waitress on Windows via `run_prod.py`; Gunicorn on Linux via `wsgi:app`.

## Key Files

| Path | Purpose |
|------|---------|
| `app.py` | Safe Flask facade and supported development entry point |
| `legacy_app.py` | Historical routes/business logic; imported by `app.py`, not a supported startup command |
| `db_migrations.py` | Safe, idempotent SQLite bootstrap/migrations |
| `password_security.py` | Adaptive password hashing + legacy-hash verification |
| `production_guards.py` | Admin mutation guard + HTTP security headers |
| `wsgi.py` | Hardened production WSGI entry point |
| `run_prod.py` | Production startup via Waitress |
| `tests/` | Unit and Flask integration tests |
| `.github/workflows/quality.yml` | Compile + test quality gate |
| `templates/` | Jinja templates |
| `static/` | Vanilla JS/CSS assets |
| `backup.py` / `backup.sh` | Database backup helpers |
| `.env.example` | Environment variable reference |
| `estagios.db` | SQLite database (gitignored) |

## Development Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure a local .env. On a fresh/empty database, set a strong bootstrap password.
cp .env.example .env
# BOOTSTRAP_ADMIN_PASSWORD=<strong-local-password>

# Supported development startup
python app.py

# Production — Windows / Waitress
python run_prod.py

# Production — Linux / Gunicorn
gunicorn -c gunicorn.conf.py wsgi:app

# Quality gate
python -m compileall -q .
python -m unittest discover -s tests -v

# Backup
python backup.py
./backup.sh
```

There are **no default application credentials**. A fresh database requires `BOOTSTRAP_ADMIN_PASSWORD`; optional `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_NAME` customize the first admin account. Remove the bootstrap password from the environment after the first successful initialization.

Never start the application with `python legacy_app.py`. Never reintroduce `admin/admin`, `user/user`, destructive database initialization, or unconditional data-rewrite migrations at process startup.

## Database Safety Rules

- All schema/bootstrap changes belong in `db_migrations.py` and must be idempotent.
- Startup migrations must preserve operational records.
- Never use broad `DELETE FROM ...` statements as part of bootstrap/reset logic.
- Never replay historical data transformations such as blindly rewriting workflow stage 7 to stage 8 on every start.
- Tests must use a temporary database or an explicit test database path; never mutate `estagios.db`.
- A fresh installation may create only the explicitly configured bootstrap admin, not demo users or demo operational data.

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

Resident/Doutorando workflow rules are defined by `PIPELINE_ETAPAS` and `PIPELINE_TRANSICOES`; see `PIPELINE.md` and integration tests before changing transitions.

## Key API Expectations

- Application APIs require authentication unless explicitly public (for example `/health`).
- Administrative configuration mutations under `/api/area-medica`, `/api/mensagens-modelo`, `/api/usuarios` and `/api/limites` must be admin-only.
- Login redirects must remain local; external `next` targets must never be honored.
- CSV responses remain UTF-8 BOM compatible with Microsoft tools.
- Pipeline changes must preserve the invariant that a resident has at most one current pending action.

## Code Conventions

### Python / Flask
- DB access uses `get_db()` and Flask `g`; connections close in teardown.
- `sqlite3.Row` is used for dict-like rows.
- SQLite `lower()` does not correctly normalize accented Portuguese text; use Python normalization/lowercasing where semantic matching requires it.
- New passwords must use `password_security.hash_password`; legacy hashes are read-only compatibility.
- Keep startup/security behavior in the safe facade/modules rather than duplicating it in route code.

### JavaScript
- `apiFetch(url, options)` wraps fetch + JSON parsing + error toasts.
- Main modals use `.open`; `usuarios.html` uses `.active`.
- Update both HTML and JS if changing modal conventions.

## Environment Variables

See `.env.example`. Important variables include:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Required for production session security |
| `BOOTSTRAP_ADMIN_PASSWORD` | Required only when creating the first admin on a fresh/empty DB |
| `BOOTSTRAP_ADMIN_USERNAME` | Optional first-admin username, defaults to `admin` |
| `BOOTSTRAP_ADMIN_NAME` | Optional first-admin display name |
| `ERP_DATABASE` | Optional alternate SQLite path, useful for tests/isolated deployments |
| `PORT` | Server port |
| `WAITRESS_THREADS` | Waitress worker thread count |
| `SMTP_*` | Optional email configuration |

## Before Merging

Run the full quality gate. For changes touching auth, startup, migrations, residents or pipeline behavior, add/extend integration coverage. A green compile alone is not sufficient; the unit/integration suite must also pass.
