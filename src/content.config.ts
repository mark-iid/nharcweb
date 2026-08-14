import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

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
    date: z.coerce.date(),
    summary: z.string().optional(),
    pinned: z.boolean().default(false),
    draft: z.boolean().default(false),
  }),
});

// Meeting minutes — typed in the CMS and/or an attached PDF.
const minutes = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/minutes' }),
  schema: z.object({
    date: z.coerce.date(),
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
    date: z.coerce.date(),
    endDate: z.coerce.date().optional(),
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
    date: z.coerce.date(),
    presenter: z.string().optional(),
    file: z.string().optional(),
    summary: z.string().optional(),
    draft: z.boolean().default(false),
  }),
});

export const collections = { pages, news, minutes, presentations, events };
