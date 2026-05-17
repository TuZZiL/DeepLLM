# Tavily Usage for Public Image Dataset Discovery

Use Tavily as the source-discovery layer. Tavily should find pages likely to expose public image candidates; Firecrawl should inspect those pages afterward.

## Inputs to prepare

Before searching, identify:

- target display name;
- known aliases or stage names;
- profession or context for disambiguation;
- requested image count;
- whether adult/ero public galleries are appropriate for the target;
- any domains the user explicitly wants to include or exclude.

If the user did not specify count, default to one image for quick lookup or ask how many images to collect before a broader run.

## Query strategy

Generate a small set of varied public-source queries. Do not treat these examples as a whitelist.

Useful query directions:

- official pages and portfolios;
- public/free galleries;
- free adult or ero galleries when appropriate;
- editorial or interview pages;
- public event galleries;
- model agency pages;
- public celebrity/model gallery aggregators;
- public commons-style image repositories.

Example queries:

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
```

Adapt queries to the person and available context. If a name is ambiguous, add profession, country, website, platform handle, or known alias.

## Tavily result normalization

For each result, normalize:

- `title`;
- `url`;
- canonical URL if available;
- domain;
- snippet/content summary;
- query that produced the result;
- source category guess;
- whether it appears public, free, and crawlable.

Deduplicate by canonical URL first, then normalized URL, then domain/path similarity.

## Tavily source scoring

Score each result before sending it to Firecrawl.

High-priority signals:

- official website or portfolio;
- public/free gallery language;
- public/free adult or ero gallery language;
- agency, editorial, interview, event, or public photo gallery context;
- image-rich page likely to expose full image URLs;
- no sign of login, subscription, or challenge requirement in snippet/title.

Medium-priority signals:

- fan gallery or public forum page;
- public social preview page;
- gallery aggregator with mixed quality;
- uncertain but plausible image page.

Low-priority signals:

- heavy ads or clickbait title;
- likely thumbnail-only page;
- weak identity match;
- excessive redirects;
- unclear image availability.

Skip signals:

- login required;
- subscription or paid-only access;
- challenge/CAPTCHA indication;
- apparent malware/adware trap;
- apparent private, hacked, stolen, or non-consensual material;
- minors or ambiguous-age subjects.

## Suggested Tavily prompt pattern

Ask Tavily for public pages, not downloads:

```text
Find public/free web pages likely to contain image galleries for {name}. Include official pages, public portfolios, editorial galleries, event galleries, and free public gallery pages. Return source pages with titles, URLs, and snippets. Do not require login or payment.
```

For adult performers or creators:

```text
Find public/free web pages likely to contain image galleries for {name}. Include official pages, public portfolios, interviews, public galleries, and free adult/ero galleries that are viewable without login or payment. Return source pages with titles, URLs, and snippets.
```

## Output expected from Tavily step

Return a compact list for Firecrawl:

```json
{
  "target": "Example Name",
  "requested_count": 1,
  "sources": [
    {
      "url": "https://example.com/gallery/example-name",
      "title": "Example Name Gallery",
      "domain": "example.com",
      "query": "Example Name public gallery",
      "source_score": "high",
      "source_type": "public_free_gallery",
      "crawl_decision": "crawl",
      "notes": "Snippet indicates free public gallery"
    }
  ]
}
```
