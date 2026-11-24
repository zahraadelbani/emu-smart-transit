# API contract

Base path `/api/v1/`. JSON, ISO 8601 timestamps, Famagusta service dates, kilometres/hour for normalized speeds and `[latitude, longitude]` for route points. This is not GeoJSON coordinate order. Public list responses use `{count,next,previous,results}` with `limit` (default 100) and `offset`. Live responses use `{results,server_time,demo_mode}`. Validation failures return HTTP 400, unauthorized staff requests 403, unavailable records 404 and throttling 429. `GET /health/` checks database connectivity (200/503).

| Method/path | Behavior |
| --- | --- |
| GET `lines/` | Active service lines and source verification flags; second placeholder excluded while inactive |
| GET `routes/` | Independent geometry, lines and ordered stops; `line=1` includes combinations |
| GET `stops/` | Active stops, accessibility and geography verification |
| GET `stops/{id}/arrivals/` | Live route-distance estimates, unavailable-bus reasons and explicitly labelled route-origin departures |
| GET `buses/live/` | One entry per assigned active bus; last-known position, timestamp, status, lines and ETA |
| GET `schedules/` | Recurring schedules; filter `service_day`, `direction`, `route_id`; `date=YYYY-MM-DD` applies effective dates, service day and exception rules |
| GET `announcements/` | Published, unexpired service notices |
| GET `service-status/` | Demo flag, timezone, configured thresholds, today's exceptions and source limitations |
| GET `auth/session/` | Session/staff state and CSRF token; sets CSRF cookie |
| POST `auth/login/` | `{username,password}`, requires `X-CSRFToken` matching cookie even for anonymous login |
| POST `auth/logout/` | CSRF-protected staff logout |
| GET `staff/overview/` | Fleet/assignment counts, active public services and worker heartbeat health |
| POST `staff/assignments/` | `{bus_id,route_id,trip_id?}` activate/replace; `{action:"end"|"cancel",assignment_id}` close |
| GET/POST `staff/simulation/` | Explicit demo mode only; `{running,speed,scenario,reset?}` |
| POST `staff/import-schedules/` | `{rows:[...],commit:false}` validate preview; resubmit unchanged rows with `commit:true` to atomically import |

Authenticated staff CRUD resources: `staff/buses/`, `devices/`, `lines/`, `routes/`, `route-stops/`, `stops/`, `schedules/`, `trips/`, `exceptions/`, `announcements/` (all under `staff/`). Standard GET, POST, PATCH, PUT and DELETE. Existing records referenced by service history cannot be deleted: deactivate them instead. Routes accept `line_ids:[1,2]` and expose nested line/stop details. Stops are independently managed; route-stops carry `route`, `stop`, `sequence`, `distance_m` and `dwell_seconds`. Repeated stop IDs are allowed at distinct sequences. Cumulative distances must increase in sequence order.

Public responses never include device IDs, IMEIs, credentials, registrations or unbounded position history. Production hides demo buses/stops/geometries, simulation fixes and assignments older than `PUBLIC_SERVICE_MAX_HOURS` (default 16). End assignments promptly after service; completed/cancelled trips and disabled services are hidden. Staff operations should occur on the same origin; CORS is intentionally not enabled. DRF's browsable API provides interactive field documentation locally; do not treat its presence as authorization.

Holiday/cancellation records default to closed. A route-specific exception overrides a global one; an enabled exception allows the route's configured service-day schedules on that date, including explicit Sunday schedules. Temporary timetable changes use additional date-bounded Schedule rows and an appropriate exception/notice; no missing departure times are fabricated.
