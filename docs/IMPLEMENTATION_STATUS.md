# Implementation status

Updated 2026-11-24. Software implementation is complete enough to run locally; university operational acceptance remains external and unverified.

## Implemented phases

| Phase | Delivered |
| --- | --- |
| Foundation | Django/DRF, React/TypeScript/Vite, Tailwind, normalized database models, initial migration, authentication, five-vehicle repeatable demo seed and Docker topology |
| Core tracking | Provider abstraction, centralized Traccar worker, simulator, validated monotonic GPS ingestion, latest-position table, integration heartbeat, student Leaflet map and 5-second HTTP polling |
| Transportation logic | Many-to-many service lines, independent combined routes, ordered/repeated stops, transactional assignments, route-projection ETA, timetables and date-specific service exceptions |
| Administration | Staff overview, assignment activation/replacement/end/cancel, fleet/device/line/route/stop/schedule/trip/exception/notice editors, map geometry/stop input, validated schedule preview/import, simulation controls, Django account management and audit history |
| Quality/deployment | Backend domain/API/security tests, frontend unit tests, Playwright workflows and five screen widths, concurrency sampler, dependency audits, Compose, Nginx/Caddy, CI and operating guides |

## Executed validation

- Django migration and idempotent demo seeding executed successfully; `check` and migration-drift checks passed.
- Backend: **44 tests passed** on Django 6.0.7 and patched DRF 3.18.3. Covers models/constraints, combined route API creation, assignment replacement/rollback/conflicts, trip validity, GPS rejection/ordering, provider failure, freshness, ETA/loops/deviations, schedules/holidays, validated import/duplicate rows, CSRF, staff authorization, privacy and seed idempotency.
- Frontend: TypeScript and Vite production build passed; **8 unit tests passed**, including combined filters, translation parity and cached-position aging during API failure. Bundle split into application, map and React/router chunks; no chunk-size warning in the final split build.
- Browser: **8 Playwright tests passed in 23.5 seconds** in the final run. Real Chromium exercises student navigation/filter/stop/timetable/notices/language flow; staff login, vehicle creation and combined assignment replacement visible in a student tab; GPS fix updates, pause/offline warning and resumed tracking; API error and denied geolocation; no horizontal overflow at 375, 390, 768, 1024 and 1440px. Desktop/mobile screenshots were inspected. External map tile loading was unavailable in this environment; marker/path interaction still worked and a tile failure message is implemented.
- Compose production/development configuration parses successfully. Docker image builds and development startup are now verified: PostgreSQL and backend healthy; migrations/demo seed completed; frontend, Nginx, simulator and Traccar running. `/`, `/health/` and `/api/v1/buses/live/` returned HTTP 200 through `http://localhost:8080`, with five live demonstration buses. The backend build now uses a 180-second pip timeout and ten retries after a slow-download timeout was encountered. **All 44 backend tests also passed against container PostgreSQL on Django 6.0.10 in 7.805 seconds.** HTTPS/university deployment and remote CI remain unverified.
- Real HTTP sampler against native Windows/Django development server and SQLite: **100/100 HTTP 200**, **10 concurrent clients**, **1.53 seconds elapsed**, **140.25 ms median**, **215.84 ms p95**. This is a small functional sample, not a production capacity claim.
- Python dependency audit detected five findings in DRF 3.16.1; upgrading to DRF 3.18.3 resolved them. **Final pip-audit: no known vulnerabilities. npm audit: zero vulnerabilities.** Container images have not been security-scanned locally.

## Source verification

The checkout was empty and the requested reference PDF was absent. The current official PDF was fetched from EMU's official Bus Services page, saved under `docs/reference/` and visually reviewed using a local rendering. Weekday external departures, campus departures/returns and matching paired Saturday departures were transcribed. The source's mismatched Saturday Line 1/4 and Line 2/5 columns are explicitly recorded for departmental review; unmatched departures are not invented as combined journeys. Import validity begins on the review date; actual semester dates require confirmation.

Line names/classifications and external colour families are sourced independently from geometry. Display hex values represent the PDF stroke colours, not a published EMU brand standard. All seeded stop coordinates, travel paths, active vehicles and ETA demonstrations are clearly marked as demonstration data. Real published timetable routes have no invented geometry.

## Known limits and follow-up

- No real tracker or SIM/APN has been connected. The local Traccar container starts successfully; external tracker connectivity and end-to-end physical GPS commissioning remain unverified. REST integration is tested using controlled provider responses.
- Backend tests pass on both native SQLite and container PostgreSQL. Simultaneous staff operations use PostgreSQL row locks and a database uniqueness constraint; a dedicated multi-client race/load test of assignment replacement remains a staging check.
- The ETA is an explainable baseline with route matching, recent progress/heading and smoothed speed; it is not a calibrated traffic model. Repeated/overlapping segment ambiguity can suppress estimates. Demonstration loops can complete/reset, and confidence stays low. Real-world accuracy must be measured.
- Base map tiles require network connectivity and an approved provider. If tiles fail, the UI warns and bus/service data remain accessible. Production OSM traffic suitability is not assumed.
- Student navigation/messages support English/Turkish. Staff operations and some detailed diagnostic/source text are English; full editorial translation remains a follow-up.
- Route editing supports ordered map clicks or JSON coordinate import. It is not automatic road snapping, and no route is treated as independently surveyed merely because it is drawn on a map.
- Timetable import accepts validated JSON, with preview. It does not automatically interpret arbitrary PDFs/CSV or infer stop arrival times from departure columns.
- Staff permissions are deliberately simple: active staff can operate the full transportation dashboard; account administration requires the appropriate Django privileges. More granular dispatcher/planner scopes can be added if the university requires them.
- DRF's local memory throttles are per process; Nginx supplies common ingress limiting. Shared campus NAT and any additional reverse proxy need university-specific configuration.
- Traccar uses a separate persistent H2 store in the supplied small-fleet configuration. University IT should select and rehearse its backup/database strategy before release.
- No deployment, DNS changes, account messages or hardware purchases were performed.

## Remaining external acceptance dependencies

GPS hardware and compatible regional data SIMs; independently surveyed stops, directions and every combined path; approved second campus service; semester end/start dates and public holiday calendar; Saturday column clarification; real journey/ETA validation; transportation staff training; university IT hosting/HTTPS/DNS/firewall approval; licensed tile provider and agreed retention, backup and monitoring policy.

Use the release checklist in `docs/OPERATIONS.md`. None of those university approvals or physical tests is marked complete.
