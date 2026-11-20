# Quick Services information panel

Updated frontend/templates/public/home.html and scoped Quick Services rules in frontend/static/css/main.css. Desktop container max-width 1480px, with 23:77 information/services columns and a responsive gap. Four existing service cards retain their icons, titles, descriptions, and destinations. Added requested label, heading, family-service description, heart-pulse outline SVG, and supporting text. Card padding 18px; title rows reserve consistent height. Background mint wave and hero unchanged. At <=1023px the information panel is above a two-column grid; at <=599px cards use one column.

Actual Chromium preview with disposable SQLite passed at 360x800, 375x812, 768x1024, 1024x768, 1366x768, 1440x900, 1920x1080. Checked panel/grid separation, no document horizontal overflow, and desktop cards in a single row within viewport. Screenshots visually inspected at 1366, 1440 and mobile 375. Card click actionability and destination HTTP requests passed at 1440. No JavaScript exceptions, failed section assets or console errors; pre-existing favicon.ico 404 explicitly excluded. git diff --check passed.

Screenshots in this directory show actual rendered application. No backend/database/authentication changes or new backend tests for this presentation-only change.
