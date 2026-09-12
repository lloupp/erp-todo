"""Safe application facade.

The historical Flask implementation lives in ``legacy_app.py`` so its old
``if __name__ == '__main__'`` migration block can no longer execute from the
supported ``python app.py`` entry point. Runtime startup is centralized here
and in ``wsgi.py`` through the idempotent database bootstrap.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Direct execution is a development path. Preserve the legacy module's
# ephemeral-secret behavior when no SECRET_KEY was supplied, but never create
# default database credentials.
if __name__ == '__main__' and not os.environ.get('SECRET_KEY'):
    os.environ.setdefault('FLASK_DEBUG', '1')

import legacy_app as _legacy
from password_security import hash_password, verify_password

# Route functions are defined in legacy_app and resolve globals in that module,
# so patch the password helpers there before serving any requests.
_legacy.hash_password = hash_password
_legacy.verify_password = verify_password

# Re-export the public application API to preserve imports such as
# ``from app import app, get_db, PIPELINE_ETAPAS`` used by scripts/tests.
for _name in dir(_legacy):
    if not _name.startswith('_'):
        globals()[_name] = getattr(_legacy, _name)

# Ensure the secure helpers themselves remain the facade's public versions.
hash_password = hash_password
verify_password = verify_password
app = _legacy.app

# Tests and alternate deployments can point the application at another SQLite
# file without mutating the repository working tree.
if os.environ.get('ERP_DATABASE'):
    app.config['DATABASE'] = os.environ['ERP_DATABASE']


def bootstrap_database() -> None:
    """Apply the production-safe, idempotent schema/bootstrap routine."""
    from db_migrations import ensure_database

    ensure_database(
        app.config['DATABASE'],
        hash_password=hash_password,
        message_seed=_legacy.MENSAGENS_MODELO_SEED,
        pipeline_etapas=_legacy.PIPELINE_ETAPAS,
        data_dir=os.path.join(BASE_DIR, 'data'),
    )


if __name__ == '__main__':
    bootstrap_database()
    app.run(
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', '5000')),
        debug=os.environ.get('FLASK_DEBUG') == '1',
    )
