# NHARC Website: Operations

Reference for running the site. Deployment, CMS login, the traffic report, the
DNS cutover, and what's still outstanding. This is the state and the decisions
that aren't visible in the code.

---

## 1. Current state

- Static Astro site, deployed to https://nharc.org with a valid Let's Encrypt
  cert.
- Served by Caddy (`/etc/caddy/Caddyfile`, source in `deploy/Caddyfile`) out of
  `/var/www/nharc`. HTTPS and renewal are automatic. Caddy uses about 30 MB.
- All the content from the old nharc.org is migrated (repeaters, nets, meetings,
  VE testing, membership, D-STAR, raffle, officers, contact), plus news, meeting
  minutes, and activities presentations.
- Browser CMS is live at `/admin/`, and GitHub sign-in works (self-hosted OAuth
  relay, section 3). Edits commit to `main` and deploy on their own.
- The site wears the club's green and gold identity (seal, tower-mark logo,
  self-hosted fonts). Baseline security headers (HSTS, nosniff and the rest)
  are set in Caddy.
- Traffic statistics are collected and reported nightly. See section 8.
- News feed (RSS) at `/rss.xml`, linked in the footer, and feed readers
  auto-discover it from every page.

Manual redeploy is `./deploy/deploy.sh` (builds and rsyncs).

---

## 2. GitHub and automatic deploys

The repo is `mark-iid/nharcweb`, and it's public. Every push to `main` kicks off
GitHub Actions, which builds the site and rsyncs it to the server over SSH
(`.github/workflows/deploy.yml`, about 25 seconds). CMS edits are commits to
`main`, so they deploy the same way.

The Actions secrets are already set up (Settings → Secrets and variables →
Actions). They're listed here just in case the deploy key ever needs rotating:

| Secret | Value |
| --- | --- |
| `DEPLOY_SSH_KEY` | private half of the deploy key (public half is in the server's `~/.ssh/authorized_keys`) |
| `DEPLOY_HOST` | `nharc.org` (was `newweb.nharc.org` before the cutover) |
| `DEPLOY_USER` | `mark` |
| `DEPLOY_PATH` | `.`, relative on purpose, see 2a (was `/var/www/nharc`) |

`.github/dependabot.yml` keeps the pinned action versions current, as one
grouped PR a month, github-actions only. npm bumps aren't tracked (there are
only two direct dependencies), so Dependabot *security* alerts cover those
instead, under Settings → Advanced Security.

---

## 2a. Restricted Actions deploy key (Aug 2026)

The problem this solved: `DEPLOY_SSH_KEY` used to be an unrestricted shell key
for `mark`, and `mark` has `NOPASSWD: ALL` sudo. So that one Actions secret was
effectively passwordless root on the server. Anyone with write access to
`mark-iid/nharcweb` could push a workflow change that printed the secret into
the Actions log, and that includes any CMS editor added as a collaborator
(section 3), since a collaborator gets the whole repo and not just
`src/content/`.

What was done: the deploy key was rotated, and the new one is locked to exactly
one capability (write into the web root, nothing else). Current state:

- `~/.ssh/authorized_keys` on the server has two lines:
  1. the personal key (`mark@Mark.localdomain`), unrestricted, unchanged.
  2. the CI key (`gh-actions-deploy-nharc-2026-08`), prefixed with
     `command="/usr/bin/rrsync -wo /var/www/nharc"` plus the existing
     `no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding`.
- The `DEPLOY_PATH` secret is now `.` rather than `/var/www/nharc`. `rrsync`
  `chdir`s into the restricted directory and strips a leading `/`, so the
  workflow has to send a relative path. The workflow file itself didn't change.
- The old unrestricted key was removed once two CI runs went green.
- Backups of the previous `authorized_keys` are on the server as
  `~/.ssh/authorized_keys.bak-20260827-212527` and `.bak-preremove`.

Verified at the time: the key can't run a command (`SSH_ORIGINAL_COMMAND='id' is
not rsync`), can't open a shell, can't *read* anything back down (that's the
`-wo`, so it can't be used to exfiltrate), and can't escape the directory (`..`
is rejected). Writes and `--delete` work normally.

So the residual risk is bounded now. A leaked `DEPLOY_SSH_KEY` lets someone
overwrite the website, which a repo collaborator could already do by committing.
It doesn't get them the server any more. `mark` still has `NOPASSWD: ALL` sudo,
but that's reachable from the personal key, not from CI.

### Gotcha: you can't test this key from your Mac

macOS ships Apple's openrsync as `/usr/bin/rsync` now, and it sends `--dirs` in
its server invocation. `rrsync` doesn't allow that option, so any rsync from the
Mac using the restricted key fails with `invalid rsync-command syntax or
options`. That's a client incompatibility and not a misconfiguration. GNU rsync
(which is what the Actions runner uses) works fine.

`./deploy/deploy.sh` isn't affected, since it authenticates with the personal
key, which has no forced command. If you ever do need to exercise the restricted
key by hand, use a GNU rsync. Easiest is to run it from the server itself, or
`brew install rsync` and call `/opt/homebrew/bin/rsync` explicitly.

### Rotating the CI key again

This recipe is zero-downtime (the old key keeps working until the last step):

```bash
ssh-keygen -t ed25519 -N '' -C 'gh-actions-deploy-nharc-YYYY-MM' -f /tmp/newkey
# append the new PUBLIC half to the server, restricted:
printf 'command="/usr/bin/rrsync -wo /var/www/nharc",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding %s\n' \
  "$(cat /tmp/newkey.pub)" | ssh mark@nharc.org 'cp ~/.ssh/authorized_keys ~/.ssh/authorized_keys.bak && cat >> ~/.ssh/authorized_keys'
gh secret set DEPLOY_SSH_KEY --repo mark-iid/nharcweb < /tmp/newkey
gh workflow run deploy.yml --repo mark-iid/nharcweb --ref main   # must go green
# only then: remove the old key line from ~/.ssh/authorized_keys
rm -P /tmp/newkey /tmp/newkey.pub
```

### If you ever need more than this

GitHub → Settings → Environments, with an environment (say `production`) holding
the `DEPLOY_*` secrets and Required reviewers set, plus
`environment: production` on the `deploy:` job, makes every run pause for your
approval before the secrets get injected. That costs a click per deploy
*including every CMS edit*, which is too much friction for this site. Noted only
in case the threat model changes.

---

## 3. Browser CMS (Sveltia) login

The editor is at `/admin/`. It commits edits to `main`, and Actions rebuilds and
deploys. `config.yml` points at `mark-iid/nharcweb`. There are two ways to sign in,
and both work:

- Sign In with GitHub (one click), backed by the self-hosted OAuth relay below.
  This is the normal path for editors.
- Access Token, as a fallback. On the login screen choose *"Sign In Using Access
  Token"* and paste a fine-grained PAT (repo = `mark-iid/nharcweb`, Contents:
  read/write). Useful if the relay is ever down.

### Adding an editor

Editors sign in with their own GitHub account, so "adding a user" really means
giving that account write access to the repo:

1. Get their GitHub username (they'll need a free GitHub account).
2. Add them as a collaborator:
   ```bash
   gh api --method PUT repos/mark-iid/nharcweb/collaborators/USERNAME
   ```
   (or GitHub → repo → Settings → Collaborators → Add people).
3. They accept the invite, then sign in at nharc.org/admin.

Edits get committed under each editor's own GitHub identity. You remove someone
by removing them as a collaborator (`gh api --method DELETE …`).

Note that a collaborator has write access to the *whole repo* (code and
content), not just the CMS, so only add people you trust that far.
Write access also means they could read the deploy secrets by editing the
workflow. See section 2a though, the deploy key is restricted to writing the web
root, so the worst they can do is what they could already do by committing.

### The self-hosted OAuth relay

A stdlib-only Python relay (`deploy/oauth-relay.py`) runs as
`nharc-oauth.service` on `127.0.0.1:8402`, reverse-proxied by Caddy at `/auth`
and `/callback`. The GitHub OAuth App exists and its Client ID and secret live in
`/etc/nharc-oauth.env`. Its callback is `https://nharc.org/callback`, so "Sign In
with GitHub" works at nharc.org/admin. Manage it with
`systemctl status|restart nharc-oauth` and `journalctl -u nharc-oauth`.

This service has a second job as of Sep 2026: it also gates `/stats` (section
8). If it stops, both CMS login and the traffic report go down.

To rotate or recreate the OAuth App (only if you need to): make a new OAuth App
(GitHub → Settings → Developer settings → OAuth Apps) with Homepage
`https://nharc.org` and callback `https://nharc.org/callback`, then update the
two values in `/etc/nharc-oauth.env` and `sudo systemctl restart nharc-oauth`.

---

## 3a. Editing the home page, events and calendar

All of this is editable in the CMS at nharc.org/admin, no code needed:

- Home Page panel is the front page: the intro paragraph, the "Around the club"
  blurb, and the raffle callout with an on/off switch (turn it off when the
  raffle ends, and the heading and text are editable there too). The breakfast
  note is under Settings → Breakfast note.
- Events / Calendar is where you add an event (date/time, location, details).
  There are two checkboxes. "Feature on the homepage" shows it as a banner under
  the hero with a date badge, and "Hide (draft)" keeps it off the site entirely.
  The `/calendar` page lists upcoming events, and past ones move down to a "Past
  events" list.
- Past and featured events drop off by date on their own. "Today" is resolved at
  build time, and a daily scheduled rebuild (the `schedule:` cron in
  `.github/workflows/deploy.yml`, 08:00 UTC) keeps the calendar and the featured
  banners current without anybody having to edit anything.

The files behind all that: `src/data/home.json` (Home Page),
`src/content/events/*.md` (events), `src/pages/calendar.astro`, and the
featured-events block in `src/pages/index.astro`.

---

## 4. Domain cutover (Aug 2026)

`nharc.org` is the live canonical site with a
valid Let's Encrypt cert and HSTS. `www.nharc.org`, `nharc.com`, and
`www.nharc.com` all 301-redirect to it. `newweb.nharc.org` is kept around as a
preview host. The Caddyfile, `astro.config.mjs` (`site`), `public/robots.txt`,
and the deploy host (Actions `DEPLOY_HOST`) are all on `nharc.org`.

CMS login moved to nharc.org/admin at the same time. The OAuth App callback,
`base_url` in `public/admin/config.yml`, and `REDIRECT_URI` / `ALLOWED_ORIGIN` in
`/etc/nharc-oauth.env` are all `https://nharc.org` now. Editors use
nharc.org/admin.

The steps taken, kept for the DNS record values:

1. Add the real domains to Caddy. Edit `deploy/Caddyfile` so the site block
   covers all three hostnames:
   ```
   nharc.org, www.nharc.org, newweb.nharc.org {
       root * /var/www/nharc
       ...
   }
   ```
   (Optionally redirect `www` to the apex.) Copy it up and reload:
   ```bash
   scp deploy/Caddyfile mark@newweb.nharc.org:/tmp/Caddyfile
   ssh mark@newweb.nharc.org 'sudo mv /tmp/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy'
   ```
2. Point DNS at this box:
   - `nharc.org` → A `66.207.135.7`
   - `www.nharc.org` → A `66.207.135.7` (or CNAME to `nharc.org`)

   Caddy picks up Let's Encrypt certs for the new names on first request (ports
   80 and 443 are already open to the internet, verified). Lower the DNS TTL a
   day ahead so the switch is quick and reversible.
3. Update the canonical URL. Set `site: 'https://nharc.org'` in
   `astro.config.mjs` and update the sitemap URL in `public/robots.txt`, then
   rebuild and redeploy.
4. Update the CMS OAuth for the new domain (section 3): change `base_url` in
   `public/admin/config.yml` to `https://nharc.org`, update the OAuth App's
   callback URL to `https://nharc.org/callback`, and set `REDIRECT_URI` and
   `ALLOWED_ORIGIN` in `/etc/nharc-oauth.env` to the new domain, then
   `sudo systemctl restart nharc-oauth`.
5. Keep `newweb.nharc.org` working as it is (it's in the Caddy block) so you can
   still preview.

The old site is hosted externally at pageone.net (`66.207.128.24`). Nothing on
this box touches it, so the cutover was purely a DNS change you control.

---

## 5. Content still to verify

Some of the old site's content was clearly dated. Confirm and update the
following, either in the CMS or in the data files:

- [x] Officers roster, updated to the 2026 elected slate
      (`src/data/officers.json`). A few entries still have first names only (Joe
      KC3ZUC, Nathan N3RTP, Sam KC3ZTO, Mark KB3LYB), so add last names when
      it's convenient. The old Board Chairman and Webmaster entries were dropped
      since they weren't in the election announcement. Re-add them if those roles
      actually exist.
- [x] Raffle, confirmed still active (Jul 2026), so the Raffle page stays live.
      (If it does wrap up later, take it out of the nav in
      `src/components/Header.astro` and `Footer.astro`, and delete
      `src/content/pages/raffle.md` plus `src/pages/raffle.astro`.)
- [x] VE testing details, verified against the live old site (Jul 2026). 2nd
      Saturday at noon, Allison Park location, Bob Worek AG3U, and the $15 + $35
      fees are all still current. Also clarified that the $35 FCC fee gets paid
      to the FCC through CORES, not at the session.
- [x] Meeting format, confirmed Sep 2026. Business meetings really are on Zoom,
      the wording was just stale (it said "currently", which read like a
      temporary pandemic-era arrangement). Reworded in `src/data/site.json` and
      `src/pages/meetings.astro` to describe it as the standing arrangement.
- [ ] Repeaters, confirm all the frequencies, tones and locations. The 444.35
      D-STAR is now labeled W3PGH B at Richland Township (from your note plus the
      2019 relocation), so confirm both the location and the `B` module letter.
      The other W3PGH machine locations are still blank.
- [ ] Membership PDF. `public/files/Membership-form.pdf` is the old form, so
      replace it if there's a newer one. Note it's actually *two* forms in one
      file (club membership, and a separate Repeater Association donation form),
      which matters for section 9.

Two more PDFs are in the repo but not linked anywhere:
`public/files/In-Magazine.pdf` ("NHARC in the news") and
`public/files/W3EXW-Prologue.pdf`.

Not migrated: the 2009-2012 photo galleries and the old D-STAR news log (mostly
2010-2019 entries). Still on the old host if either is ever wanted.

---

## 6. Members-only area (future)

The architecture leaves room for this. There's a placeholder `/members` page and
route already. When you're ready, the lightest option is a shared-password gate
in Caddy (`basic_auth` over a protected subtree). Per-member logins would mean
putting a small auth service in front of Caddy, though the `/stats` gate in
section 8 is now a working example of how to do that if you want it. No members
code exists yet, this is just a note.

## 6a. Look and branding

The site uses the club's green and gold identity, built from the official seal
artwork: pine green `#006633` and gold `#ffcf35`, the tower-mark logo, the
circular seal, and self-hosted webfonts (Barlow Semi Condensed for headings,
Public Sans for body). The colours are CSS variables at the top of
`src/styles/global.css`. The seal and ARRL badge are in `public/images/`, and the
fonts are in `public/fonts/`.

Two old branches are still in git and can be deleted whenever you like:

- `signal-theme`, an early dark "signal" concept with an animated waveform hero,
  abandoned before the green/gold rebrand.
- `green-gold-rebrand`, the rebrand branch, already merged into `main`.

---

## 7. WordPress removal (Jul 2026)

The old WordPress stack (Apache, MySQL, PHP, and the WordPress files) has been
purged. Server memory went from about 47 MB free to about 405 MB free, and Caddy
is the only web service now. Everything was backed up first, to the server at
`~/wp-backup/`:

- `wordpress-db-2026-07-17.sql.gz` (2.8 MB), full database dump
- `wordpress-files-2026-07-17.tar.gz` (130 MB), all WordPress files including
  uploads

The old install was an abandoned "The7"-theme build: 20 pages, a portfolio, and
638 media files that were mostly theme demo filler. The only real club asset in
there was the masthead image, and that one also still lives on the old site at
`nharc.org/art/masthead-trim.jpg`. Keep or delete `~/wp-backup/` at your
discretion.

---

## 8. Traffic statistics (Sep 2026)

Caddy writes a JSON access log, and a nightly systemd timer runs GoAccess over it
and renders a report at https://nharc.org/stats. There's no JavaScript tracker on
the site and no third-party analytics service, so nothing here needs a consent
banner.

Signing in is GitHub, same as the CMS. Whoever can push to the repo can read the
report, checked live against GitHub each time somebody signs in, so there's no
separate password and no second list to keep in sync. Visit `/stats`, you get
bounced through GitHub, and you come back to the report. Adding or removing a
stats viewer is exactly the same as adding or removing an editor (section 3).

The tradeoff is that there is no view-only tier. Adding somebody so they can
see traffic numbers also gives them write access to the whole repo. If you ever want to hand someone stats *without* edit rights, the
relay needs its own allowlist instead of the push-access check. See
`deploy/stats/README.md`.

That file has the full detail, including the operating commands and why each
choice was made. The short version:

| Thing | Where |
|---|---|
| Log | `/var/log/caddy/access.log` (JSON, ~90-day rotation, gzipped by Caddy) |
| Nightly job | `nharc-stats.timer` → `nharc-stats.service`, 03:20 local |
| Report | `/var/www/nharc-stats/index.html` → `/stats` |
| Gate | `forward_auth` → the OAuth relay's `/auth/stats/verify` |
| Session key | `SESSION_SECRET` in `/etc/nharc-oauth.env`, and not in git since this repo is public |
| Install / re-install | `ssh mark@nharc.org 'bash -s' < deploy/stats/install.sh` |

Three gotchas worth knowing before you touch any of it:

- Never run `caddy validate` or `caddy run` as root on this box. Doing that
  creates `/var/log/caddy/access.log` owned by root, and then the `caddy` user
  can't open it, so `systemctl reload caddy` fails with `permission denied`. The
  site stays up on the old config, but the log stops. Fix it with
  `sudo chown caddy:caddy /var/log/caddy/access.log && sudo systemctl reload caddy`.
- GoAccess is built from source (`install.sh` does it). Ubuntu 20.04 is EOL, so
  `deb.goaccess.io` dropped the `focal` suite, and the distro package (1.3, from
  2019) can't parse JSON logs at all.
- The `/stats` gate lives inside the CMS OAuth relay (`nharc-oauth`), so that
  service has two jobs now. If it stops, editors lose "Sign In with GitHub" *and*
  `/stats` goes unreachable. `systemctl status nharc-oauth` covers both.

The report job is capped at `MemoryMax=192M` on purpose. This box has 476 MB and
no swap, and the last OOM event on it killed the web server, so the cap means a
runaway report dies instead of the site.

### Still worth adding

- Google Search Console (and Bing Webmaster Tools). Free, and the only place you
  can see what people actually *searched for* to find the club. Verify the
  domain, then submit `https://nharc.org/sitemap-index.xml`. Log analysis can't
  give you this.
- A monthly plain-language summary of the report is a natural thing to automate
  on top of `/stats`, rather than reading the dashboard by hand.

---

## 9. Membership web form (prototype, Sep 2026)

A design preview exists at `/membership/preview`. It's noindex, excluded from the
sitemap, unlinked from the nav and footer, and the submit button is disabled.
Nothing is wired up behind it. Its purpose is to evaluate the layout before
committing to a back end.

Source is `src/pages/membership/preview.astro`. The fields match the current PDF
(name, callsign, address, city, state, ZIP, home and cell phone, email, license
class, ARRL member) plus a new/renewal toggle and a notes field. A honeypot input
and a load-time stamp are in the markup to illustrate the anti-spam approach;
nothing reads them yet.

Five questions need answering before any of this gets built: where the handler
runs, how mail gets delivered, how spam is handled, whether callsigns are
validated, and what happens to the donation form. Each is below, with a
recommendation.

### Where the handler runs

The site is static, so nothing can accept a POST today. The options are to extend
the existing Python relay, run a separate small service, or use a hosted form
service. A separate service is the better choice. The relay is already
load-bearing for CMS login and `/stats` (section 8), and a defect in public form
handling should not be able to take editor sign-in down with it. Anything
requiring a database is out on this hardware.

### Mail delivery

This is the highest risk in the design, because it fails silently. There's no MTA
on the box, mail for nharc.org is hosted at `newvader.pageone.net`, and no DMARC
record exists. SPF already authorizes this server:
`v=spf1 a mx include:_spf.google.com ip4:66.207.128.0/24 ~all`, where the `a`
mechanism covers `66.207.135.7`. Outbound port 25 is open.

Direct-to-MX would therefore work, but authenticated submission through pageone
on port 587 is the safer route, since that mail is signed by infrastructure that
already sends for the domain.

The controlling requirement is not to depend on email at all. Every submission
should be written to a file on the server as well, making email a notification
and the file the record. Without that, an expired credential means membership
applications disappear with no indication that anything is wrong.

### Spam

Two distinct problems, and the second is the serious one.

Junk submissions are inevitable. A honeypot field, a minimum time-to-submit, and
an IP rate limit handle most of it at no cost. Cloudflare Turnstile is the
fallback if real spam appears. It's worth deferring, because the site currently
loads no third-party scripts at all, which is why it needs no consent banner.

Mail header injection is the actual vulnerability. If user input reaches the
`To`, `From`, `Subject`, or `Reply-To` headers unsanitized, an attacker can embed
newlines, add recipients, and use the form as a spam relay with the domain's own
SPF authorizing it. The recipient must be hardcoded rather than derived from
input, and CR/LF must be stripped from anything placed in a header. User content
belongs in the body only.

### Callsign validation

Worth doing for auto-fill rather than validation. callook.info is free and
requires no key, and populating name, address, and license class from a callsign
removes most of the typing and eliminates transcription errors for the treasurer.

It must be advisory and never blocking. New licensees lag in ULS, vanity calls
change, club and trustee calls exist, foreign hams exist, and associate or family
members may not be licensed at all. The current PDF does not require a valid
callsign, so the form should not either.

### Payment and the donation form

The form should not collect payment details. Dues are paid by check, Zelle, or in
person, and keeping it that way keeps the club entirely outside PCI scope. The
form captures intent to join, not money.

Separately, `Membership-form.pdf` contains two forms: the club membership form,
and a Repeater Association donation form for a different 501(c)(3) with its own
PO Box (15352). Replacing "the PDF" with a single webform would drop the donation
half. Tax-deductible donations also imply an acknowledgment back to the donor.
Treat it as a second decision rather than part of this one.

### Recommendation

Keep the PDF and add the form, rather than replacing one with the other. The PDF
costs nothing to leave up, remains what gets handed out at a hamfest table, and
serves as the fallback if the form breaks. PDFs are genuinely difficult to fill
out on a phone, which is the strongest argument for adding the form at all.
