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
  // Keep noindex pages out of the sitemap: the members-area placeholder, and
  // the membership form design preview. Both are precise matches so the real
  // /membership page is NOT affected.
  integrations: [
    sitemap({
      filter: (page) => !/\/members\/?$/.test(page) && !/\/membership\/preview\/?$/.test(page),
    }),
  ],
});
