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

print("=== Teste Residentes Module ===")

with app.test_client() as client:
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    
    # Listar residentes
    resp = client.get('/api/residentes')
    print(f"GET /api/residentes: {resp.status_code}")
    
    # Buscar especialidades via filtro residentes
    resp = client.get('/api/residentes?busca=cardio')
    if resp.status_code == 200:
        data = resp.get_json()
        print(f"GET /api/residentes?busca=cardio: {len(data)} items")
    
    # Testar importação EXCEL (preview sem file)
    resp = client.post('/api/residentes/importar-excel', json={'confirmar': 0})
    print(f"POST /api/residentes/importar-excel (sem file): {resp.status_code}")
    
    # Testar avançar status (com residente inexistente)
    resp = client.post('/api/residentes/999/avancar', json={'status': 'Deferido'})
    print(f"POST /api/residentes/999/avancar: {resp.status_code}")
    
    # Testar mensagens modelo
    resp = client.get('/api/mensagens-modelo')
    if resp.status_code == 200:
        data = resp.get_json()
        print(f"GET /api/mensagens-modelo: {len(data)} templates")