#!/usr/bin/env sh
set -eu

: "${DATABASE_URL_SYNC:?DATABASE_URL_SYNC is required}"
: "${BACKUP_FILE:?BACKUP_FILE is required}"

umask 077
pg_dump --format=custom --no-owner --no-acl --file="$BACKUP_FILE" "$DATABASE_URL_SYNC"
pg_restore --list "$BACKUP_FILE" >/dev/null
echo "Backup created and archive verified: $BACKUP_FILE"
