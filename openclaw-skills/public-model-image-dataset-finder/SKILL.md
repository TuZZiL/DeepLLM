---
name: public-model-image-dataset-finder
description: OpenClaw skill for finding publicly accessible images of adult public figures, celebrities, models, adult performers, and online creators for personal ML dataset preparation. Use Tavily for source discovery and Firecrawl for public page extraction. Prioritize public, free, open-web galleries, including free adult/ero galleries when accessible without login or payment. Do not target private, paid-only, login-only, hacked, stolen, or non-consensually distributed media.
---

# Public Model Image Dataset Finder

## Purpose

Use this skill to find public image candidates for a personal SD/LoRA dataset.

This skill may search for publicly available images of:

- celebrities and public figures;
- actors, musicians, influencers, creators, and models;
- adult performers who are clearly adults;
- public/free adult or ero gallery pages;
- public portfolios, official websites, editorial pages, interviews, and public event galleries.

Adult and erotic content is allowed when it is publicly accessible, free to view, and does not require login, payment, bypassing, or unauthorized access.

This skill must not intentionally seek or collect:

- private media;
- paid-only or subscription-only media;
- login-only media;
- hacked, stolen, or non-consensually distributed media;
- access-controlled full-size images;
- images of minors or people whose adult status is unclear.

## Operating rules

1. Use only public pages that are accessible without login, payment, challenge solving, or access-control bypassing.
2. Do not bypass CAPTCHA, Cloudflare, rate limits, authentication, paywalls, hotlink restrictions, or account restrictions.
3. Do not preserve cookies, credentials, session states, downloaded images, or generated dataset manifests in git unless the user explicitly asks to version a sanitized sample manifest.
4. Default to source discovery and dry-run candidate reporting before any download.
5. Keep searches and crawls bounded by user intent, `max_images`, source count, page count, and request delay.
6. Stop using a source when it redirects to login, demands payment, blocks access, or appears to distribute private or unauthorized material.
7. Treat query examples as suggestions, not a whitelist. The agent may create additional queries when useful, as long as the search intent remains focused on public/free/open-web sources.
8. If the user asks for private, paid-only, login-only, hacked, or non-consensual material, refuse that part and offer to search public/free alternatives.

## Defaults

- Default target image count is `max_images = 1`.
- If the user did not specify how many images to find, ask a short clarification before a broad collection run. For a quick lookup, use `max_images = 1`.
- Minimum accepted image size is `width >= 512px` and `height >= 512px`.
- Prefer larger, cleaner, less watermarked images when available, but do not reject an otherwise valid image only because it is below 768px.
- Prefer still image formats: JPEG, PNG, and WebP.
- Reject GIF, SVG, tiny thumbnails, contact sheets, UI screenshots, memes, and obvious duplicate crops.

## Recommended workflow

Run the workflow in this order:

1. Clarify target and count.
   - Identify the exact person or alias.
   - Confirm that the request is for public/free sources only.
   - If no count is provided, use one image for quick lookup or ask how many images to collect.
2. Build search intent.
   - Generate a small set of useful public-source queries.
   - Include aliases, profession, official/public/gallery terms, and adult/ero gallery terms when appropriate.
   - Do not over-constrain the search to fixed templates.
3. Use Tavily for discovery.
   - Search for source pages, not direct downloads.
   - Merge duplicate URLs and canonicalize domains.
   - Score sources before crawling them.
4. Use Firecrawl for accepted public pages.
   - Extract page metadata, image URLs, `srcset` variants, OpenGraph/Twitter images, JSON-LD images, and same-gallery pagination.
   - Do not log in, solve challenges, or access restricted pages.
5. Validate image candidates.
   - Check dimensions and MIME type.
   - Prefer public full-size image URLs already exposed in page HTML or public metadata.
   - Reject restricted, private, duplicate, or low-quality candidates.
6. Return a manifest-style dry-run.
   - Show candidate image URLs, source pages, source type, dimensions, and notes.
   - Include rejected source counts and reasons when helpful.
7. Download only after confirmation.
   - Respect `max_images`, delay, and output directory.
   - Save a manifest beside downloaded files.

## Tavily recommendations

Use Tavily for broad source discovery and query expansion. Tavily should answer: “Which public pages are likely to contain usable images?” It should not be treated as the final image extractor.

Good Tavily practice:

- Start with 3-8 focused queries for the target person.
- Include known aliases and disambiguation terms when needed.
- Mix official/public queries with gallery-oriented queries.
- For adult performers or online creators, include public/free gallery phrasing where appropriate.
- Request enough results to compare domains, but keep the crawl queue small.
- Deduplicate by canonical URL and normalized domain.
- Prefer result pages whose title/snippet indicates free public viewing.
- Avoid spending crawl budget on sources that obviously require login, payment, or challenge solving.

Example query families, provided as suggestions rather than restrictions:

```text
{name} public gallery
{name} free gallery
{name} official photos
{name} model portfolio
{name} photo gallery
{name} HD photos
{name} photoshoot
{name} interview photos
{name} event photos
{name} public ero gallery
{name} adult gallery free
{name} official website gallery
{name} agency portfolio
{name} Wikimedia Commons
{name} IMDb gallery
{name} Listal gallery
{name} Bellazon gallery
{name} GotCeleb gallery
{name} CelebMafia gallery
```

Tavily result scoring:

- High: official sites, public portfolios, public/free galleries, free adult/ero galleries, editorial galleries, event galleries, public agency pages.
- Medium: fan galleries, public forums, public social previews, celebrity/model gallery aggregators.
- Low: pages with heavy ads, uncertain provenance, weak snippets, small thumbnails only, or excessive redirects.
- Skip: login-only, paywalled, challenge-blocked, malware-like, or apparently private/unauthorized sources.

Read `references/tavily_usage.md` for a compact Tavily checklist and prompt pattern.

## Firecrawl recommendations

Use Firecrawl only after Tavily has identified promising public pages. Firecrawl should answer: “Which image candidates are actually exposed by this public page?”

Good Firecrawl practice:

- Crawl accepted source pages only.
- Limit depth and page count.
- Prefer same-domain and same-gallery pagination.
- Extract HTML/Markdown plus metadata when available.
- Collect image candidates from `img`, `srcset`, `picture/source`, lazy-load attributes, OpenGraph, Twitter cards, and JSON-LD.
- Choose the largest candidate in a `srcset` when dimensions or density descriptors are present.
- Resolve relative URLs against the page URL.
- Stop when a page requires login, payment, challenge solving, or an unsupported browser flow.
- Do not use Firecrawl to bypass access controls or crawl paid/private areas.

Read `references/firecrawl_usage.md` for extraction targets and candidate normalization rules.

## Source priority

Highest priority:

- official websites and official galleries;
- public model portfolios;
- agency portfolios;
- public/free gallery pages;
- public/free adult or ero galleries;
- editorial, interview, and event galleries;
- reputable public celebrity/model gallery sites.

Medium priority:

- fan galleries;
- forum/gallery pages visible without login;
- public social media previews;
- public image boards that do not appear to host private or stolen content.

Skip sources when:

- login is required;
- payment or subscription is required;
- full-size media is hidden behind access controls;
- the page appears to distribute private, hacked, stolen, or non-consensual material;
- the page is a malware/adware trap;
- the page blocks access with CAPTCHA, Cloudflare, or similar challenges;
- the page focuses on minors or ambiguous-age people.

Read `references/source_evaluation.md` for source scoring details.

## Image candidate validation

Accept image candidates when:

- width is at least 512px;
- height is at least 512px;
- format is JPEG, PNG, or WebP;
- image is not obviously a tiny thumbnail;
- image is not a collage, contact sheet, meme, or UI screenshot;
- image is not a duplicate of a better candidate;
- image is reachable from a public/free page.

Prefer:

- higher resolution;
- clear subject visibility;
- varied poses, framing, clothing, and lighting;
- low watermark;
- single-subject images;
- images where the target identity is likely correct.

Reject:

- tiny thumbnails;
- animated GIFs and SVGs;
- UI screenshots;
- memes;
- contact sheets;
- heavily watermarked previews;
- duplicate crops;
- images requiring login/payment to access;
- images whose subject identity is uncertain.

## Manifest output

Return structured candidates before downloading. A JSON object should include at least:

```json
{
  "person": "Example Name",
  "source_page_url": "https://example.com/gallery",
  "image_url": "https://example.com/image.jpg",
  "width": 1024,
  "height": 1536,
  "mime": "image/jpeg",
  "query": "Example Name public gallery",
  "source_type": "public_free_gallery",
  "source_score": "high",
  "crawl_date": "YYYY-MM-DD",
  "decision": "candidate",
  "notes": "Public page, no login, no payment required"
}
```

Recommended optional fields:

- `canonical_source_url`;
- `domain`;
- `page_title`;
- `alt_text`;
- `license_hint`;
- `sha256` after download;
- `phash` after local processing;
- `rejection_reason` for rejected candidates.

Read `references/manifest_schema.md` for a fuller schema.

## Download behavior

Default to dry-run. Before downloading, show:

- selected person or alias;
- requested image count;
- number of candidate images;
- selected source domains;
- rejected source count and major reasons;
- any access, quality, or source concerns.

Download only after user confirmation. Use bounded parameters:

- `max_images`;
- `delay`;
- `output_dir`;
- `manifest_path`.

Keep downloaded media, manifests, cookies, and temporary crawl outputs out of git unless the user explicitly requests a sanitized example file.
