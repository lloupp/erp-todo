# Repository Guidelines

## Project Overview
Medical internship management system for Santa Casa / UFCSPA built with Flask + SQLite. Tracks internships across three types (Observership, Obrigatório, Optativo) through a 7-stage workflow with filtering, history tracking, and CSV export.

## Architecture & Data Flow
- **Backend**: Single-file Flask app (`app.py`) with SQLite database
- **Frontend**: Vanilla JS (`static/js/app.js`) + CSS (`static/css/style.css`) served via Flask templates
- **API**: RESTful JSON endpoints under `/api/*`
- **Database**: SQLite with three tables (`tipo_estagio`, `estagios`, `historico_etapas`)
- **State**: Server-side persistence; client caches filter options and renders from API responses

## Key Directories
| Path | Purpose |
|------|---------|
| `app.py` | Flask application, routes, DB initialization, business logic |
| `templates/` | Jinja2 templates (only `index.html`) |
| `static/css/` | Stylesheets (`style.css`) |
| `static/js/` | Client-side logic (`app.js`) |
| `estagios.db` | SQLite database (auto-created on first run) |

## Development Commands
```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run (debug mode, port 5000)
python app.py

# Access
# Local: http://localhost:5000
# Network: http://<IP>:5000
```

## Code Conventions & Common Patterns

### Python (Flask)
- **DB access**: `get_db()` returns connection from Flask `g`; `@app.teardown_appcontext` closes it
- **Row factory**: `sqlite3.Row` for dict-like row access
- **Routes**: RESTful, consistent naming (`/api/estagios`, `/api/estagios/<id>/avancar`)
- **Error handling**: Implicit via Flask; JSON responses with appropriate HTTP codes
- **Constants**: Module-level dicts for workflow (`TIPO_ESTAGIO`, `ETAPAS_OBS`, `ETAPAS_OBR_OPT`, `ETAPA_COLORS`)

### JavaScript (Vanilla ES6)
- **Module pattern**: IIFE-like `init()` + global functions attached to `window` implicitly
- **API wrapper**: `apiFetch(url, options)` handles fetch + JSON parsing + error toasts
- **State**: Module-level `let` variables (`currentEstagioId`, `tipos`, `debounceTimer`)
- **DOM**: Direct `document.getElementById` / `querySelector`; no framework
- **Rendering**: `renderEstagios(data)` builds HTML strings via template literals
- **Modals**: CSS class `.active` on overlay elements; `openModal()` / `closeModal()` helpers
- **Debounce**: `debounceTimer` for search input (300ms)

### CSS
- **Custom properties**: `--color-primary`, `--color-border`, etc. defined in `:root`
- **Utility classes**: `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`, `.btn-sm`
- **Responsive**: Mobile-first with `@media (max-width: 900px)` for sidebar collapse
- **Badges**: `.badge-tipo` + stage-specific (`.badge-obs`, `.badge-obr`, `.badge-opt`)

### Database Schema
```sql
tipo_estagio(id, nome)                    -- 1=Observership, 2=Obrigatorio, 3=Optativo
estagios(id, tipo_id, mes_ano, semana, nome, especialidade, cracha, valor, termino, email, telefone, observacao, documentos, envio_certificado, etapa, created_at, updated_at)
historico_etapas(id, estagio_id, etapa, observacao, responsavel, ts)
```

### Workflow Stages
| Stage | Observership | Obrigatório/Optativo |
|-------|--------------|---------------------|
| 0 | — | Verificação de vaga |
| 1 | Venda realizada | Venda realizada |
| 2 | Pagamento confirmado | Pagamento confirmado |
| 3 | Docs enviados | Docs enviados |
| 4 | Docs validados | Docs validados |
| 5 | Vaga confirmada | Vaga confirmada |
| 6 | Orientações enviadas | Orientações enviadas |
| 7 | Concluído | Concluído |

## Important Files
| File | Role |
|------|------|
| `app.py` | Entry point, all routes, DB init, constants |
| `templates/index.html` | Single-page layout, modals, filter sidebar |
| `static/js/app.js` | All client logic: API, rendering, modals, filters, CSV export |
| `static/css/style.css` | Complete styling including responsive rules |
| `requirements.txt` | `flask==3.1.1` |
| `estagios.db` | SQLite database (gitignored in practice) |

## Runtime/Tooling Preferences
- **Python**: 3.10+ (Flask 3.1.1)
- **Package manager**: pip with virtualenv
- **Database**: SQLite (file-based, zero-config)
- **No build step**: Static assets served directly
- **No linting/formatting configured** — follow existing style

## Testing & QA
- **No test suite present** — manual testing via browser
- **Smoke test**: Run `python app.py`, verify:
  - Page loads at `localhost:5000`
  - Create/edit/delete internships via modals
  - Filters (type, specialty, stage, month, search) work
  - Stage advance logs to history modal
  - CSV export downloads file
- **Database**: Auto-seeds `tipo_estagio` and sample data on first run via `init_db()`