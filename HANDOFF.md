# NHARC Website — Handoff & Operations

This covers everything that isn't in the code: how the live site is set up, the
one-time steps to finish (GitHub CI + browser CMS login), how to switch the real
`nharc.org` domain over, and the content that still needs a human to verify.

---

## 1. What's done and live

- **Static Astro site** built and deployed to **https://newweb.nharc.org** (valid
  Let's Encrypt HTTPS).
- Served by **Caddy** (`/etc/caddy/Caddyfile`, source in `deploy/Caddyfile`) from
  `/var/www/nharc`. Automatic HTTPS + renewal. Caddy uses ~30 MB RAM.
- **Apache is stopped and disabled** (the old WordPress + Elementor attempt was
  OOM-killing the 476 MB box — that's why we went static).
- All content from the old nharc.org has been migrated (repeaters, nets, meetings,
  VE testing, membership, D-STAR, raffle, officers, contact).
- Browser CMS files are in place at `/admin/` but need the GitHub backend wired up
  (section 3) before login works.

**Redeploy anytime** from your Mac: `./deploy/deploy.sh` (builds + rsyncs).

---

## 2. Put it on GitHub + automatic deploys

The browser CMS and CI both need the repo on GitHub.

1. **Create the repo** on GitHub (a club org like `nharc`, or your account). The
   local repo is **already initialized**: `main` (the live classic theme) and
   `signal-theme` (the archived dark theme). Push both:
   ```bash
   cd ~/src/nharcweb
   git remote add origin git@github.com:OWNER/nharcweb.git
   git push -u origin main
   git push origin signal-theme
   ```
2. **Make a deploy SSH key** (lets GitHub Actions rsync to the server):
   ```bash
   ssh-keygen -t ed25519 -f ~/nharc_deploy -N "" -C "gh-actions-deploy"
   ssh mark@newweb.nharc.org "cat >> ~/.ssh/authorized_keys" < ~/nharc_deploy.pub
   ```
3. **Add repo secrets** (GitHub → Settings → Secrets and variables → Actions):
   | Secret | Value |
   | --- | --- |
   | `DEPLOY_SSH_KEY` | contents of `~/nharc_deploy` (the **private** key) |
   | `DEPLOY_HOST` | `newweb.nharc.org` |
   | `DEPLOY_USER` | `mark` |
   | `DEPLOY_PATH` | `/var/www/nharc` |
4. Delete the local private key copy (`rm ~/nharc_deploy`). The workflow
   (`.github/workflows/deploy.yml`) now builds and deploys on every push to `main`.

---

## 3. Turn on the browser CMS (Sveltia) login

The editor lives at **/admin/**. It commits edits to GitHub; Actions then rebuilds
and deploys. Editors need a (free) GitHub account with write access to the repo.

First, set the repo in **`public/admin/config.yml`**:
```yaml
backend:
  name: github
  repo: OWNER/nharcweb   # <-- your real org/repo
  branch: main
```

Then pick a login method:

- **Simplest — Personal Access Token.** Sveltia lets each editor sign in with a
  GitHub fine-grained PAT (scoped to this repo, Contents: read/write). No server to
  run. Good for 1–3 maintainers. Share these one-time setup instructions with each
  editor; nothing else to configure.
- **Nicer — GitHub OAuth ("Sign in with GitHub" button).** Stand up the small
  `sveltia-cms-auth` relay (a free Cloudflare Worker) and create a GitHub OAuth App;
  set the Worker URL as `base_url` in `config.yml`. See
  https://github.com/sveltia/sveltia-cms#readme. Worth it if several people edit.

Commit the `config.yml` change and push. Test at
`https://newweb.nharc.org/admin/`.

---

## 4. Switching `nharc.org` over (when ready)

The site is on staging today. To make it the real site:

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
4. Keep `newweb.nharc.org` working as-is (it's in the Caddy block), so you can still
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
- [ ] **VE testing details** — location, fees, and contact taken from the old page
      (`src/content/pages/ve-testing.md`). Confirm still accurate.
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

## 6a. Themes

The live site uses the **classic** light theme. A second, bolder **dark "signal"**
theme (animated waveform hero, modernized gradient NHARC wordmark) is preserved on the
**`signal-theme`** git branch to revisit later — likely without the animation.

- `main` (the active branch) = classic theme. All content edits go here, so the CMS and
  every edit land on the live look automatically.
- `signal-theme` = the dark theme, frozen. To preview or adopt it later, we'll rebase it
  onto the current content and deploy.

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
