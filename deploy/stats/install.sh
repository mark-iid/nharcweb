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
AUTH_FILE=/etc/caddy/stats-auth.conf

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

# --- /stats credentials ---------------------------------------------------
# Kept out of the repo: nharcweb is a public repo, and while a bcrypt hash is
# not directly reversible there is no reason to publish one.
if [ ! -f "$AUTH_FILE" ]; then
  echo "==> Generating /stats credentials"
  pass=$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | head -c 20)
  hash=$(caddy hash-password --plaintext "$pass")
  cat > "$AUTH_FILE" <<EOF
# Credentials for https://nharc.org/stats — imported by /etc/caddy/Caddyfile.
# Regenerate:  caddy hash-password --plaintext 'newpassword'
basic_auth {
	nharc ${hash}
}
EOF
  chown root:caddy "$AUTH_FILE"
  chmod 0640 "$AUTH_FILE"
  echo ""
  echo "    ####################################################"
  echo "    #  /stats login   user: nharc"
  echo "    #                 pass: ${pass}"
  echo "    #  Save this now — it is not stored anywhere else."
  echo "    ####################################################"
  echo ""
else
  echo "==> Keeping existing credentials in ${AUTH_FILE}"
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
echo "  https://nharc.org/stats"
