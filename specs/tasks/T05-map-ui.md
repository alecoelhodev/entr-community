# T05: Map UI: filters, search, detail panel

**Status:** ready
**Depends on:** T04, T06
**User stories:** US-1, US-2, US-3, US-4

## Goal
The home page is the directory map, centered on Doral, FL. A category select and a search box drive the markers and the nearby list. Clicking a marker opens the business panel in the sidebar.

## Context
- Build to the `Main`, `Panel` and `Mobile` artboards in [design.md](../design.md). That includes the tokens, the vendored fonts, the pin styles and the "Delivery" badge in results.
- The current page is `templates/places/map.html` with `static/js/map.js` (`Alpine.data("placesMap")`).
- Patterns to keep:
  - Leaflet objects live in closure variables, not on the Alpine component.
  - URLs come from `data-*` attributes.
  - A debounced `moveend` triggers the marker load, and `AbortController` cancels stale fetches.
  - `htmx.ajax` swaps the sidebar content.
- The CSP forbids inline scripts and styles. Alpine is the CSP build, so templates can use plain property access only, with no expressions.
- Endpoints come from T04 (`directory:geojson`, `directory:nearby`) and T06 (`directory:panel`).

## Acceptance criteria
- `/` renders the directory map (`directory:map`). The old places map moves off `/`; T09 deletes it.
- The center and zoom come from `data-center-lat="25.8195" data-center-lng="-80.3553" data-zoom="13"`, which the view sets from settings constants (`MAP_DEFAULT_CENTER`, `MAP_DEFAULT_ZOOM`).
- Sidebar controls:
  - A category `<select>`: "All categories" plus every category, server-rendered.
  - A search `<input type="search" maxlength="100">`.
  - The radius select, which already exists.
- Changing the category, or typing in search (debounced 300 ms), reloads the markers with the `category` and `q` params. If a point was clicked, the nearby list reloads with the same filters.
- Clicking a marker loads `/b/<slug>/panel/` into `#detail` via `htmx.ajax`. The panel can be closed, which clears `#detail`.
- An empty result shows "No businesses match these filters here." A 400 shows the existing "Zoom in…" or a filter error message.
- The map tooltip shows the name and category.

## Tests to write first
`apps/directory/tests/test_map_page.py` → `MapPageTests`
- `test_home_is_directory_map`: `/` contains `x-data="directoryMap"`.
- `test_data_attributes_present`: the geojson, nearby and panel URL template, center lat/lng and zoom.
- `test_category_options_rendered`.
- `test_search_input_has_maxlength_100`.
- `test_csp_header_allows_tile_origin`: the existing assertion, kept.
- `test_no_inline_script_or_style`: the response has no `<script>` tag without `src`, and no `style=` attribute.

JS behavior has no automated test runner in this project; don't add one in this task. Cover it with the manual checklist below.

## Implementation notes
- Rename the component `placesMap` → `directoryMap`. Keep a single `static/js/map.js`.
- Panel URL: pass a template URL such as `data-panel-url="/b/__slug__/panel/"`, built with `{% url 'directory:panel' 'slug-placeholder' %}`, and substitute `encodeURIComponent(slug)` in JS. Don't concatenate unescaped strings.
- Use `URLSearchParams` for query strings, and drop empty values.
- Bind controls with `x-model` to component properties (`category`, `q`), and react with `$watch` inside `init()`. No inline expressions.
- Add the CSS to `static/css/app.css`.

## Out of scope
- User geolocation (non-goal).
- Marker clustering.
- URL state (deep links to filters).

## Manual verification
Run with `seed_directory`, or admin-created data in Doral, and check each item:
- [ ] The map opens on Doral.
- [ ] Category "Bakery" shows only bakeries; "All" restores everything.
- [ ] Typing "golfeados" leaves only matching markers.
- [ ] Clicking a marker opens its panel; closing it clears it.
- [ ] Clicking the map lists nearby results respecting the filters.
- [ ] The browser console has no CSP violations.
