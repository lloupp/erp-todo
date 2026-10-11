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

print("=== Teste Relatórios e Importação ===")

with app.test_client() as client:
    # Login
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    
    # Teste /api/relatorios/exportar (egressos)
    resp = client.get('/api/relatorios/exportar?relatorio=egressos')
    print(f"/api/relatorios/exportar?relatorio=egressos: status={resp.status_code}, len={len(resp.get_data())}")
    
    # Teste /api/relatorios/exportar (pendentes)
    resp = client.get('/api/relatorios/exportar?relatorio=pendentes')
    print(f"/api/relatorios/exportar?relatorio=pendentes: status={resp.status_code}, len={len(resp.get_data())}")
    
    # Teste /api/pendencias (usado no banner)
    resp = client.get('/api/pendencias')
    if resp.status_code == 200:
        pend = resp.get_json()
        print(f"/api/pendencias: OK - keys={list(pend.keys())}")
    else:
        print(f"/api/pendencias: FAIL - status {resp.status_code}")
    
    # Teste /api/meses
    resp = client.get('/api/meses')
    print(f"/api/meses: status={resp.status_code}")