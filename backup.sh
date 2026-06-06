#!/bin/bash
# Backup diário do banco SQLite com retenção de 7 dias.
# Crontab sugerido (todo dia às 2h): 0 2 * * * /path/to/erp-todo/backup.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB="$SCRIPT_DIR/estagios.db"
BACKUP_DIR="$SCRIPT_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/estagios_$DATE.db"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB" ]; then
    echo "Banco nao encontrado: $DB"
    exit 1
fi

cp "$DB" "$DEST"
echo "Backup criado: $DEST"

# Apagar backups com mais de 7 dias
find "$BACKUP_DIR" -name "estagios_*.db" -mtime +7 -delete
echo "Backups antigos removidos."
