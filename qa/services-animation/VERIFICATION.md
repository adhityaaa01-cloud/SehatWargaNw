# Quick Services centering and entrance animation

Changed only frontend/static/css/main.css and frontend/static/js/main.js. Wrapper now uses margin-inline:auto, width calc(100% - 64px) and max-width:1400px; existing 23:77 panel/grid ratio and 24px gap retained. Tablet/phone wrapper remains full width with existing container padding.

Vanilla IntersectionObserver observes each service card at 15% visibility and immediately unobserves it. Native Element.animate animates translateX(40px) → 0 and opacity 0 → 1 for 680ms with cubic-bezier(0.22, 1, 0.36, 1). Reverse delays 330/220/110/0ms produce Pengaduan → Iuran → Pengajuan → Kepesertaan. Only transform and opacity animate. Default HTML/CSS remains visible without JS, IntersectionObserver or animation API. Reduced motion skips animation; changing to reduced motion cancels active animations. Keyboard focus cancels the focused card's entrance.

Actual Chromium isolated SQLite preview checks passed at 360x800, 375x812, 768x1024, 1024x768, 1366x768, 1440x900, 1920x1080. Wrapper left/right margins equal; desktop panel and four cards remain side-by-side and within viewport. No horizontal overflow. 1366 and 1440 screenshots visually inspected. Service destinations and click actionability passed; no JS/section asset errors (existing favicon 404 excluded).

Additional instrumented browser run verified actual keyframes, delays, finish-event order, no replay after scrolling away/back, and fully visible non-animated cards in separate reduced-motion, JavaScript-disabled, and IntersectionObserver-disabled contexts. All passed. git diff --check passed. No hero, navbar, template, backend, authentication or routing changes.
