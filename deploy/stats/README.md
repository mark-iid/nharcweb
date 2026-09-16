# Traffic statistics

`Caddy JSON access log` → `nightly GoAccess run` → `https://nharc.org/stats`

All of it is server-side. There's no JavaScript tracker on the site and no
third-party analytics service, so there's nothing here that needs a consent
banner. (The `/stats` page itself does set one session cookie once you sign in,
but that's an authentication cookie on a private page, not visitor tracking.)

Who can see it: anyone who can push to `mark-iid/nharcweb`, which is the same
people who can edit the site in the CMS. That's read live from GitHub every time
someone signs in, so removing a collaborator removes their access to the report
too. There's no second list to keep in sync.

## Install

```sh
ssh mark@nharc.org 'bash -s' < deploy/stats/install.sh   # from a checkout
# or, on the server, from a copy of this directory:
sudo ./install.sh
```

It's idempotent, so re-running it after changing `goaccess.conf` or the units is
fine. On a first run it appends a generated `SESSION_SECRET` (and `STATS_REPO`)
to `/etc/nharc-oauth.env`, installs the relay, and restarts `nharc-oauth`.
There's no password to write down anywhere, since sign-in is GitHub.

It does not install the Caddyfile. Do that separately:

```sh
scp deploy/Caddyfile mark@nharc.org:/tmp/Caddyfile
ssh mark@nharc.org 'sudo install -m 0644 /tmp/Caddyfile /etc/caddy/Caddyfile \
  && sudo chown caddy:caddy /var/log/caddy/access.log \
  && sudo systemctl reload caddy'
```

That `chown` isn't decoration. If you run `caddy validate` or `caddy run` as
root at any point, it creates `access.log` owned by root with mode 0600, and
then the `caddy` user can't open it. The next reload fails with `permission
denied`. The running server keeps its old config when that happens, so the site
stays up, but the new log never starts. Re-chown it and reload.

## Pieces

| Where | What |
|---|---|
| `deploy/Caddyfile` | the `log` block (JSON → `/var/log/caddy/access.log`), the `/stats` handler, and its `forward_auth` gate |
| `deploy/oauth-relay.py` | the gate itself: `/auth/stats/{verify,login,logout}`, installed at `/opt/nharc-oauth/oauth-relay.py` |
| `/etc/nharc-oauth.env` | `SESSION_SECRET` and `STATS_REPO` (mode 0600, and not in git) |
| `/etc/goaccess/nharc.conf` | from `goaccess.conf` here |
| `nharc-stats.service` | one-shot report render |
| `nharc-stats.timer` | nightly at 03:20 local, `Persistent=true` |
| `/var/www/nharc-stats/index.html` | the rendered report |

## Operating it

```sh
sudo systemctl start nharc-stats.service    # re-render the report now
systemctl list-timers nharc-stats.timer     # when does it next run
journalctl -u nharc-stats -n 50             # did it fail
sudo tail -f /var/log/caddy/access.log      # watch live traffic
systemctl status nharc-oauth                # the /stats gate + CMS login
journalctl -u nharc-oauth -n 50             # gate errors
```

If the relay is down then `/stats` is unreachable, and so is CMS "Sign In with
GitHub". The report itself is just a file though, so `sudo cat
/var/www/nharc-stats/index.html` still works over SSH.

Granting and revoking access is the same thing you do for editors (HANDOFF
section 3):

```sh
gh api --method PUT repos/mark-iid/nharcweb/collaborators/USERNAME
gh api --method DELETE repos/mark-iid/nharcweb/collaborators/USERNAME
```

Worth saying plainly: there is no view-only tier. Anyone you add so they can see
traffic numbers also gets write access to the whole repo. If you want somebody
to read stats without being able to edit the site, the relay would need its own
allowlist instead of the `permissions.push` check.

## How the /stats gate works

Caddy `forward_auth`s every `/stats` request to the relay at
`/auth/stats/verify`. The relay answers `200` if the request carries a valid
session cookie, and `302 /auth/stats/login` if it doesn't. Caddy passes any
non-2xx straight back to the browser, so somebody who isn't signed in just lands
in the GitHub flow.

Signing in goes out to GitHub, comes back to `/callback`, and then the relay
asks GitHub `GET /repos/{STATS_REPO}` using that person's own token and reads
`permissions.push`. Push access mints an HMAC-signed session cookie (HttpOnly,
Secure, SameSite=Lax, 12 hours). No push access gets a 403 that explains why.
The cookie only carries a username and an expiry, and it's rejected if either
the signature or the expiry fails. A missing `SESSION_SECRET` fails closed, so
nobody gets in rather than everybody.

Two structural details that are easy to break by accident:

A GitHub OAuth App has exactly one callback URL, and the CMS already owns
`/callback`. Touching the OAuth App was the change most likely to break editor
sign-in, so instead both flows share that one callback and get told apart by a
`stats.` prefix on the OAuth `state`. If you ever change that prefix, change it
in the sender *and* in the branch in `do_GET`.

The gate endpoints live under `/auth/stats/`, not `/stats-auth/`. The report is
served by `handle_path /stats*`, and any path starting with `stats` collides
with that. `/auth*` was already proxied to the relay, so putting them there
needs no extra Caddy route.

## Notes and deliberate choices

GoAccess is built from source rather than installed from a package. Ubuntu 20.04
is past end-of-life, so `deb.goaccess.io` doesn't publish a `focal` suite any
more, and the distro package is 1.3 (from 2019) which predates JSON log parsing
entirely. The jammy `.deb` isn't a substitute either, since it's built against a
newer glibc than focal has. `install.sh` builds 1.9.4, which has
`--log-format=CADDY` built in.

The nightly job re-parses every retained log instead of keeping incremental
state. A full recompute can't drift or double-count, and at this site's volume
it takes a few seconds. The tradeoff is that the report only covers the
retention window below.

Retention is roughly 90 days, set by `roll_keep 12` and `roll_keep_for 2160h` on
the `log` block in the Caddyfile. Caddy gzips the rolled files itself, so
logrotate isn't involved at all. Raise `roll_keep` if you want more history. The
box has about 846 GB free, so disk isn't the constraint here.

`MemoryMax=192M` on the service is a guard, not a tuning knob. This box has 476
MB and no swap, and the last OOM event on it killed the web server. If a bot
flood ever pushes GoAccess's in-memory hashes past the cap, the *report* job
dies and the site keeps serving. A failed render shows up in `journalctl -u
nharc-stats`.

Access logs contain visitor IP addresses. They're readable only by `caddy`, they
age out with the rotation window above, and they never leave the server.
GoAccess needs them to count unique visitors. If you'd rather not retain them at
all, drop `roll_keep_for` to something short.

Crawlers are reported rather than discarded (`ignore-crawlers false`), so "is
Google actually indexing us" stays a question you can answer. Bot traffic does
inflate the headline request count, so read the Crawlers panel alongside it.
Flip that setting if the noise ever gets in the way.

## What this won't tell you

Log analysis sees requests, not people. It can't reliably tell a returning
visitor from a new one beyond an IP heuristic, and it can't see anything
happening client-side.

For search terms, meaning what people actually typed to find the club, you need
Google Search Console. That's the only source for it, and it's worth having
regardless.
