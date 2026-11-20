# Landing page viewport verification

Background: supplied PNG copied without alteration to frontend/static/images/sehatwarga-hero.png; served successfully (HTTP 200). Source image remains in image/.

Changed: frontend/templates/public/home.html, frontend/static/css/main.css, new static image. Existing hero and service links/content retained. Landing-specific navbar is 68px. Desktop hero uses 44svh with intrinsic content growth; service cards use four equal columns, tablet two, phone one. Existing guide/search/help sections remain below the first screen. No content clipping or fixed page height.

Actual Chromium + disposable SQLite preview checked at 360x800, 375x812, 768x1024, 1024x768, 1366x768, 1440x900, 1920x1080. All passed asset availability, three hero links present, and document no horizontal overflow. At desktop widths all four cards share one row and their bottom edges fall within the viewport. Screenshots saved alongside this file. Desktop 1366/1440 and mobile 375 screenshots visually inspected; copy remains clear and illustration sits right on desktop and below copy on phones.

`.venv/bin/python -m unittest tests.test_render_routes`: 1 test passed, covering seeded public/citizen/admin routes. A SQLite ResourceWarning occurred after successful completion. `git diff --check`: passed.

Verification is scoped to landing layout and route rendering. No new end-to-end authentication, payment, or scan verification performed for this CSS/template change.
