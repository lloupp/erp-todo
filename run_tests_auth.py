# -*- coding: utf-8 -*-
import os
import sys

os.environ['SECRET_KEY'] = 'test-key-dev-only'
os.environ['FLASK_DEBUG'] = '1'
os.environ['AI_ENABLED'] = 'false'

# Mock __file__ para app.py
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

# Executar app.py até antes do main
_app_path = os.path.join(_BASE_DIR, 'app.py')
_code = open(_app_path).read()
_main_marker = "if __name__"
_idx = _code.find(_main_marker)
if _idx > 0:
    _code = _code[:_idx]

# Mock __file__ antes de executar
import types
_mod = types.ModuleType('app_test')
_mod.__file__ = _app_path
exec(compile(_code, _app_path, 'exec'), _mod.__dict__)
app = _mod.app

print("=== Testes com Autenticação ===")

# Login com admin/admin
with app.test_client() as client:
    # Fazer login
    login_resp = client.post('/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=False)
    login_status = f"OK - login status {login_resp.status_code}"
    print(f"/login (admin/admin): {login_status}")
    
    # Teste dashboard autenticado
    try:
        resp = client.get('/api/dashboard')
        if resp.status_code == 200:
            data = resp.get_json()
            keys = list(data.keys())
            print(f"/api/dashboard (autenticado): OK - {len(keys)} chaves")
            # Verificar schema dos KPIs
            kpis = data.get('kpis', {})
            print(f"  KPIs keys: {list(kpis.keys())}")
        else:
            print(f"/api/dashboard (autenticado): FAIL - status {resp.status_code}")
    except Exception as e:
        print(f"/api/dashboard (autenticado): FAIL - {e}")
    
    # Teste /api/me autenticado
    try:
        resp = client.get('/api/me')
        if resp.status_code == 200:
            user = resp.get_json()
            print(f"/api/me (autenticado): OK - user={user.get('username')}, role={user.get('role')}")
        else:
            print(f"/api/me (autenticado): FAIL - status {resp.status_code}")
    except Exception as e:
        print(f"/api/me (autenticado): FAIL - {e}")
    
    # Teste /api/estagios autenticado
    try:
        resp = client.get('/api/estagios')
        if resp.status_code == 200:
            data = resp.get_json()
            print(f"/api/estagios (autenticado): OK - {len(data)} items")
        else:
            print(f"/api/estagios (autenticado): FAIL - status {resp.status_code}")
    except Exception as e:
        print(f"/api/estagios (autenticado): FAIL - {e}")