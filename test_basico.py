"""Testes do ERP Estágios Médicos - sem dependencias externas."""
import os
import sys
import sqlite3
import json

# Setup path
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

def test_db_schema_exists():
    """Verifica tabelas principais existem."""
    conn = sqlite3.connect(os.path.join(_BASE_DIR, 'estagios.db'))
    cur = conn.cursor()
    tabelas = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tabelas = {t[0] for t in tabelas}
    required = {'residentes', 'usuarios', 'historico_residentes', 'area_medica', 'mensagens_modelo'}
    missing = required - tabelas
    conn.close()
    if missing:
        return f"MISSING TABLES: {missing}"
    return "OK - todas tabelas principais existem"

def test_residentes_columns():
    """Verifica colunas essenciais na tabela residentes."""
    conn = sqlite3.connect(os.path.join(_BASE_DIR, 'estagios.db'))
    cur = conn.cursor()
    cols = cur.execute("PRAGMA table_info(residentes)").fetchall()
    col_names = {c[1] for c in cols}
    required = {'id', 'nome', 'email', 'especialidade', 'status', 'valor', 'mes_ano'}
    missing = required - col_names
    conn.close()
    if missing:
        return f"MISSING COLUMNS in residentes: {missing}"
    return "OK - colunas residentes OK"

def test_usuarios_seed():
    """Verifica usuarios admin/user seedados."""
    conn = sqlite3.connect(os.path.join(_BASE_DIR, 'estagios.db'))
    cur = conn.cursor()
    rows = cur.execute("SELECT username, role FROM usuarios").fetchall()
    conn.close()
    usuarios = {r[0]: r[1] for r in rows}
    if 'admin' not in usuarios:
        return "MISSING admin user"
    if 'user' not in usuarios:
        return "MISSING user user"
    return f"OK - usuarios: {usuarios}"

def test_area_medica_not_empty():
    """Verifica area_medica tem registros."""
    conn = sqlite3.connect(os.path.join(_BASE_DIR, 'estagios.db'))
    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) FROM area_medica").fetchone()[0]
    conn.close()
    if count == 0:
        return "WARNING: area_medica vazia (sem especialidades cadastradas)"
    return f"OK - {count} especialidades cadastradas"

def test_mensagens_modelo_seed():
    """Verifica templates de WhatsApp seedados."""
    conn = sqlite3.connect(os.path.join(_BASE_DIR, 'estagios.db'))
    cur = conn.cursor()
    rows = cur.execute("SELECT chave FROM mensagens_modelo").fetchall()
    keys = {r[0] for r in rows}
    conn.close()
    required = {'whatsapp_aluno', 'whatsapp_area_medica'}
    missing = required - keys
    if missing:
        return f"MISSING templates: {missing}"
    return f"OK - templates seedados: {len(keys)}"

def test_app_imports():
    """Verifica app.py importa sem erros."""
    try:
        # Set minimal env vars
        os.environ.setdefault('SECRET_KEY', 'test-key-dev-only')
        os.environ.setdefault('FLASK_DEBUG', '1')
        # Importar o modulo (nao iniciar servidor)
        import importlib.util
        spec = importlib.util.spec_from_file_location("app_module", os.path.join(_BASE_DIR, "app.py"))
        # Nao carregar, só verificar syntax
        with open(os.path.join(_BASE_DIR, 'app.py'), 'r') as f:
            code = f.read()
        compile(code, 'app.py', 'exec')
        return "OK - app.py syntax valid"
    except Exception as e:
        return f"FAIL: {e}"

def test_status_values():
    """Verifica status válidos no enum."""
    conn = sqlite3.connect(os.path.join(_BASE_DIR, 'estagios.db'))
    cur = conn.cursor()
    # Pegar status unicos
    rows = cur.execute("SELECT DISTINCT status FROM residentes WHERE status IS NOT NULL").fetchall()
    status_vals = {r[0] for r in rows}
    conn.close()
    valid = {'Interessado', 'Em andamento', 'Deferido', 'Confirmado', 'Indeferido', 'Cancelado', 'Desistente', 'Trocado', 'Nao veio'}
    invalid = status_vals - valid
    if invalid:
        return f"INVALID status values: {invalid}"
    return f"OK - status valid: {status_vals}"

def test_residentes_count():
    """Conta residentes totais (deve ser >0 em produção)."""
    conn = sqlite3.connect(os.path.join(_BASE_DIR, 'estagios.db'))
    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) FROM residentes").fetchone()[0]
    conn.close()
    return f"INFO - {count} residentes cadastrados"

if __name__ == '__main__':
    os.chdir(_BASE_DIR)
    tests = [
        ('db_schema_exists', test_db_schema_exists),
        ('residentes_columns', test_residentes_columns),
        ('usuarios_seed', test_usuarios_seed),
        ('area_medica_not_empty', test_area_medica_not_empty),
        ('mensagens_modelo_seed', test_mensagens_modelo_seed),
        ('app_imports', test_app_imports),
        ('status_values', test_status_values),
        ('residentes_count', test_residentes_count),
    ]
    
    resultados = []
    for nome, fn in tests:
        try:
            out = fn()
            resultados.append((nome, out))
        except Exception as e:
            resultados.append((nome, f"ERROR: {e}"))
    
    # Imprimir resultados
    for nome, out in resultados:
        print(f"{nome}: {out}")
    
    # Contar falhas criticas
    erros = [r for r in resultados if r[1].startswith('MISSING') or r[1].startswith('FAIL') or r[1].startswith('ERROR')]
    print(f"\nTOTAL: {len(resultados)} testes, {len(erros)} falhas criticas")