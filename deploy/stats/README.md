# Traffic statistics

`Caddy JSON access log` → `nightly GoAccess run` → `https://nharc.org/stats`

Everything is server-side. There is no JavaScript tracker on the site, no
cookies, no third-party service, and so nothing that needs a consent banner.

## Install

```sh
ssh mark@nharc.org 'bash -s' < deploy/stats/install.sh   # from a checkout
# or, on the server, from a copy of this directory:
sudo ./install.sh
```

The script is idempotent. On first run it prints a generated password for
`/stats` — **save it then**, it is not stored in plaintext anywhere.

It does not install the Caddyfile. Do that separately:

```sh
scp deploy/Caddyfile mark@nharc.org:/tmp/Caddyfile
ssh mark@nharc.org 'sudo install -m 0644 /tmp/Caddyfile /etc/caddy/Caddyfile \
  && sudo chown caddy:caddy /var/log/caddy/access.log \
  && sudo systemctl reload caddy'
```

The `chown` matters: if you run `caddy validate` or `caddy run` as root at any
point, it creates `access.log` root-owned `0600` and the `caddy` user can no
longer open it, so the next reload fails with `permission denied`. The running
server keeps its old config in that case, so the site stays up, but the new log
never starts. Re-chown and reload.

## Pieces

| Where | What |
|---|---|
| `deploy/Caddyfile` | `log` block (JSON → `/var/log/caddy/access.log`) and the `/stats` handler |
| `/etc/caddy/stats-auth.conf` | basic-auth hash for `/stats`. **Not in git** — this repo is public |
| `/etc/goaccess/nharc.conf` | from `goaccess.conf` here |
| `nharc-stats.service` | one-shot report render |
| `nharc-stats.timer` | nightly at 03:20 local, `Persistent=true` |
| `/var/www/nharc-stats/index.html` | the rendered report |

## Operating it

```sh
sudo systemctl start nharc-stats.service    # re-render right now
systemctl list-timers nharc-stats.timer     # when does it next run
journalctl -u nharc-stats -n 50             # did it fail
sudo tail -f /var/log/caddy/access.log      # watch live traffic
```

## Notes and deliberate choices

**GoAccess is built from source, not installed from a package.** Ubuntu 20.04
is past end-of-life, so `deb.goaccess.io` no longer publishes a `focal` suite,
and the distro package is 1.3 (2019) which predates JSON log parsing entirely.
The jammy `.deb` is not a substitute — it is built against a newer glibc than
focal has. `install.sh` builds 1.9.4, which has `--log-format=CADDY` built in.

**The nightly job re-parses every retained log rather than keeping incremental
state.** A full recompute cannot drift or double-count, and at this site's
volume it takes seconds. The cost is that the report covers only the retention
window below.

**Retention is ~90 days,** set by `roll_keep 12` / `roll_keep_for 2160h` on the
`log` block in the Caddyfile, and Caddy gzips rolled files itself (no logrotate
involved). Raise `roll_keep` for a longer history; the box has ~846 GB free, so
disk is not the constraint.

**`MemoryMax=192M` on the service is a deliberate guard, not a tuning knob.**
This box has 476 MB and no swap, and an OOM event here previously killed the
web server. If a bot flood ever makes GoAccess's in-memory hashes blow past the
cap, the *report* job dies and the site keeps serving. A failed render shows up
in `journalctl -u nharc-stats`.

**Access logs contain visitor IP addresses.** They are readable only by
`caddy`, they age out with the rotation window above, and they never leave the
server. GoAccess needs them to count unique visitors. If you would rather not
retain them at all, drop `roll_keep_for` to something short.

**Crawlers are reported, not discarded** (`ignore-crawlers false`), so "is
Google actually indexing us" stays an answerable question. Bot traffic does
inflate the headline request count — read the Crawlers panel alongside it. Flip
that setting if the noise ever gets in the way.

## What this does not tell you

Log analysis sees requests, not people: it cannot tell a returning visitor from
a new one beyond an IP heuristic, and it cannot see anything client-side.
For search terms — what people typed to find the club — use Google Search
Console, which is the only source for that and is worth having regardless.
