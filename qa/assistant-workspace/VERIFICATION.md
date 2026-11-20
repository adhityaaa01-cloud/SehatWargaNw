# SehatWarga assistant workspace redesign

Three-column desktop layout: 250px identity/session sidebar, flexible chat, 260px quick-service/information panel. Compact 64px existing application header, white panels, subtle borders, local project font. At <=1023px side panels become native disclosure elements above/below the chat. Composer stays inside the chat viewport and grows with input; attachment/preview area scrolls when necessary. VisualViewport resize handling and a 375x500 check approximate reduced screen space, not a physical mobile keyboard test.

Welcome uses the five requested question labels. All call the existing send mechanism; administrative preset payloads use phrasing recognized by current backend intent/safety rules. Manual typed messages are unchanged. Welcome hides when a conversation starts, suggestions move into a disclosure, and the current-session label uses the first question. No persistent history/localStorage was added. Percakapan Baru reloads the existing assistant route; no invented reset/delete API or fake historical records.

Status: fallback configuration displays Mode panduan lokal. Other configurations display Ketersediaan AI belum diperiksa. Busy status reflects a current request; no provider health endpoint exists, so external availability is never claimed. Existing safe textContent/plain-text rendering retained; no unsafe HTML or new Markdown parser. Existing structured facility and scan content retained, with raw OCR inside a disclosure. Camera/gallery inputs, CSRF, preview, scan correction/confirmation paths and retry behavior retained. Scroll follow respects readers of older messages, including scan completion.

Quick links point to existing facility/service/contribution routes (admin mappings use admin lists; guests follow existing login redirects). Right panel explains portal guidance, uploads and privacy. No backend, database, endpoint contracts, auth rules, framework or persistent storage changes.

Changed this task:
- frontend/templates/assistant/chat.html
- frontend/static/css/assistant.css (existing conflicting rules consolidated)
- frontend/static/js/assistant.js
- scripts/check_assistant_workspace.py
- qa/assistant-workspace artifacts
Existing user edits to AI/scan backend and unrelated landing files were preserved.

Actual validation:
- .venv/bin/python -m unittest tests.test_render_routes tests.test_medicine_scan tests.test_redesign_ai: 47 tests passed.
- BROWSER_EXECUTABLE=/tmp/sw-browsers/chromium-1248/chrome-linux64/chrome .venv/bin/python scripts/check_assistant_workspace.py: passed at1440x900,1366x768,1920x1080,1024x768,768x1024,375x812,360x800,375x500.
- Checked one h1, no horizontal overflow, desktop column separation, visible composer bottom, collapsed mobile panels, welcome→conversation, suggestions disclosure.
- All five suggestions verified against actual backend response intents. Nearest-facility request shows explicit location action without automatically requesting coordinates.
- New conversation resets the visible conversation. Upload preview and cancel verified on phone as well as desktop; capture input retained. Scan-result disclosure tested with a mocked scan response; actual OCR/candidate validation covered by medicine-scan tests, not a live OCR accuracy check.
- Server error/retry, escaped script input, long-thread scroll preservation, quick-link destinations and no JavaScript exceptions: passed.
- Desktop welcome/conversation and mobile screenshots visually inspected and refined. git diff --check passed.
- Camera hardware capture, external AI provider availability, and live map tiles not independently verified. External Leaflet stylesheet can require network. No screenshot reference file was available locally; composition follows the three-column requirements supplied in the task.

Run .venv/bin/python scripts/preview.py then open http://127.0.0.1:5055/assistant.
Screenshots with width-height in filename are final; older width-only captures are earlier iterations.
