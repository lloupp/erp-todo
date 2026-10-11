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

print("=== Teste Parser _melhor_match_especialidade ===")

# Teste CORRETO: passar lista já normalizada
with app.app_context():
    conn = _mod.get_db()
    canonicos = [r['especialidade'] for r in conn.execute("SELECT DISTINCT especialidade FROM area_medica LIMIT 10").fetchall()]
    canonicos_norm = [_mod._normalizar_texto_especialidade(c) for c in canonicos]
    
    print(f"Canonicos (raw): {canonicos[:5]}...")
    print(f"Canonicos (norm): {canonicos_norm[:5]}...")
    
    # Testar com 'cardio' vs 'cardiologia'
    result = _mod._melhor_match_especialidade('cardio', canonicos_norm)
    print(f"_melhor_match_especialidade('cardio', canonicos_norm): index={result}, value={canonicos[result] if result else result}")
    
    # Testar com 'cardiologia' (mais preciso)
    result2 = _mod._melhor_match_especialidade('cardiologia', canonicos_norm)
    print(f"_melhor_match_especialidade('cardiologia', canonicos_norm): index={result2}, value={canonicos[result2] if result2 else result2}")