# NHARC Website (W3EXW)

Modern website for the **North Hills Amateur Radio Club**, built with
[Astro](https://astro.build). It's a static site — the server just serves plain
files, so it's fast, secure, and light enough to run comfortably on a small box.

**Live (staging):** https://newweb.nharc.org

---

## Editing content — two ways

### 1. In the browser (for non-technical editors)
Once the GitHub backend is set up (see [HANDOFF.md](HANDOFF.md)), club volunteers
edit the site at **https://newweb.nharc.org/admin/** — a friendly form-based editor
(Sveltia CMS). Saving publishes automatically. No coding required.

### 2. In the code (for developers)
Content lives in plain files you can edit directly:

| What | Where |
| --- | --- |
| Club info, schedule, contact, dues | `src/data/site.json` |
| Repeater list | `src/data/repeaters.json` |
| Net schedule | `src/data/nets.json` |
| Officers roster | `src/data/officers.json` |
| PA D-STAR reference table | `src/data/padstar.json` |
| Page prose (About, Membership, VE Testing, D-STAR, Raffle) | `src/content/pages/*.md` |
| News / announcements | `src/content/news/*.md` |
| PDFs, images | `public/files/`, `public/images/` |

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
`/var/www/nharc` with automatic HTTPS via Let's Encrypt. Apache and the old
WordPress attempt are disabled.

## Project layout

```
src/
  components/   Header, Footer, Logo, PageHeader
  content/      Markdown: pages/ and news/  (+ content.config.ts schemas)
  data/         JSON data files (repeaters, nets, officers, site, padstar)
  layouts/      BaseLayout.astro
  pages/        One .astro file per route
  styles/       global.css
public/
  admin/        Sveltia CMS (index.html + config.yml)
  files/        PDFs (membership form, etc.)
  images/       Images
deploy/         Caddyfile + deploy.sh
```

See [HANDOFF.md](HANDOFF.md) for GitHub/CI setup, the CMS login setup, the DNS
cutover to `nharc.org`, and the list of content that still needs verifying.
