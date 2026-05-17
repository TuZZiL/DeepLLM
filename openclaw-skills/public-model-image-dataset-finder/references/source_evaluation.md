# Source Evaluation Rules

This skill prioritizes public/free sources that are likely to expose usable images for personal ML dataset preparation.

## Highest priority sources

Use these first when available:

- official websites;
- official galleries;
- public model portfolios;
- agency portfolios;
- public/free adult or ero gallery pages;
- public/free celebrity or model galleries;
- editorial galleries;
- public interview pages with image galleries;
- public event or red-carpet galleries;
- public commons-style repositories.

## Medium priority sources

Use these when high-priority sources do not provide enough candidates:

- fan galleries;
- public forum/gallery pages visible without login;
- public social media preview pages;
- public image boards with clear public access;
- mixed-quality gallery aggregators.

## Low priority sources

Use these only if needed and inspect carefully:

- pages with heavy ads;
- pages with uncertain provenance;
- pages with only thumbnail previews;
- pages with unclear identity matching;
- pages with many redirects;
- low-quality repost blogs.

## Skip sources

Skip sources when any of these are true:

- login is required;
- payment or subscription is required;
- the full-size media is access-controlled;
- the page blocks access with CAPTCHA, Cloudflare, or similar challenges;
- the page appears to distribute private, hacked, stolen, or non-consensual content;
- the page focuses on minors or ambiguous-age people;
- the page is a malware/adware trap;
- the page is unrelated to the target person.

## Identity matching

Before accepting a source, check whether the page likely refers to the intended person:

- exact or known alias match;
- profession/context match;
- visual/page context match when available;
- domain/source context match;
- no conflicting evidence that the page is about someone else.

When identity is uncertain, mark candidates as `needs_identity_review` instead of accepting them directly.

## Access notes

A page being visible on the public web does not automatically mean every image is suitable. The agent should record source notes such as:

- `public_free_gallery`;
- `official_gallery`;
- `editorial_gallery`;
- `adult_ero_public_gallery`;
- `fan_gallery`;
- `login_required_rejected`;
- `payment_required_rejected`;
- `challenge_rejected`;
- `identity_uncertain`;
- `quality_too_low`.
