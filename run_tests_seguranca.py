# -*- coding: utf-8 -*-
import os
import sys

os.environ['SECRET_KEY'] = 'test-key-dev-only'
os.environ['FLASK_DEBUG'] = '1'

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

print("=== Teste Segurança ====")

with app.test_client() as client:
    # Teste CSRF ausente - testar POST sem token
    # Tentativa de criar residente sem autenticação
    resp = client.post('/api/estagios', json={'nome': 'Teste Hackeado'})
    print(f"POST /api/estagios sem auth: {resp.status_code} (esperado 302/401)")
    
    # Login como user comum
    client.post('/login', data={'username': 'user', 'password': 'user'})
    
    # Teste user tentando acessar rota admin
    resp = client.get('/api/usuarios')
    print(f"GET /api/usuarios (role=user): {resp.status_code} (esperado 403)")
    
    # Logout e login como admin
    client.get('/logout')
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    
    # Teste admin acessa usuarios
    resp = client.get('/api/usuarios')
    print(f"GET /api/usuarios (role=admin): {resp.status_code} (esperado 200)")
    
    # Teste WeasyPrint fallback (PDF) - sem estagios no BD
    resp = client.get('/api/estagios/999/pdf')
    print(f"GET /api/estagios/999/pdf (id inexistente): {resp.status_code}")