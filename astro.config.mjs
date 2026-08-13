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
  // Keep the members-area placeholder out of the sitemap (it's also noindex).
  // Precise match so /membership is NOT affected.
  integrations: [sitemap({ filter: (page) => !/\/members\/?$/.test(page) })],
});
