from pathlib import Path

path = Path('legacy_app.py')
text = path.read_text(encoding='utf-8')

start_marker = '\ndef hash_password(password):'
auth_marker = '\n\n# ── Auth routes'
if text.count(start_marker) != 1:
    raise SystemExit('legacy password/init block not found exactly once')
start = text.index(start_marker)
end = text.index(auth_marker, start)
text = text[:start] + text[end:]

run_marker = '\n\n# ── Run ───────────────────────────────────────────────────────\n'
if text.count(run_marker) != 1:
    raise SystemExit('legacy run block not found exactly once')
text = text[:text.index(run_marker)] + '\n'

for forbidden in (
    'def init_db():',
    'UPDATE estagios SET etapa=8 WHERE etapa=7',
    "hash_password('admin')",
    "hash_password('user')",
    "app.run(host='0.0.0.0', port=5000, debug=True)",
):
    if forbidden in text:
        raise SystemExit(f'forbidden pattern remains: {forbidden}')

path.write_text(text, encoding='utf-8')
print('legacy startup code removed')
