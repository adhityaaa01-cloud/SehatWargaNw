# Hero typography and entrance motion

Scoped to hero: Source Sans 3 Latin variable WOFF2 (28,872 bytes), self-hosted with font-display:swap, weights 400–700, system sans-serif fallback. No global font replacement or new frontend dependency. Source: Google Fonts Source Sans 3 CSS and fonts.gstatic.com WOFF2. License bundled as frontend/static/fonts/sourcesans3-OFL.txt from https://github.com/google/fonts/tree/main/ofl/sourcesans3 (SIL OFL). Original Plus Jakarta Sans remains elsewhere.

Headline 700 / line-height 1.1 / -1px tracking: 57.372px at 1366, 60.48px at 1440, 64px at 1920; actual browser measured two lines at each. Text area increased to min(62%,760px) after initial 1440px check revealed excess wrapping. Description 19px/1.6 (mobile16px), label13px/650, actions16px/600, disclaimer13px. Tablet headline42–48px, phone34–40px. Illustration asset, navigation and all three action destinations unchanged.

Native animate on five hero elements: translateX(-32px)/opacity0 to original position/opacity1; duration650ms, cubic-bezier(0.22,1,0.36,1), delays0/110/220/330/440ms. Runs at DOMContentLoaded only; scroll never retriggers. Reduced motion skips/cancels it. Keyboard focus cancels active hero motion. Default CSS keeps all copy visible without JS/animation support.

Actual Chromium with temporary SQLite: passed at 1366x768, 1440x900, 1920x1080, 1024x768, 768x1024, 375x812, 360x800. No horizontal overflow. Desktop 1366/1440/1920 and phone375 screenshots visually inspected. Local font loaded successfully, original three action paths checked, actual keyframes/timing/finish order verified, no replay on scroll verified, reduced-motion and JS-disabled visibility verified. No JavaScript exceptions observed. Backend page render unittest passed. git diff --check passed.

Reproduce browser QA:
BROWSER_EXECUTABLE=/path/to/chromium .venv/bin/python scripts/check_hero_typography.py

Changed this iteration: frontend/static/css/main.css, frontend/static/js/main.js, frontend/templates/public/home.html (disclaimer class only), new local font/license, scripts/check_hero_typography.py, and qa/hero-typography artifacts. No backend, database, routes or authentication edits.

## Hero alignment refinement (supersedes earlier layout/motion details)

All five elements now share one .hero-content parent, including the label formerly outside it. Hero container uses two-column CSS Grid, with the illustration supplied by the existing right-side background. Text column uses flex-column/align-items:flex-start/text-align:left. Removed percentage width rules on individual elements, the disclaimer margin utility, and redundant desktop spacing overrides; margins now follow a single scoped rhythm. Desktop copy aligns to the top padding rather than vertical centering. Tablet/phone switch to one text column with the existing illustration beneath. A narrow-desktop-only white overlay protects readability at1024–1199px; source illustration unchanged. Navbar and Quick Services styles untouched.

Motion now translates the parent column once (-32px→0,650ms), while children fade sequentially at0/110/220/330/440ms. This keeps the horizontal start identical throughout entrance rather than translating each element independently. Reduced-motion, no-JS visibility and keyboard focus cancellation retained.

Browser regression script updated to assert exactly five immediate content children, all text-align:left, and matching bounding-box x positions within1px. Passed at1366x768,1440x900,1920x1080,1024x768,768x1024,375x812,360x800. Desktop headline remains two lines; actual font sizes unchanged. Native animation instrumentation verified one parent movement plus five opacity animations, correct finish order, no replay, reduced-motion and no-JS fallback. Original button paths unchanged; no JavaScript exceptions or horizontal overflow. Updated screenshots visually inspected at1366,1440,1024 and phone375. RenderRoutes unittest passed again (2.591s); git diff --check passed.

Changed this iteration: frontend/templates/public/home.html, frontend/static/css/main.css, frontend/static/js/main.js, scripts/check_hero_typography.py, and QA artifacts.
