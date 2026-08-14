#!/usr/bin/env bash
#
# Build the site and deploy it to the staging server over SSH.
# Usage:  ./deploy/deploy.sh
#
# Requires: node/npm locally, ssh access to the server as $DEPLOY_USER.
set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:-nharc.org}"
DEPLOY_USER="${DEPLOY_USER:-mark}"
DEPLOY_PATH="${DEPLOY_PATH:-/var/www/nharc}"

cd "$(dirname "$0")/.."

# Guard: refuse to deploy from a stale tree. Because the deploy below uses
# `rsync --delete`, building from a checkout that's behind origin/main would
# wipe files added since (e.g. images committed through the CMS).
echo "==> Checking local tree is up to date with origin/main"
git fetch -q origin main
if [ -n "$(git rev-list HEAD..origin/main 2>/dev/null)" ]; then
  echo "ERROR: origin/main has commits you don't have locally." >&2
  echo "Run 'git pull' first, or just push and let CI deploy." >&2
  exit 1
fi

echo "==> Building site"
npm run build

echo "==> Deploying dist/ to ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}"
rsync -az --delete \
  --exclude='.well-known' \
  dist/ "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/"

echo "==> Done. https://${DEPLOY_HOST}/"
