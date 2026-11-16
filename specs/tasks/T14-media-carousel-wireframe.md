# T14: Media carousel: wireframe (design only)

**Status:** ready
**Depends on:** — (needs the user's approval to finish)
**User stories:** US-15

## Goal
Agree on how a business's photos and videos look and behave before any code is written. The outcome is an approved wireframe added to the design canvas and recorded in `specs/design.md`. T15 implements it.

## Context
- Product decision (2026-11-15): on the full business page, the right-hand column gets a media section, "think of it as a small Instagram". For the MVP its content is **Instagram and YouTube embeds**; uploads are still a non-goal.
- Embeds use **click to load**. Each item shows a branded placeholder; the third-party iframe loads only when the visitor clicks. This avoids third-party cookies and weight on every page view. YouTube uses `youtube-nocookie.com`.
- The current right column is the contact card (`Detail` artboard; `templates/directory/_detail_body.html` → `.biz-contact`). The panel (`Panel` artboard) is a narrow single column.
- Approved design canvas: https://claude.ai/artifact/PVv2PjiiMunuoWRnFed2wV. Tokens and components are in [design.md](../design.md).

## Acceptance criteria (what the wireframe must show)
- **Detail page, desktop:**
  - The media section sits in the right column above the contact card. A large active item plus a strip of thumbnails or dots, with prev/next buttons.
  - Each item is a placeholder card: the provider mark (Instagram / YouTube), a "Tap to load" call to action, and a caption line if one exists.
  - It also shows one item in its loaded state.
- **Detail page, phone width:** the carousel is full width below the header block, with swipe-friendly cards (scroll-snap) and dots.
- **Panel (map sidebar):** a decision. Either a compact one-row strip that links to the page, or no media in the panel. Show the chosen option.
- **Vendor listing form:**
  - A "Photos & videos" section: paste Instagram post/reel or YouTube links (up to 8), with an optional caption, reorder up/down and remove.
  - Error state for an unsupported link: "Paste a link to an Instagram post or reel, or a YouTube video."
- **Empty state:** with no media, the section is hidden for customers. The vendor dashboard and form hint "Add photos or videos from Instagram or YouTube".
- **Accessibility notes on the artboard:**
  - Carousel controls are real buttons with labels, and the active slide is announced.
  - Placeholders are buttons whose label names the provider and caption.
  - Keyboard: arrow keys move between slides; Enter/Space loads the embed.
  - Reduced motion: no auto-advance.
- **Consent copy:** placeholder text notes "Loads content from Instagram/YouTube".

## Tests to write first
None; this is a design task.

## Implementation notes
- Add the new artboards (`MediaDetail`, `MediaMobile`, `MediaForm`, plus `MediaPanel` if the panel shows media) to the existing design canvas with the Artifact tool, using the same tokens and type as the approved screens. Publish to the same canvas URL.
- **⚠ confirm: the user approves the wireframe** before T15 starts. Iterate on feedback in the canvas.
- Once approved:
  - Add a "Media carousel" component entry to `specs/design.md` (layout, states, a11y, provider placeholders).
  - Update the screen → route → task table.
  - Mark T15 `ready`.

## Out of scope
- Code.
- Uploads.
- Other providers (TikTok, Facebook).
- Auto-play and auto-advance.

## Manual verification
The user reviews the canvas and approves it, or requests changes.
