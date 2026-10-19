import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Pages render dates as UTC wall-clock. The CMS writes datetimes without seconds
// (2026-10-22T18:00), which YAML leaves as a string rather than a timestamp, and
// new Date() reads a zoneless string in the build machine's own zone. Pin it to UTC
// so a local build and the CI runner agree.
const asUtc = (v: unknown) => (typeof v === 'string' && /T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(v) ? `${v}Z` : v);
const date = z.preprocess(asUtc, z.coerce.date());

// The CMS saves a cleared optional date as '' (or a bare key, which YAML reads as
// null) instead of omitting it. Treat both as absent: coercing '' fails the build,
// and coercing null silently becomes 1 Jan 1970.
const optionalDate = z.preprocess(
  (v) => (v === '' || v === null ? undefined : asUtc(v)),
  z.coerce.date().optional(),
);

// Free-form page bodies (prose) that club editors can edit in the CMS.
const pages = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/pages' }),
  schema: z.object({
    title: z.string(),
    description: z.string().optional(),
    order: z.number().optional(),
  }),
});

// News / announcements, newest first.
const news = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/news' }),
  schema: z.object({
    title: z.string(),
    date,
    summary: z.string().optional(),
    pinned: z.boolean().default(false),
    draft: z.boolean().default(false),
  }),
});

// Meeting minutes — typed in the CMS and/or an attached PDF.
const minutes = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/minutes' }),
  schema: z.object({
    date,
    meeting: z.enum(['Business', 'Activities']).default('Business'),
    title: z.string().optional(),
    document: z.string().optional(),
    draft: z.boolean().default(false),
  }),
});

// Events / calendar — upcoming club activities. Past ones drop off automatically.
const events = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/events' }),
  schema: z.object({
    title: z.string(),
    date,
    endDate: optionalDate,
    location: z.string().optional(),
    featured: z.boolean().default(false),
    draft: z.boolean().default(false),
  }),
});

// Activities-meeting presentations — an uploaded slide deck plus metadata.
const presentations = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/presentations' }),
  schema: z.object({
    title: z.string(),
    date,
    presenter: z.string().optional(),
    file: z.string().optional(),
    summary: z.string().optional(),
    draft: z.boolean().default(false),
  }),
});

export const collections = { pages, news, minutes, presentations, events };
