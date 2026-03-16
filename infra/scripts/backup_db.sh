#!/usr/bin/env bash
# backup_db.sh — Backup do PostgreSQL com timestamp.
# Uso: ./backup_db.sh
# Variáveis de ambiente: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, BACKUP_DIR

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-vms}"
DB_USER="${POSTGRES_USER:-vms}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="${BACKUP_DIR}/vms_${TIMESTAMP}.sql.gz"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Iniciando backup: ${FILENAME}"

PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-password \
    --format=plain \
    | gzip -9 > "${FILENAME}"

SIZE=$(du -sh "${FILENAME}" | cut -f1)
echo "[$(date -Iseconds)] Backup concluído: ${FILENAME} (${SIZE})"

# Remove backups mais antigos que KEEP_DAYS dias
find "${BACKUP_DIR}" -name "vms_*.sql.gz" -mtime "+${KEEP_DAYS}" -delete
echo "[$(date -Iseconds)] Limpeza: backups com mais de ${KEEP_DAYS} dias removidos"
