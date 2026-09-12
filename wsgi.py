"""Hardened WSGI entry point shared by Waitress and Gunicorn."""

import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

import app as app_module
from db_migrations import ensure_database
from password_security import hash_password, verify_password
from production_guards import install_production_guards


# Keep existing password hashes readable while every new/changed password uses
# the adaptive KDF from password_security.
app_module.hash_password = hash_password
app_module.verify_password = verify_password
app = app_module.app

ensure_database(
    app.config['DATABASE'],
    hash_password=hash_password,
    message_seed=app_module.MENSAGENS_MODELO_SEED,
    pipeline_etapas=app_module.PIPELINE_ETAPAS,
    data_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'),
)
install_production_guards(app)
