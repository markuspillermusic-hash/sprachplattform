#!/bin/sh
set -eu

APP_DIR=/opt/sprachplattform
BACKUP_DIR=/var/backups/sprachplattform
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TEMP_FILE="${BACKUP_DIR}/.postgres-${TIMESTAMP}.dump.tmp"
BACKUP_FILE="${BACKUP_DIR}/postgres-${TIMESTAMP}.dump"

install -d -m 0700 "$BACKUP_DIR"
trap 'rm -f "$TEMP_FILE"' EXIT HUP INT TERM

cd "$APP_DIR"
/usr/bin/docker compose --env-file .env exec -T db \
    sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$TEMP_FILE"

test -s "$TEMP_FILE"
chmod 0600 "$TEMP_FILE"
mv "$TEMP_FILE" "$BACKUP_FILE"
trap - EXIT HUP INT TERM

/usr/bin/docker compose --env-file .env exec -T db \
    pg_restore --list < "$BACKUP_FILE" > /dev/null

find "$BACKUP_DIR" -type f -name 'postgres-*.dump' -mtime +14 -delete
