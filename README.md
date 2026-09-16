# NHARC Website (W3EXW)

[![Build & Deploy](https://github.com/mark-iid/nharcweb/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/mark-iid/nharcweb/actions/workflows/deploy.yml)
[![Site](https://img.shields.io/website?url=https%3A%2F%2Fnharc.org&label=nharc.org&up_message=up&down_message=down)](https://nharc.org)
[![Built with Astro](https://img.shields.io/badge/built%20with-Astro-BC52EE?logo=astro&logoColor=white)](https://astro.build)

Website for the North Hills Amateur Radio Club, built with
[Astro](https://astro.build). It's a static site, so the server is just handing
out plain files. That matters more than it sounds like it should: the box this
runs on has 476 MB of RAM and no swap, and an earlier WordPress attempt got
OOM-killed on it.

Live at https://nharc.org.

---

## Editing content

There are two ways in, depending on who you are.

**In the browser.** Club volunteers edit at https://nharc.org/admin/ using
Sveltia CMS. Sign in with GitHub, make your changes, and saving publishes on its
own. No code involved. Getting someone editor access means adding their GitHub
account to the repo (see [HANDOFF.md](HANDOFF.md) section 3).

**In the files.** Everything is plain text if you'd rather edit it directly:

| What | Where |
| --- | --- |
| Club info, schedule, contact, dues | `src/data/site.json` |
| Home page (intro, "Around the club" blurb, raffle on/off) | `src/data/home.json` |
| Repeater list | `src/data/repeaters.json` |
| Net schedule | `src/data/nets.json` |
| Officers roster | `src/data/officers.json` |
| PA D-STAR reference table | `src/data/padstar.json` |
| Page prose (About, Membership, VE Testing, D-STAR, Raffle) | `src/content/pages/*.md` |
| News / announcements | `src/content/news/*.md` |
| Meeting minutes | `src/content/minutes/*.md` |
| Activities presentations | `src/content/presentations/*.md` |
| Events / calendar | `src/content/events/*.md` |
| PDFs, images | `public/files/`, `public/images/`, `public/uploads/` |

## Local development

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # output to dist/
npm run preview  # serve the built site
```

## Deploying

Push to `main` and GitHub Actions builds and deploys it
(`.github/workflows/deploy.yml`). CMS edits are just commits, so they trigger
the same thing. That's the normal path.

If you need to push something out by hand, `./deploy/deploy.sh` builds locally
and rsyncs `dist/` to the server. It refuses to run if your checkout is behind
`origin/main`, which is deliberate: the rsync uses `--delete`, so deploying from
a stale tree would wipe files that were added since (images uploaded through the
CMS, usually).

## How it's served

[Caddy](https://caddyserver.com) serves `/var/www/nharc` with automatic HTTPS
from Let's Encrypt. Config is `deploy/Caddyfile`, and the installed copy lives
at `/etc/caddy/Caddyfile`.

Caddy also writes a JSON access log that feeds a nightly traffic report at
`/stats`. See [deploy/stats/README.md](deploy/stats/README.md).

## Project layout

```
src/
  components/   Header, Footer, TowerMark, Icon, PageHeader, ClubSlideshow
  content/      Markdown: pages/, news/, minutes/, presentations/, events/  (+ content.config.ts schemas)
  data/         JSON data files (repeaters, nets, officers, site, padstar)
  layouts/      BaseLayout.astro
  pages/        One .astro file per route
  styles/       global.css  (green & gold theme, self-hosted webfonts)
public/
  admin/        Sveltia CMS (index.html + config.yml)
  files/        PDFs (membership form, etc.)
  fonts/        Self-hosted webfonts (Barlow Semi Condensed, Public Sans)
  images/       Images (club seal, ARRL badge, and the club/ photo set)
  uploads/      CMS-uploaded media
deploy/         Caddyfile, deploy.sh, oauth-relay.py, stats/
```

[HANDOFF.md](HANDOFF.md) has the rest: GitHub and CI setup, how CMS login
actually works, the DNS cutover, the traffic stats, and the content that still
needs somebody to verify it.
