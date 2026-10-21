// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Primary domain (post-cutover). newweb.nharc.org still serves as a preview host.
export default defineConfig({
  site: 'https://nharc.org',
  trailingSlash: 'ignore',
  // Astro 7 defaults to 'jsx', which drops the space at a line break before an
  // inline element ("or\n<strong>131.8 Hz</strong>" renders as "or131.8 Hz").
  // true is the lossless compression Astro 5 used.
  compressHTML: true,
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
