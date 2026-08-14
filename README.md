# NHARC Website (W3EXW)

Modern website for the **North Hills Amateur Radio Club**, built with
[Astro](https://astro.build). It's a static site — the server just serves plain
files, so it's fast, secure, and light enough to run comfortably on a small box.

**Live (staging):** https://newweb.nharc.org

---

## Editing content — two ways

### 1. In the browser (for non-technical editors)
Club volunteers edit the site in the browser at **https://newweb.nharc.org/admin/** —
a friendly form-based editor (Sveltia CMS). Sign in with GitHub, make changes, and
saving publishes automatically. No coding required. Editor access is granted by adding
the person's GitHub account to the repo (see [HANDOFF.md](HANDOFF.md)).

### 2. In the code (for developers)
Content lives in plain files you can edit directly:

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

- **Automatic (recommended):** push to `main` → GitHub Actions builds and deploys
  (`.github/workflows/deploy.yml`). CMS edits trigger this too.
- **Manual:** `./deploy/deploy.sh` builds locally and rsyncs `dist/` to the server.

## How it's served

The server runs [Caddy](https://caddyserver.com) (`deploy/Caddyfile`), serving
`/var/www/nharc` with automatic HTTPS via Let's Encrypt.

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
deploy/         Caddyfile + deploy.sh
```

See [HANDOFF.md](HANDOFF.md) for GitHub/CI setup, the CMS login setup, the DNS
cutover to `nharc.org`, and the list of content that still needs verifying.
