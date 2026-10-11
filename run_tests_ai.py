# -*- coding: utf-8 -*-
import os
import sys

os.environ['SECRET_KEY'] = 'test-key-dev-only'
os.environ['FLASK_DEBUG'] = '1'
os.environ['AI_ENABLED'] = 'false'

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

# Executar app.py até antes do main
_app_path = os.path.join(_BASE_DIR, 'app.py')
_code = open(_app_path).read()
_idx = _code.find("if __name__")
if _idx > 0:
    _code = _code[:_idx]

import types
_mod = types.ModuleType('app_test')
_mod.__file__ = _app_path
exec(compile(_code, _app_path, 'exec'), _mod.__dict__)
app = _mod.app

print("=== Teste AI Module ===")

with app.test_client() as client:
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    
    # Testar /api/ai/chat com AI desativado
    resp = client.post('/api/ai/chat', json={'message': 'teste'})
    print(f"/api/ai/chat (AI_ENABLED=false): {resp.status_code}")
    if resp.status_code == 200:
        print(f"  Response: {resp.get_json()}")
    
    # Testar /api/ai/insights
    resp = client.get('/api/ai/insights')
    print(f"/api/ai/insights: {resp.status_code}")

print("\n=== Teste Pipeline_acoes (tabela já existe) ===")
with app.app_context():
    conn = _mod.get_db()
    # Verificar schema completo
    cols = conn.execute("PRAGMA table_info(pipeline_acoes)").fetchall()
    print(f"Colunas de pipeline_acoes: {[c[1] for c in cols]}")
    
    # Testar query que seria usada no dashboard pipeline
    count = conn.execute("SELECT COUNT(*) FROM pipeline_acoes").fetchone()[0]
    print(f"pipeline_acoes count: {count}")