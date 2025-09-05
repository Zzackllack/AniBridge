#!/usr/bin/env bash
set -euo pipefail

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
CHOWN_RECURSIVE="${CHOWN_RECURSIVE:-true}"

echo "[entrypoint] Starting with PUID=${PUID} PGID=${PGID}"

# Create or adjust group
if getent group appgroup >/dev/null 2>&1; then
  existing_gid=$(getent group appgroup | cut -d: -f3 || true)
  if [ "${existing_gid}" != "${PGID}" ]; then
    if getent group "${PGID}" >/dev/null 2>&1; then
      echo "[entrypoint] A group with GID ${PGID} exists; reusing it for appuser"
      group_name=$(getent group "${PGID}" | cut -d: -f1)
      usermod -g "${PGID}" appuser || true
      adduser appuser "${group_name}" || true
    else
      groupmod -o -g "${PGID}" appgroup || true
    fi
  fi
else
  if getent group "${PGID}" >/dev/null 2>&1; then
    group_name=$(getent group "${PGID}" | cut -d: -f1)
    adduser appuser "${group_name}" || true
  else
    addgroup --system --gid "${PGID}" appgroup || true
  fi
fi

# Create or adjust user
if id -u appuser >/dev/null 2>&1; then
  existing_uid=$(id -u appuser)
  if [ "${existing_uid}" != "${PUID}" ]; then
    usermod -o -u "${PUID}" appuser || true
  fi
else
  adduser --system --uid "${PUID}" --ingroup appgroup appuser || true
fi

# Ensure directories exist
mkdir -p /data || true
mkdir -p /app || true

# Adjust ownership on mounts
if [ "${CHOWN_RECURSIVE,,}" = "true" ]; then
  chown -R "${PUID}:${PGID}" /data 2>/dev/null || true
  chown -R "${PUID}:${PGID}" /app 2>/dev/null || true
else
  chown "${PUID}:${PGID}" /data 2>/dev/null || true
  chown "${PUID}:${PGID}" /app 2>/dev/null || true
fi

echo "[entrypoint] Launching: $* as appuser"
exec gosu appuser:appgroup "$@"

