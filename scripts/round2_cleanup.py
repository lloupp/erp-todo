from pathlib import Path

path = Path('app.py')
text = path.read_text(encoding='utf-8')

anchor = 'import ai_pool  # pool dedicado de threads para chamadas de IA (isolamento do Waitress)\n'
secure_import = 'from password_security import hash_password, verify_password\n'
if secure_import not in text:
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor + '\n' + secure_import, 1)

start_marker = '\ndef hash_password(password):'
auth_marker = '\n\n# ── Auth routes'
assert text.count(start_marker) == 1
start = text.index(start_marker)
end = text.index(auth_marker, start)
text = text[:start] + text[end:]

run_marker = '\n\n# ── Run ───────────────────────────────────────────────────────\n'
assert text.count(run_marker) == 1
run_start = text.index(run_marker)
text = text[:run_start] + '''\n\n# ── Startup guard ─────────────────────────────────────────────\n# app.py defines routes and business logic only. Use a supported entry point so\n# database bootstrap and migrations always pass through db_migrations.py.\nif __name__ == '__main__':\n    raise SystemExit(\n        'Execucao direta de app.py foi desativada. Use "python run_dev.py" '\n        'em desenvolvimento ou "python run_prod.py" em producao.'\n    )\n'''

assert 'def init_db():' not in text
assert text.count("if __name__ == '__main__':") == 1
path.write_text(text, encoding='utf-8')
print('app.py cleanup applied')
