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
_main_marker = "if __name__"
_idx = _code.find(_main_marker)
if _idx > 0:
    _code = _code[:_idx]

import types
_mod = types.ModuleType('app_test')
_mod.__file__ = _app_path
exec(compile(_code, _app_path, 'exec'), _mod.__dict__)
app = _mod.app

print("=== Testes Parser e Context ===")

# Teste 1: Parser _parse_mes_texto (funciona sem contexto)
try:
    result = _mod._parse_mes_texto('janeiro 2026')
    print(f"_parse_mes_texto('janeiro 2026'): {result}")
    assert result == '2026-01', f"Esperado 2026-01, got {result}"
except Exception as e:
    print(f"_parse_mes_texto: FAIL - {e}")

# Testes que precisam de application context
with app.app_context():
    # Teste 2: Parser _melhor_match_especialidade
    try:
        conn = _mod.get_db()
        esps = [r['especialidade'] for r in conn.execute("SELECT DISTINCT especialidade FROM area_medica LIMIT 5").fetchall()]
        if esps:
            result = _mod._melhor_match_especialidade('cardio', esps)
            print(f"_melhor_match_especialidade('cardio', ...): {result}")
    except Exception as e:
        print(f"_melhor_match_especialidade: FAIL - {e}")
    
    # Teste 3: Verificar AI_ENABLED via variável
    ai_enabled = os.environ.get('AI_ENABLED', 'false') == 'true'
    print(f"AI_ENABLED: {ai_enabled}")

# Testes HTTP
with app.test_client() as client:
    # Login primeiro
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    
    resp = client.get('/api/tipos')
    if resp.status_code == 200:
        tipos = resp.get_json()
        print(f"/api/tipos (autenticado): OK - {len(tipos)} tipos")
    else:
        print(f"/api/tipos (autenticado): FAIL - status {resp.status_code}")
    
    resp = client.get('/api/especialidades')
    if resp.status_code == 200:
        esps = resp.get_json()
        print(f"/api/especialidades (autenticado): OK - {len(esps)} especialidades")
    else:
        print(f"/api/especialidades (autenticado): FAIL - status {resp.status_code}")