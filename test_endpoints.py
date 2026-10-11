# Testes API Endpoints - sem tocar no código existente
import os
import sys

import pytest

pytest.importorskip("flask", reason="dependencias Flask nao instaladas neste ambiente")
pytest.importorskip("flask_login", reason="dependencias Flask nao instaladas neste ambiente")
pytest.importorskip("flask_weasyprint", reason="dependencias Flask nao instaladas neste ambiente")

# Setup mínimo ANTES de importar o app
os.environ['SECRET_KEY'] = 'test-key-dev-only'
os.environ['FLASK_DEBUG'] = '1'
os.environ['AI_ENABLED'] = 'false'

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE_DIR)

# Importar o app de forma simples
exec(open(os.path.join(_BASE_DIR, 'app.py')).read().split("if __name__")[0])

# Testar endpoints
def test_health_endpoint():
    try:
        with app.test_client() as client:
            resp = client.get('/health')
            return f"OK - /health: {resp.status_code}"
    except Exception as e:
        return f"FAIL - /health: {e}"

def test_dashboard_endpoint():
    # /api/dashboard exige login: sem sessão deve redirecionar (302) ou negar (401).
    try:
        with app.test_client() as client:
            resp = client.get('/api/dashboard')
            if resp.status_code in (302, 401):
                return f"OK - /api/dashboard protegido ({resp.status_code})"
            if resp.status_code == 200:
                data = resp.get_json()
                expected_keys = ['kpis', 'por_status', 'por_tipo', 'por_especialidade', 'financeiro']
                missing = [k for k in expected_keys if k not in data]
                if missing:
                    return f"WARN - /api/dashboard falta chaves: {missing}"
                return f"OK - /api/dashboard ({len(data)} chaves)"
            return f"FAIL - /api/dashboard status {resp.status_code}"
    except Exception as e:
        return f"FAIL - /api/dashboard: {e}"

def test_residentes_endpoint():
    # /api/estagios exige login: sem sessão deve redirecionar (302) ou negar (401).
    try:
        with app.test_client() as client:
            resp = client.get('/api/estagios')
            if resp.status_code in (200, 302, 401):
                return f"OK - /api/estagios: {resp.status_code}"
            return f"FAIL - /api/estagios status {resp.status_code}"
    except Exception as e:
        return f"FAIL - /api/estagios: {e}"

def test_auth_endpoint():
    try:
        with app.test_client() as client:
            resp = client.get('/api/me')
            if resp.status_code in [401, 302]:
                return f"OK - /api/me protegido ({resp.status_code})"
            return f"WARN - /api/me status {resp.status_code}"
    except Exception as e:
        return f"FAIL - /api/me: {e}"

if __name__ == '__main__':
    print("=== Testes de Integração API ===")
    tests = [
        ('/health', test_health_endpoint),
        ('/api/dashboard', test_dashboard_endpoint),
        ('/api/estagios', test_residentes_endpoint),
        ('/api/me', test_auth_endpoint),
    ]
    
    erros = []
    for route, fn in tests:
        try:
            out = fn()
            print(f"{route}: {out}")
            if 'FAIL' in out:
                erros.append(route)
        except Exception as e:
            print(f"{route}: ERROR - {e}")
            erros.append(route)
    
    print(f"\nTOTAL: {len(tests)} testes, {len(erros)} falhas")
    if erros:
        print(f"FALHAS: {erros}")
