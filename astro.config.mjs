// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Primary domain (post-cutover). newweb.nharc.org still serves as a preview host.
export default defineConfig({
  site: 'https://nharc.org',
  trailingSlash: 'ignore',
  build: {
    format: 'directory',
  },
  // Keep the members-area placeholder out of the sitemap (it's also noindex).
  // Precise match so /membership is NOT affected.
  integrations: [sitemap({ filter: (page) => !/\/members\/?$/.test(page) })],
});
