# Smoother motion and vertical centering

Scoped changes: main.css vertically centers the Quick Services wrapper in the available section space on desktop (flex align-items:center). This moves content down naturally without fixed offsets or changing hero/mobile layout. main.js entrance duration now 820ms, stagger 100ms, easing cubic-bezier(0.22,0.75,0.28,1) for a gentler start; direction, reverse order, once-only observation and accessibility fallbacks retained.

Chromium + disposable SQLite preview: seven viewport checks passed (360,375,768,1024,1366,1440,1920 widths); no horizontal overflow and desktop cards within viewport. Actual 1366x768 and 1440x900 screenshots visually inspected. Instrumented browser check passed: updated delays 300/200/100/0, duration 820ms, finish order right-to-left, no replay on return scroll, reduced motion/no-JS/no-IntersectionObserver visible fallback. Existing destination/actionability checks passed. git diff --check passed. No unrelated changes.
