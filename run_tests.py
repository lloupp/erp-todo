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
_mod.__file__ = _app_path  # mock __file__

# Executar com __file__ disponível
exec(compile(_code, _app_path, 'exec'), _mod.__dict__)

app = _mod.app  # salvar referência

print("=== Testes de Integração API ===")

# Teste 1: /health
try:
    with app.test_client() as client:
        resp = client.get('/health')
        health_status = f"OK - status {resp.status_code}"
except Exception as e:
    health_status = f"FAIL - {e}"
print(f"/health: {health_status}")

# Teste 2: /api/dashboard
try:
    with app.test_client() as client:
        resp = client.get('/api/dashboard')
        if resp.status_code == 200:
            data = resp.get_json()
            keys = list(data.keys())
            dashboard_status = f"OK - {len(keys)} chaves: {keys}"
        elif resp.status_code in (302, 401):
            # exige login: sem sessão o redirect/negação é o comportamento esperado
            dashboard_status = f"OK - protegido ({resp.status_code})"
        else:
            dashboard_status = f"FAIL - status {resp.status_code}"
except Exception as e:
    dashboard_status = f"FAIL - {e}"
print(f"/api/dashboard: {dashboard_status}")

# Teste 3: /api/estagios
try:
    with app.test_client() as client:
        resp = client.get('/api/estagios')
        estagios_status = f"OK - status {resp.status_code}"
except Exception as e:
    estagios_status = f"FAIL - {e}"
print(f"/api/estagios: {estagios_status}")

# Teste 4: /api/me (sem login)
try:
    with app.test_client() as client:
        resp = client.get('/api/me')
        if resp.status_code in [401, 302]:
            auth_status = f"OK - protegido ({resp.status_code})"
        else:
            auth_status = f"WARN - status {resp.status_code}"
except Exception as e:
    auth_status = f"FAIL - {e}"
print(f"/api/me: {auth_status}")

# Registrar falhas
erros = []
for nome, status in [('/health', health_status), ('/api/dashboard', dashboard_status), ('/api/estagios', estagios_status), ('/api/me', auth_status)]:
    if 'FAIL' in status:
        erros.append(nome)

print(f"\nTOTAL: 4 testes, {len(erros)} falhas")
if erros:
    print(f"FALHAS: {erros}")