# Firecrawl Usage for Public Image Candidate Extraction

Use Firecrawl after Tavily has produced a short, scored list of public source pages. Firecrawl should inspect accepted pages and extract image candidates that are visible from public HTML or public metadata.

## Crawl boundaries

Keep crawling bounded:

- crawl only accepted source URLs;
- limit page count and depth;
- prefer same-domain links;
- follow same-gallery pagination only when useful;
- stop at login, payment, CAPTCHA, Cloudflare, or unsupported browser challenge pages;
- do not attempt to bypass access controls.

## Extraction targets

For each page, extract:

- final URL and canonical URL;
- page title;
- page description when useful;
- `img[src]`;
- `img[srcset]`;
- `picture source[srcset]`;
- lazy-load attributes such as `data-src`, `data-original`, `data-full`, `data-lazy-src`, and similar variants;
- OpenGraph image fields such as `og:image`;
- Twitter card image fields such as `twitter:image`;
- JSON-LD image fields;
- anchor links that point directly to image files;
- same-gallery pagination links.

## Candidate normalization

For every extracted image candidate:

1. Resolve relative URLs against the current page URL.
2. Strip obvious tracking fragments when safe.
3. Preserve query parameters when they appear necessary for the image to load.
4. Choose the largest `srcset` candidate when width or density descriptors are available.
5. Keep the source page URL that exposed the image.
6. Record the extraction method: `img`, `srcset`, `picture`, `lazy_attr`, `og_image`, `twitter_image`, `json_ld`, or `direct_anchor`.
7. Mark whether the image appears to be a thumbnail, preview, or full-size candidate.

## Dimension and MIME checks

When Firecrawl or a follow-up HTTP HEAD/GET can provide metadata, keep candidates that satisfy:

- width >= 512px;
- height >= 512px;
- MIME is `image/jpeg`, `image/png`, or `image/webp`.

If dimensions are unavailable, keep the candidate as `needs_validation` unless the URL clearly indicates a thumbnail or unsupported asset.

## Same-gallery pagination

Follow pagination when:

- it stays on the same domain or canonical gallery source;
- labels indicate `next`, page numbers, or gallery continuation;
- the user requested more than one image or the current page lacks valid candidates;
- the crawl remains within configured limits.

Do not follow unrelated outbound links, ad links, account links, checkout links, or login links.

## Firecrawl output format

Return normalized candidates:

```json
{
  "source_page_url": "https://example.com/gallery/page-1",
  "canonical_source_url": "https://example.com/gallery/page-1",
  "page_title": "Example Gallery",
  "candidates": [
    {
      "image_url": "https://example.com/images/example-1024.jpg",
      "extraction_method": "srcset",
      "width": 1024,
      "height": 1536,
      "mime": "image/jpeg",
      "candidate_type": "full_or_large",
      "decision": "candidate",
      "notes": "Largest srcset entry exposed in public HTML"
    }
  ],
  "pagination": [
    "https://example.com/gallery/page-2"
  ],
  "blocked": false,
  "block_reason": null
}
```

## Stop conditions

Stop crawling a source and mark it rejected when:

- login is required;
- payment or subscription is required;
- full-size image requires restricted access;
- CAPTCHA, Cloudflare, or a challenge page appears;
- the page appears to distribute private, stolen, hacked, or non-consensual media;
- the page is not about the target person;
- repeated errors or rate limiting occur.
