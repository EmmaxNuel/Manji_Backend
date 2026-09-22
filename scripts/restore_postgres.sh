#!/bin/bash
set -euo pipefail

BACKUP_DIR="/backups"
DB_NAME="${POSTGRES_DB:-manji}"
DB_USER="${POSTGRES_USER:-manji}"
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file.dump>"
    echo "Available backups:"
    ls -la "${BACKUP_DIR}"/manji_*.dump 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file ${BACKUP_DIR}/${BACKUP_FILE} not found"
    exit 1
fi

echo "WARNING: This will restore the database from ${BACKUP_FILE}"
echo "This operation will DESTROY all current data in ${DB_NAME}"
read -p "Are you sure? Type 'yes' to confirm: " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo "[$(date)] Restoring ${DB_NAME} from ${BACKUP_FILE}..."

pg_restore -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    --no-password --verbose --clean --if-exists \
    "${BACKUP_DIR}/${BACKUP_FILE}"

if [ $? -eq 0 ]; then
    echo "[$(date)] Restore completed successfully"
else
    echo "[$(date)] ERROR: Restore failed"
    exit 1
fi