// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Staging: newweb.nharc.org. At DNS cutover, change `site` to https://nharc.org.
export default defineConfig({
  site: 'https://newweb.nharc.org',
  trailingSlash: 'ignore',
  build: {
    format: 'directory',
  },
  integrations: [sitemap()],
});
