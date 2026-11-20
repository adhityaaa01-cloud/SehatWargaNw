# Hero → Quick Services background transition

Changed only frontend/static/css/main.css: removed hero bottom border, added a 56px non-interactive bottom-edge gradient ending at #eff8f6, and added a matching top-to-bottom gradient over the existing mint-wave image in Quick Services. Hero copy sits above the overlay. Existing images, card rules, grid, text, links, and backend unchanged.

Chromium with temporary SQLite preview passed at 360x800, 375x812, 768x1024, 1024x768, 1366x768, 1440x900, 1920x1080. No horizontal overflow; desktop service cards remain in one row within viewport; asset checks, link actionability/destination checks passed. No JavaScript exceptions or section asset failures. Existing favicon 404 excluded as previously documented.

Visually inspected desktop hero-1366.png and mobile-seam.png (scrolled to show the actual join). Both show a soft continuous mint transition with the illustration visible, readable copy and white cards. Screenshots in this directory. git diff --check passed.
