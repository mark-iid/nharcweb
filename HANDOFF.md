# NHARC Website — Handoff & Operations

This covers everything that isn't in the code: how the live site is set up (GitHub CI
and the browser CMS login are both done), how to switch the real `nharc.org` domain
over when you're ready, and the content that still needs a human to verify.

---

## 1. What's done and live

- **Static Astro site** built and deployed to **https://newweb.nharc.org** (valid
  Let's Encrypt HTTPS).
- Served by **Caddy** (`/etc/caddy/Caddyfile`, source in `deploy/Caddyfile`) from
  `/var/www/nharc`. Automatic HTTPS + renewal. Caddy uses ~30 MB RAM.
- All content from the old nharc.org has been migrated (repeaters, nets, meetings,
  VE testing, membership, D-STAR, raffle, officers, contact), plus news, meeting
  minutes, and activities presentations.
- **Browser CMS is live** at `/admin/` — GitHub sign-in works (self-hosted OAuth
  relay, section 3). Edits commit to `main` and auto-deploy.
- The site wears the club's **green & gold identity** (seal, tower-mark logo,
  self-hosted fonts). Baseline security headers (HSTS, nosniff, etc.) are set in Caddy.

**Redeploy anytime** from your Mac: `./deploy/deploy.sh` (builds + rsyncs).

---

## 2. GitHub + automatic deploys — DONE

The repo is at **`mark-iid/nharcweb`** (public). Every push to `main` triggers GitHub
Actions to build the site and rsync it to the server over SSH
(`.github/workflows/deploy.yml`, ~25 s). CMS edits commit to `main`, so they deploy the
same way.

The Actions secrets are already configured (Settings → Secrets and variables → Actions)
— listed here only in case the deploy key ever needs rotating:

| Secret | Value |
| --- | --- |
| `DEPLOY_SSH_KEY` | private half of the deploy key (public half is in the server's `~/.ssh/authorized_keys`) |
| `DEPLOY_HOST` | `nharc.org` (was `newweb.nharc.org` pre-cutover) |
| `DEPLOY_USER` | `mark` |
| `DEPLOY_PATH` | `/var/www/nharc` |

---

## 3. Browser CMS (Sveltia) login — LIVE

The editor lives at **/admin/**. It commits edits to `main`; Actions rebuilds and
deploys. `config.yml` points at `mark-iid/nharcweb`. Two ways to sign in, both working:

- **Sign In with GitHub** (one-click) — backed by the self-hosted OAuth relay below.
  This is the normal path for editors.
- **Access Token** (fallback) — on the login screen choose *"Sign In Using Access
  Token"* and paste a fine-grained PAT (repo = `mark-iid/nharcweb`, Contents:
  read/write). Handy if the relay is ever down.

### Adding an editor
Editors sign in with their own GitHub account, so "adding a user" means giving that
account write access to the repo:

1. Get their GitHub username (they need a free GitHub account).
2. Add them as a collaborator:
   ```bash
   gh api --method PUT repos/mark-iid/nharcweb/collaborators/USERNAME
   ```
   (or GitHub → repo → Settings → Collaborators → Add people).
3. They accept the invite, then sign in at **nharc.org/admin**.

Edits are committed under each editor's own GitHub identity. Remove someone by removing
them as a collaborator (`gh api --method DELETE …`). Note: a collaborator has write
access to the **whole repo** (code + content), not just the CMS — add only people you
trust accordingly.

### The self-hosted OAuth relay — configured
A tiny stdlib-Python relay (`deploy/oauth-relay.py`) runs as **`nharc-oauth.service`**
on `127.0.0.1:8402`, reverse-proxied by Caddy at `/auth` and `/callback`. The GitHub
OAuth App is created and its Client ID/secret live in `/etc/nharc-oauth.env`; its
callback is `https://nharc.org/callback`, so "Sign In with GitHub" works at
**nharc.org/admin**. Manage with `systemctl status|restart nharc-oauth` and
`journalctl -u nharc-oauth`.

To rotate or recreate the OAuth App (only if needed): make a new OAuth App (GitHub →
Settings → Developer settings → **OAuth Apps**) with Homepage `https://nharc.org` and
callback `https://nharc.org/callback`, then update the two values in
`/etc/nharc-oauth.env` and `sudo systemctl restart nharc-oauth`.

---

## 4. Domain cutover — DONE (nharc.org is live)

**Cutover complete (Aug 2026):** `nharc.org` is the live, canonical site (valid Let's
Encrypt cert + HSTS). `www.nharc.org`, `nharc.com`, and `www.nharc.com` 301-redirect to
it. `newweb.nharc.org` is kept as a preview host. The Caddyfile, `astro.config.mjs`
(`site`), `public/robots.txt`, and the deploy host (Actions `DEPLOY_HOST`) are all on
`nharc.org`.

> **CMS login now lives at `nharc.org/admin`** (moved Aug 2026): the OAuth App callback,
> `base_url` in `public/admin/config.yml`, and `REDIRECT_URI`/`ALLOWED_ORIGIN` in
> `/etc/nharc-oauth.env` are all `https://nharc.org`. Editors use **nharc.org/admin**.

The steps below are retained for reference and the DNS record values.

1. **Add the real domains to Caddy.** Edit `deploy/Caddyfile` — change the site
   block to cover all three hostnames, e.g.:
   ```
   nharc.org, www.nharc.org, newweb.nharc.org {
       root * /var/www/nharc
       ...
   }
   ```
   (Optionally redirect `www` → apex.) Copy it up and reload:
   ```bash
   scp deploy/Caddyfile mark@newweb.nharc.org:/tmp/Caddyfile
   ssh mark@newweb.nharc.org 'sudo mv /tmp/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy'
   ```
2. **Point DNS at this box.** At your DNS host, set:
   - `nharc.org` → **A** `66.207.135.7`
   - `www.nharc.org` → **A** `66.207.135.7` (or CNAME to `nharc.org`)

   Caddy will automatically obtain Let's Encrypt certs for the new names on first
   request (ports 80/443 are already open to the internet — verified). Lower the
   DNS TTL a day ahead for a quick, reversible switch.
3. **Update the canonical URL.** In `astro.config.mjs` set `site: 'https://nharc.org'`
   and in `public/robots.txt` update the sitemap URL. Rebuild/redeploy.
4. **Update the CMS OAuth for the new domain** (§3): change `base_url` in
   `public/admin/config.yml` to `https://nharc.org`, update the OAuth App's callback
   URL to `https://nharc.org/callback`, and set `REDIRECT_URI` / `ALLOWED_ORIGIN` in
   `/etc/nharc-oauth.env` to the new domain, then `sudo systemctl restart nharc-oauth`.
5. Keep `newweb.nharc.org` working as-is (it's in the Caddy block), so you can still
   preview.

> The old site is hosted externally at pageone.net (`66.207.128.24`). Nothing on
> this box touches it — the cutover is purely a DNS change you control.

---

## 5. Content that needs a human to verify

Some of the old site's content was clearly dated. Please confirm and update (in the
CMS or the data files) before this becomes the public site:

- [x] **Officers roster** — updated to the 2026 elected slate (`src/data/officers.json`).
      Note: several entries have first names only (Joe KC3ZUC, Nathan N3RTP, Sam KC3ZTO,
      Mark KB3LYB) — add last names when handy. The old Board Chairman and Webmaster
      entries were dropped (not in the election announcement); re-add if those roles exist.
- [x] **Raffle** — confirmed **still active** (Jul 2026); the Raffle page stays live.
      (If it later concludes, remove it from the nav in `src/components/Header.astro` /
      `Footer.astro` and delete `src/content/pages/raffle.md` + `src/pages/raffle.astro`.)
- [x] **VE testing details** — verified against the live old site (Jul 2026): 2nd Sat
      at noon, Allison Park location, Bob Worek AG3U, $15 + $35 fees all still current.
      Clarified that the $35 FCC fee is paid to the FCC via CORES, not at the session.
- [ ] **Repeaters** — confirm all frequencies/tones/locations. The 444.35 D-STAR is
      now labeled **W3PGH B** at **Richland Township** (per your note + the 2019
      relocation) — confirm the location and the `B` module letter. Other W3PGH machine
      locations are still blank.
- [ ] **Meeting format** — old site said business meetings are "currently virtual via
      Zoom." Confirm current in-person/Zoom status (`src/data/site.json`).
- [ ] **Membership PDF** — `public/files/Membership-form.pdf` is the old form; replace
      if there's a newer one.

Also available if you want them: `public/files/In-Magazine.pdf` ("NHARC in the news")
and `public/files/W3EXW-Prologue.pdf` — not linked anywhere yet.

**Not migrated:** the 2009–2012 photo galleries and the old D-STAR news log (mostly
2010–2019 entries). Say the word if you want any of it brought over or archived.

---

## 6a. Look & branding

The live site uses the club's **green & gold identity**, built from the official seal
artwork: pine green `#006633` + gold `#ffcf35`, the tower-mark logo, the circular seal,
and self-hosted webfonts (Barlow Semi Condensed for headings, Public Sans for body).
Colours are CSS variables at the top of `src/styles/global.css`; the seal and ARRL
badge live in `public/images/`, fonts in `public/fonts/`.

Two old branches remain in git and can be deleted whenever you like:

- `signal-theme` — an early dark "signal" concept (animated waveform hero), abandoned
  before the green/gold rebrand.
- `green-gold-rebrand` — the rebrand branch, already merged into `main`.

## 6. Members-only area (future)

The architecture leaves room for it: there's a placeholder `/members` page and route.
When you're ready, the lightest option is a shared-password gate in Caddy
(`basic_auth` over a protected subtree); per-member logins would mean adding a small
auth service in front of Caddy. No members code exists yet — this is just a note.

---

## 7. WordPress removed (done)

The old WordPress stack — Apache, MySQL, PHP, and the WordPress files — has been
**purged**. Server memory went from ~47 MB free to **~405 MB free**, and Caddy is now
the only web service. Everything was **backed up first** to the server at
`~/wp-backup/` before removal:

- `wordpress-db-2026-07-17.sql.gz` (2.8 MB) — full database dump
- `wordpress-files-2026-07-17.tar.gz` (130 MB) — all WordPress files incl. uploads

The old install was an abandoned "The7"-theme build (20 pages, a portfolio, and 638
media files that were mostly theme demo filler). The only real club asset in it was
the masthead image, which also still lives on the old site at
`nharc.org/art/masthead-trim.jpg`. Keep or delete `~/wp-backup/` at your discretion.
