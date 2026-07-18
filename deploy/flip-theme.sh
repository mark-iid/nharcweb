#!/usr/bin/env bash
#
# Instantly switch the LIVE site between the two themes, with no rebuild.
# Both themes are kept as ready-built snapshots on the server:
#   /var/www/nharc-signal   <- new dark "signal" theme (default)
#   /var/www/nharc-classic  <- previous light theme (fallback)
#
# Usage:  ./deploy/flip-theme.sh signal      # new dark theme
#         ./deploy/flip-theme.sh classic     # old light theme
set -euo pipefail

VARIANT="${1:-}"
DEPLOY_HOST="${DEPLOY_HOST:-newweb.nharc.org}"
DEPLOY_USER="${DEPLOY_USER:-mark}"
DEPLOY_PATH="${DEPLOY_PATH:-/var/www/nharc}"

case "$VARIANT" in
  signal|classic) ;;
  *) echo "usage: $0 <signal|classic>"; exit 1 ;;
esac

ssh "${DEPLOY_USER}@${DEPLOY_HOST}" \
  "rsync -a --delete ${DEPLOY_PATH}-${VARIANT}/ ${DEPLOY_PATH}/"

echo "Live site flipped to '${VARIANT}'  ->  https://${DEPLOY_HOST}/"
