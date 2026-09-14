import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import MarkdownIt from 'markdown-it';
import sanitizeHtml from 'sanitize-html';
import type { APIContext } from 'astro';
import site from '../data/site.json';

const parser = new MarkdownIt();

// Feed readers fetch the XML on its own, with no page around it, so every link
// and image has to carry the full origin. Astro's content is authored with
// root-relative paths (`/uploads/...`), so rewrite those as we render.
function absolutize(html: string, origin: string): string {
  return html.replace(/(href|src)="\/(?!\/)/g, `$1="${origin}/`);
}

// sanitize-html's defaults drop images and h1/h2, both of which club editors
// legitimately use in a post. Everything else stays at the safe defaults.
const allowedTags = [...sanitizeHtml.defaults.allowedTags, 'img', 'h1', 'h2'];
const allowedAttributes = {
  ...sanitizeHtml.defaults.allowedAttributes,
  img: ['src', 'alt', 'title', 'width', 'height'],
};

export async function GET(context: APIContext) {
  const origin = context.site!.origin;

  // Newest first. `pinned` deliberately does NOT reorder the feed — a reader
  // expects reverse-chronological, and re-pinning an old post would otherwise
  // resurface it as if it were new.
  const posts = (await getCollection('news', ({ data }) => !data.draft)).sort(
    (a, b) => b.data.date.getTime() - a.data.date.getTime()
  );

  return rss({
    title: `${site.clubName} (${site.callsign}) — News`,
    description: site.tagline,
    site: context.site!,
    trailingSlash: false,
    items: posts.map((post) => {
      const body = absolutize(parser.render(post.body ?? ''), origin);
      return {
        title: post.data.title,
        pubDate: post.data.date,
        description: post.data.summary ?? '',
        link: `/news/${post.id}`,
        content: sanitizeHtml(body, { allowedTags, allowedAttributes }),
      };
    }),
    // Declared so the self-link below validates; without it the W3C feed
    // validator flags a missing `rel="self"`.
    xmlns: { atom: 'http://www.w3.org/2005/Atom' },
    customData: [
      '<language>en-us</language>',
      `<copyright>© ${new Date().getFullYear()} ${site.clubName}</copyright>`,
      `<atom:link href="${origin}/rss.xml" rel="self" type="application/rss+xml"/>`,
    ].join(''),
  });
}
