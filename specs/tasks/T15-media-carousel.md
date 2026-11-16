# T15: Media carousel: implementation

**Status:** blocked
**Depends on:** T14 (wireframe approved)
**User stories:** US-15

## Goal
Vendors add Instagram and YouTube links to their listing. Customers see them as a click-to-load carousel on the business page, as approved in T14.

## Context
- Product decisions (2026-11-15):
  - Embeds only (no uploads).
  - Instagram and YouTube.
  - Click to load.
  - YouTube via `youtube-nocookie.com`.
- **The CSP blocks all iframes today:** `default-src 'self'` with no `frame-src` (`config/settings.py` → `SECURE_CSP`). Instagram's official `embed.js` would also need a third-party script, which the CSP forbids. Use the script-free iframe endpoints instead:
  - Instagram: `https://www.instagram.com/p/<shortcode>/embed` (reels: `/reel/<shortcode>/embed`).
  - YouTube: `https://www.youtube-nocookie.com/embed/<id>`.

  Check both URL formats against each provider's current documentation while implementing.
- **Security:** never render a user-supplied URL into an iframe. Parse links at the form boundary into `(provider, ref)`, validate `ref` with a strict regex, and build the embed URL server-side from a fixed template.
- Moderation: edits to approved listings go live without re-moderation (product.md open question), so new media appears immediately. Staff can unapprove. Note this risk in the PR.
- The layout, states and a11y follow the approved T14 artboards and the `specs/design.md` "Media carousel" entry.

## Acceptance criteria
- **Model:** `MediaItem(EmbeddedModel)` with:
  - `provider`: `instagram` or `youtube`.
  - `ref`: Instagram shortcode `^[A-Za-z0-9_-]{5,40}$` with `kind` `post` or `reel`; YouTube id `^[A-Za-z0-9_-]{11}$`.
  - `caption`: ≤ 120 chars, blank allowed.

  `Business.media = EmbeddedModelArrayField(MediaItem, default=list, blank=True)`, at most 8 items. It's not part of `search_terms`.
- **Vendor form:**
  - A media formset (up to 8 rows) taking a pasted link plus caption. Accepted link forms:
    - `instagram.com/p/<sc>/`, `instagram.com/reel/<sc>/`, with or without `www.` and with query strings stripped.
    - `youtube.com/watch?v=<id>`, `youtu.be/<id>`, `youtube.com/shorts/<id>`.
  - Anything else → "Paste a link to an Instagram post or reel, or a YouTube video."
  - Blank rows are ignored. Order is kept, and reorder works as in T14.
- **Detail page:**
  - The carousel is in the right column above contact, full width on phones, per T14.
  - Each slide is a placeholder `<button>` labelled with the provider and caption.
  - Clicking replaces it with an `<iframe>` built from the server-generated embed URL: `loading="lazy"`, `referrerpolicy="strict-origin-when-cross-origin"`, `sandbox="allow-scripts allow-same-origin allow-popups allow-presentation"`, `allow="encrypted-media; picture-in-picture"`, plus a `title`.
  - The section is hidden when there's no media.
- **Panel:** whatever T14 approved.
- **CSP:** `frame-src` adds exactly `https://www.instagram.com` and `https://www.youtube-nocookie.com`. Everything else is unchanged, with no inline script or style.
- **JS:** `static/js/media-carousel.js` registers `Alpine.data("mediaCarousel")`, loaded only on the detail page.
  - Prev/next, arrow keys and dots.
  - Click-to-load, swapping in the iframe from a `data-embed-src` the server provides.
  - No auto-advance.
- **Dashboard:** hint when a listing has no media.

## Tests to write first
`apps/directory/tests/test_media.py` → `MediaLinkParsingTests`, `MediaFormTests`, `MediaRenderTests`
- Parsing, one case per accepted link form → `(provider, ref, kind)`.
- Rejected:
  - Other domains, e.g. `instagram.com.evil.example`.
  - `javascript:` links.
  - Profile URLs (`instagram.com/<user>/`).
  - Playlists.
  - Malformed ids.
  - A YouTube id that isn't 11 characters.
- `test_more_than_8_rejected`, `test_blank_rows_ignored`, `test_order_preserved`.
- `test_media_round_trip`: save and reload as an embedded array.
- Rendering:
  - Placeholders render with no `<iframe>` in the initial HTML (click to load).
  - `data-embed-src` is exactly the server-built URL.
  - The caption is escaped.
  - The section is hidden with no media.
- `test_csp_frame_src_allows_only_instagram_and_youtube_nocookie`.
- `test_detail_page_no_inline_script_or_style` (re-assert).

## Implementation notes
- The parser lives in `apps/directory/media.py` as `parse_media_link(url) -> (provider, ref, kind)` or raises `ValidationError`. It uses `urllib.parse`, an exact host allowlist, and the regexes above. It's the only place that turns links into refs.
- The embed URL builder sits next to it (`embed_url(item)`). Templates call it through a model property, never by concatenating strings in the template.
- Thumbnails: YouTube offers static thumbnails (`i.ytimg.com`). Using one would add an `img-src` origin and still be a third-party request, so only do it if T14 shows thumbnails, and note the CSP change. Instagram has no script-free thumbnail, so use the branded placeholder.
- Docs: CLAUDE.md (media model, parser, CSP `frame-src`) and product.md (domain model `media` row; US-15).

## Out of scope
- Uploads and storage.
- Other providers.
- Fetching thumbnails or metadata server-side (oEmbed).
- Re-moderation of media changes.

## Manual verification
- Add 3 links (an Instagram post, an Instagram reel, a YouTube video) in the listing form and reorder them.
- On the page, placeholders show and no requests go to Instagram or YouTube until a click (check the network tab). After a click the embed plays.
- No CSP violations in the console.
- At 390 px, slides swipe and snap.
