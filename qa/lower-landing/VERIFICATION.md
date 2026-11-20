# Healthcare journey, About Us, and landing footer

Original image/a_wide_horizontal_background_image_web_hero_secti.png exists (2172x724 PNG). Byte-identical static copy: frontend/static/images/healthcare-journey.png (matching SHA-256 f3a6cd10e7a297761dc916ac37b7612973e57ef563ce851ab8ef1869f611b748). HTTP 200 verified. Image is scoped to the journey/help wrapper, never the whole site. A masked image layer preserves the path and three points while fading the map/mint wave into the wrapper background. Directory's bottom now fades to the same mint. Initial visual check found the image bottom edge visible; fixed by fading the image layer itself.

Three original steps retained word-for-word, three columns on desktop/tablet, aligned beneath the three journey points. Mobile uses a visible full-width miniature path above stacked steps. Help panel uses solid white, 16px radius, subtle border/shadow, max-width1040px and original /assistant destination.

Added standalone #tentang-kami section with all requested text, purpose, six services and development commitment. Two-column editorial layout on desktop; one column on phones. No extra people/statistics. Existing local font used. New footer groups brand, navigation, guidance and portal access, preserves academic/simulation disclaimer. Base introduces an overridable footer_content block; the new footer content is restricted to home.html. Other page footers retain their previous content.

Changed this iteration: frontend/templates/public/home.html, frontend/templates/base.html, frontend/static/css/main.css, new frontend/static/images/healthcare-journey.png, scripts/check_lower_landing.py, qa/lower-landing artifacts. No backend/database/authentication or routing changes.

Actual checks:
- .venv/bin/python -m unittest tests.test_render_routes: 1 test passed (covers seeded public/citizen/admin routes), 2.701s. Existing post-success SQLite ResourceWarning.
- BROWSER_EXECUTABLE=/tmp/sw-browsers/chromium-1248/chrome-linux64/chrome .venv/bin/python scripts/check_lower_landing.py: passed at1366x768,1440x900,1920x1080,768x1024,375x812,360x800. Uses temporary SQLite and server.
- Three stages/six services, help action, all footer destinations, asset availability, responsive column counts and no horizontal overflow: passed. No JavaScript exceptions observed.
- Actual desktop journey/About/footer and mobile journey/About/footer screenshots inspected. Screenshots use real viewport captures to avoid sticky-header artifacts from element screenshots.
- git diff --check: passed.

For local review: .venv/bin/python scripts/preview.py → http://127.0.0.1:5055.
