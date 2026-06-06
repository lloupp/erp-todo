import shutil, os, glob
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'estagios.db')
BACKUP_DIR = os.path.join(BASE, 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)

if not os.path.exists(DB):
    raise SystemExit(f'Banco nao encontrado: {DB}')

dest = os.path.join(BACKUP_DIR, f'estagios_{datetime.now():%Y%m%d_%H%M%S}.db')
shutil.copy2(DB, dest)
print(f'Backup criado: {dest}')

cutoff = datetime.now() - timedelta(days=7)
for f in glob.glob(os.path.join(BACKUP_DIR, 'estagios_*.db')):
    if datetime.fromtimestamp(os.path.getmtime(f)) < cutoff:
        os.remove(f)
        print(f'Removido: {f}')
