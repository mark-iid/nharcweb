# Traffic statistics

`Caddy JSON access log` → `nightly GoAccess run` → `https://nharc.org/stats`

Everything is server-side. There is no JavaScript tracker on the site and no
third-party analytics service, so nothing that needs a consent banner. (The
`/stats` page itself sets one session cookie once you sign in, but that is an
authentication cookie on a private page, not visitor tracking.)

**Who can see it:** anyone who can push to `mark-iid/nharcweb` — i.e. exactly
the people who can edit the site in the CMS. Access is read live from GitHub at
each sign-in, so removing a collaborator removes their access to the report
too, with no second list to keep in sync.

## Install

```sh
ssh mark@nharc.org 'bash -s' < deploy/stats/install.sh   # from a checkout
# or, on the server, from a copy of this directory:
sudo ./install.sh
```

The script is idempotent. On first run it appends a generated `SESSION_SECRET`
(and `STATS_REPO`) to `/etc/nharc-oauth.env`, installs the relay, and restarts
`nharc-oauth`. There is no password to save — sign-in is GitHub.

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
| `deploy/Caddyfile` | `log` block (JSON → `/var/log/caddy/access.log`), the `/stats` handler, and its `forward_auth` gate |
| `deploy/oauth-relay.py` | the gate itself: `/auth/stats/{verify,login,logout}`, installed at `/opt/nharc-oauth/oauth-relay.py` |
| `/etc/nharc-oauth.env` | `SESSION_SECRET` + `STATS_REPO` (mode 0600, **not in git**) |
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
systemctl status nharc-oauth                # the /stats gate + CMS login
journalctl -u nharc-oauth -n 50             # gate errors
```

If the relay is down, `/stats` is unreachable (and so is CMS "Sign In with
GitHub"). The report itself is just a file, so `sudo cat
/var/www/nharc-stats/index.html` still works over SSH.

Grant or revoke access exactly as you do for editors (HANDOFF §3):

```sh
gh api --method PUT repos/mark-iid/nharcweb/collaborators/USERNAME
gh api --method DELETE repos/mark-iid/nharcweb/collaborators/USERNAME
```

Note the flip side: **there is no view-only tier.** Anyone you add so they can
see traffic numbers also gets write access to the whole repo. If you want
someone to read stats without being able to edit the site, the relay would need
a separate allowlist instead of the `permissions.push` check.

## How the /stats gate works

Caddy `forward_auth`s every `/stats` request to the relay at
`/auth/stats/verify`. The relay answers `200` if the request carries a valid
session cookie and `302 /auth/stats/login` otherwise; Caddy passes any non-2xx
straight back to the browser, so an unauthenticated visitor simply lands in the
GitHub flow.

Signing in goes to GitHub, comes back to `/callback`, and the relay then asks
GitHub `GET /repos/{STATS_REPO}` with the user's own token and reads
`permissions.push`. Push access mints an HMAC-signed session cookie
(`HttpOnly`, `Secure`, `SameSite=Lax`, 12 hours); no push access gets a 403
explaining why. The cookie carries only a username and an expiry, and is
rejected if either the signature or the expiry fails — a missing
`SESSION_SECRET` means it fails closed and nobody gets in.

Two structural details that are easy to break:

- **A GitHub OAuth App has exactly one callback URL,** and the CMS already owns
  `/callback`. Rather than touch the OAuth App (the thing most likely to break
  editor sign-in), both flows share that callback and are told apart by a
  `stats.` prefix on the OAuth `state`. If you change the prefix, change it in
  both the sender and the branch in `do_GET`.
- **The gate endpoints live under `/auth/stats/`, not `/stats-auth/`,** because
  the report is served by `handle_path /stats*` and *any* path beginning with
  `stats` would collide with it. `/auth*` is already proxied to the relay, so
  this needs no extra Caddy route.

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
