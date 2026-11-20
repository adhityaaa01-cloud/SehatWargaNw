# Landing directory and seamless map background

Asset image/sehatwarga-direktori-map-bg.png inspected (2172x724 PNG), copied unchanged to frontend/static/images. Quick Services bottom fades to #def4eb, matching the directory top. Search and results share one background section; a responsive upper map layer preserves the illustration composition and fades into the full-section map. Mobile illustration is softer for readable headings. Hero unchanged.

Existing GET /facilities is the sole data source; no backend/database/authentication modifications. home-directory.js fetches its server-rendered, Jinja-escaped facility cards and pagination, with existing search/facility_type parameters. A JSON script element in that directory template exposes the already-available map_facilities context (no new data queries). Interactive map uses only valid actual coordinates from that response. Background image markers remain decorative. Cards preserve actual names, category, address, city, phone, codes and detail links. No synthetic distance/rating/hours.

Loading, empty, request-error, and map-unavailable states implemented. Requests abort on replacement and timeout. Map resources removed when results change. No-JS form/filter/full-directory links keep working; inline results require JavaScript. External Leaflet/tile availability is not guaranteed; map-failure fallback was explicitly verified with the library request blocked. Successful live tile rendering not independently verified in this run.

Changed this iteration:
- frontend/templates/public/home.html
- frontend/templates/public/facilities/list.html (existing coordinate data as JSON)
- frontend/static/css/main.css
- frontend/static/js/home-directory.js (new)
- frontend/static/images/sehatwarga-direktori-map-bg.png (new copy)
- scripts/check_landing_directory.py (new browser regression)
- qa/landing-directory screenshots and this report

Actual tests:
- .venv/bin/python -m unittest tests.test_render_routes: 1 test passed (covers seeded public/citizen/admin pages), 1.382s; post-success SQLite ResourceWarning.
- BROWSER_EXECUTABLE=/tmp/sw-browsers/chromium-1248/chrome-linux64/chrome .venv/bin/python scripts/check_landing_directory.py: passed. Uses disposable SQLite and a temporary local server, not configured application DB.
- Chromium at 1366x768, 1440x900, 768x1024, 375x812, 360x800: no horizontal overflow, asset 200, cards rendered.
- Actual HOSPITAL/PUSKESMAS/CLINIC filters, name search, no-result search, detail destination, server 503 state, library-failure fallback, no-JS navigation: passed. No JavaScript exceptions. Intentional blocked-map/503 errors and pre-existing favicon 404 are expected during fault checks.
- Desktop/mobile transition and cards screenshots visually inspected and refined. git diff --check passed.

Run .venv/bin/python scripts/preview.py and visit http://127.0.0.1:5055 for safe local review.

## Full-width layout refinement

Updated only home directory markup and scoped CSS, plus the browser regression checks. Existing container now has directory-container class: width 100%, max-width 1680px, auto margins and padding clamp(20px,3vw,48px). No duplicate outer wrapper. Search width increased from 680px to up to 1080px. Results heading/status/full-directory link sit left, category filters right with natural wrapping on small screens.

Grid uses 24px gaps and equal-height rows. Columns: >=1440 four, 1024–1439 three, 640–1023 two, <640 one. Fixed column counts prevent sparse filtered results stretching a card across the entire row. Card contents/data unchanged, solid white surfaces retained. Map background, hero and navbar unchanged.

Actual expanded browser run passed at 1366x768, 1440x900, 1728x900, 1920x1080, 1024x768, 768x1024, 640x960, 375x812 and 360x800. Assertions verify column count, centered wrapper at min(viewport,1680px), equal card heights, asset availability and zero horizontal overflow. Screenshots updated in this directory; desktop 1366/1440/1920 and mobile375 visually inspected. Existing category/search/detail/empty/error/map-failure/no-JS checks all passed. RenderRoutes unittest passed again. git diff --check passed.
