# Manifest Schema for Image Dataset Candidates

The manifest records what was found, where it came from, and why it was accepted or rejected. Use JSON Lines for large runs or a JSON array for small runs.

## Minimal candidate record

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

## Recommended full record

```json
{
  "person": "Example Name",
  "aliases_checked": ["Example Alias"],
  "source_page_url": "https://example.com/gallery/page-1",
  "canonical_source_url": "https://example.com/gallery/page-1",
  "domain": "example.com",
  "page_title": "Example Name Gallery",
  "image_url": "https://example.com/images/example-1024.jpg",
  "extraction_method": "srcset",
  "width": 1024,
  "height": 1536,
  "mime": "image/jpeg",
  "query": "Example Name public gallery",
  "source_type": "public_free_gallery",
  "source_score": "high",
  "license_hint": "publicly accessible; verify before reuse",
  "crawl_date": "YYYY-MM-DD",
  "downloaded": false,
  "local_path": null,
  "sha256": null,
  "phash": null,
  "decision": "candidate",
  "rejection_reason": null,
  "notes": "Largest public srcset candidate"
}
```

## Decisions

Use these `decision` values:

- `candidate`: acceptable candidate for user review or download;
- `selected`: chosen for download or dataset inclusion;
- `downloaded`: successfully downloaded and hashed;
- `rejected`: rejected by source, access, quality, identity, or duplicate checks;
- `needs_validation`: dimensions, MIME, identity, or access status still need checking;
- `needs_identity_review`: source or image may refer to a different person.

## Rejection reasons

Common `rejection_reason` values:

- `width_below_512`;
- `height_below_512`;
- `unsupported_mime`;
- `thumbnail_only`;
- `duplicate`;
- `heavy_watermark`;
- `collage_or_contact_sheet`;
- `ui_screenshot_or_meme`;
- `login_required`;
- `payment_required`;
- `challenge_required`;
- `private_or_unauthorized_source`;
- `identity_uncertain`;
- `minor_or_age_uncertain`;
- `not_target_person`;
- `network_error`.

## Dataset notes

For LoRA dataset preparation, the manifest should make it easy to:

- audit source URLs;
- remove low-quality or uncertain candidates;
- deduplicate images after download;
- keep only images above the 512px threshold;
- track public/free source assumptions;
- separate candidate discovery from final dataset curation.
