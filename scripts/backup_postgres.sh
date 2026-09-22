#!/bin/bash
set -euo pipefail

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="${POSTGRES_DB:-manji}"
DB_USER="${POSTGRES_USER:-manji}"
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting backup of ${DB_NAME}..."

pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    --no-password --verbose --format=custom --compress=9 \
    --file="${BACKUP_DIR}/manji_${DATE}.dump"

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup completed: manji_${DATE}.dump"
    
    find "${BACKUP_DIR}" -name "manji_*.dump" -type f -mtime +${RETENTION_DAYS} -delete
    echo "[$(date)] Cleaned up backups older than ${RETENTION_DAYS} days"
else
    echo "[$(date)] ERROR: Backup failed"
    exit 1
fi