#!/usr/bin/env bash
#
# Install the traffic-stats pipeline on the web server:
#   Caddy JSON access log  ->  nightly GoAccess run  ->  /stats (basic auth)
#
# Idempotent — safe to re-run after changing goaccess.conf or the units.
# Usage (on the server):  sudo ./install.sh
#         or from your Mac: ssh mark@nharc.org 'bash -s' < deploy/stats/install.sh
set -euo pipefail

GOACCESS_VERSION=1.9.4
STATS_DIR=/var/www/nharc-stats
OAUTH_ENV=/etc/nharc-oauth.env
RELAY_PATH=/opt/nharc-oauth/oauth-relay.py
STATS_REPO=mark-iid/nharcweb

if [ "$(id -u)" -ne 0 ]; then
  echo "Re-running under sudo..." >&2
  exec sudo -E bash "$0" "$@"
fi

# --- GoAccess -------------------------------------------------------------
# Ubuntu 20.04 is EOL, so deb.goaccess.io no longer publishes a focal suite and
# the distro package is 1.3 (2019), which predates JSON log parsing entirely.
# Build from source instead; it's a small C program with only an ncurses dep.
if ! command -v goaccess >/dev/null 2>&1 || \
   ! goaccess --version 2>/dev/null | grep -q "$GOACCESS_VERSION"; then
  echo "==> Building GoAccess ${GOACCESS_VERSION} from source"
  apt-get install -y -qq build-essential libncursesw5-dev
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  curl -sL "https://tar.goaccess.io/goaccess-${GOACCESS_VERSION}.tar.gz" | tar xz -C "$tmp"
  ( cd "$tmp/goaccess-${GOACCESS_VERSION}" \
      && ./configure --prefix=/usr/local --enable-utf8 >/dev/null \
      && make -j1 >/dev/null \
      && make install >/dev/null )
  echo "    $(goaccess --version | head -1)"
else
  echo "==> GoAccess $(goaccess --version | head -1 | grep -oE '[0-9.]+') already installed"
fi

# --- Report directory -----------------------------------------------------
echo "==> Report directory ${STATS_DIR}"
install -d -o caddy -g caddy -m 0755 "$STATS_DIR"

# --- Access log -----------------------------------------------------------
# Pre-create it owned by caddy. `caddy validate`/`caddy run` as root will
# otherwise create it root-owned 0600 on first touch, and the caddy user then
# cannot open it — Caddy refuses to load the config and `systemctl reload`
# fails. (The running server keeps the old config, so the site stays up, but
# the new log never starts.)
echo "==> Access log /var/log/caddy/access.log"
install -d -o caddy -g caddy -m 0755 /var/log/caddy
[ -f /var/log/caddy/access.log ] || install -o caddy -g caddy -m 0640 /dev/null /var/log/caddy/access.log
chown caddy:caddy /var/log/caddy/access.log

# --- GoAccess config ------------------------------------------------------
echo "==> GoAccess config /etc/goaccess/nharc.conf"
install -d -m 0755 /etc/goaccess
install -m 0644 "$(dirname "$0")/goaccess.conf" /etc/goaccess/nharc.conf

# --- /stats access ---------------------------------------------------------
# /stats is gated on GitHub identity by the OAuth relay (deploy/oauth-relay.py):
# whoever can push to the repo can read the report. That needs an HMAC key for
# the session cookies. Generated here if the relay's env file lacks one.
if ! grep -q "^SESSION_SECRET=" "$OAUTH_ENV" 2>/dev/null; then
  echo "==> Generating SESSION_SECRET in ${OAUTH_ENV}"
  if [ ! -f "$OAUTH_ENV" ]; then
    echo "    ERROR: ${OAUTH_ENV} does not exist — set up the OAuth relay first" >&2
    exit 1
  fi
  secret=$(head -c 32 /dev/urandom | base64 | tr -d '\n')
  printf 'SESSION_SECRET=%s\n' "$secret" >> "$OAUTH_ENV"
  printf 'STATS_REPO=%s\n' "$STATS_REPO" >> "$OAUTH_ENV"
  chown root:root "$OAUTH_ENV"
  chmod 0600 "$OAUTH_ENV"
  restart_relay=yes
else
  echo "==> SESSION_SECRET already present in ${OAUTH_ENV}"
  restart_relay=yes
fi

echo "==> Installing relay to ${RELAY_PATH} and restarting nharc-oauth"
install -d -m 0755 "$(dirname "$RELAY_PATH")"
install -m 0644 -o root -g root "$(dirname "$0")/../oauth-relay.py" "$RELAY_PATH"
if [ "${restart_relay:-}" = yes ]; then
  systemctl restart nharc-oauth
  sleep 1
  systemctl is-active --quiet nharc-oauth && echo "    nharc-oauth is running" \
    || { echo "    ERROR: nharc-oauth failed to start"; journalctl -u nharc-oauth -n 20 --no-pager; exit 1; }
fi

# --- systemd --------------------------------------------------------------
echo "==> systemd units"
install -m 0644 "$(dirname "$0")/nharc-stats.service" /etc/systemd/system/
install -m 0644 "$(dirname "$0")/nharc-stats.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now nharc-stats.timer >/dev/null
echo "    next run: $(systemctl show nharc-stats.timer -p NextElapseUSecRealtime --value)"

echo ""
echo "Done. Deploy the Caddyfile (deploy/deploy.sh installs the site, but the"
echo "Caddyfile is copied manually) and reload Caddy, then:"
echo "  sudo systemctl start nharc-stats.service   # render the first report now"
echo "  https://nharc.org/stats                    # sign in with GitHub"
