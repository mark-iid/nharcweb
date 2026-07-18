#!/usr/bin/env bash
#
# Build the site and deploy it to the staging server over SSH.
# Usage:  ./deploy/deploy.sh
#
# Requires: node/npm locally, ssh access to the server as $DEPLOY_USER.
set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:-newweb.nharc.org}"
DEPLOY_USER="${DEPLOY_USER:-mark}"
DEPLOY_PATH="${DEPLOY_PATH:-/var/www/nharc}"

cd "$(dirname "$0")/.."

echo "==> Building site"
npm run build

echo "==> Deploying dist/ to ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}"
rsync -az --delete \
  --exclude='.well-known' \
  dist/ "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/"

echo "==> Done. https://${DEPLOY_HOST}/"
