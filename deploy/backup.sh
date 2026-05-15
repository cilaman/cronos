#!/usr/bin/env bash
# Tarball /opt/cronos/data into /var/backups/cronos/, keep the last 14.
#
# Designed to be invoked by deploy/cronos-backup.service (runs as the cronos
# user). Override BACKUP_DIR or RETENTION via env when testing locally.

set -euo pipefail

SRC="${CRONOS_DATA_DIR:-/opt/cronos/data}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/cronos}"
RETENTION="${RETENTION:-14}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="${BACKUP_DIR}/cronos-data-${stamp}.tar.gz"

mkdir -p "${BACKUP_DIR}"

# --warning=no-file-changed: tasks may be written mid-snapshot; that's fine,
# the next run will pick up the new state.
tar --warning=no-file-changed -czf "${out}" -C "$(dirname "${SRC}")" "$(basename "${SRC}")"

# Prune old backups beyond the retention window.
find "${BACKUP_DIR}" -maxdepth 1 -name 'cronos-data-*.tar.gz' -type f \
  -printf '%T@ %p\n' \
  | sort -nr \
  | awk -v keep="${RETENTION}" 'NR>keep {print $2}' \
  | xargs -r rm -f

echo "Wrote ${out}"
