# EMU Smart Transit

A working Django REST + React university transit application with anonymous student access, staff operations, centralized Traccar polling and an isolated five-vehicle simulator. Built for approximately five physical buses whose service lines change through transactional assignments.

**This repository contains demonstration geography, not an approved operational network.** The current official PDF is included in `docs/reference/2026-27-fall.pdf`. Verified timetable facts and demonstration map data are stored separately. No GPS hardware or university deployment has been verified.

## Start with Docker

Install Docker Engine/Desktop with Compose, then from the repository root:

```powershell
Copy-Item .env.example .env
# Edit .env: replace SECRET_KEY and POSTGRES_PASSWORD with strong random values.
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
docker compose exec backend python manage.py createsuperuser
```

Open **http://localhost:8080**. Staff sign-in is at `/staff`; the detailed Django administration is at `/admin/`. No default account or committed password exists. `createsuperuser` prompts for your chosen credentials. For ordinary dispatchers, create an active staff account through Django admin. All active staff can operate the transportation dashboard; superuser access is for account administration.

The development override seeds the dataset and starts the simulator automatically. Start, pause, reset, change speed or select outage/delay/reassignment scenarios in **Staff → simulation**. Every demonstration bus and ETA is labelled. The second campus service is an inactive unverified line placeholder, with no invented route or schedule.

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f gps-worker
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

Do not add `-v` to `down` unless you intend to delete the persistent databases.

If an initial build reports `ReadTimeoutError` while downloading from `files.pythonhosted.org`, retry the same Compose command. The backend build allows a 180-second network timeout and ten retries for slow connections. Initial image and dependency downloads can take several minutes; downloaded image layers are reused on subsequent attempts.

## Start without Docker (Windows PowerShell)

Python 3.12+ and Node 24 are used by CI. SQLite is supported for local development/tests; production uses PostgreSQL. The launcher can install dependencies and prepare the demo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-local.ps1 -Setup
```

Or use the explicit commands below. Backend terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
$env:DEBUG='true'
$env:DEMO_MODE='true'
python backend/manage.py migrate
python backend/manage.py seed_demo
python backend/manage.py createsuperuser
python backend/manage.py runserver 127.0.0.1:8000
```

GPS worker terminal, using the same Python environment:

```powershell
.\.venv\Scripts\Activate.ps1
$env:DEBUG='true'
$env:DEMO_MODE='true'
python backend/manage.py poll_gps --provider simulation
```

Frontend terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/api`, `/admin` and `/static` to Django. Browser geolocation works on loopback or HTTPS and is requested only after clicking the location button. Denying permission does not block the app. Student coordinates are held only in browser memory.

For Linux/macOS, activate with `source .venv/bin/activate` and replace the PowerShell environment assignments with `export DEBUG=true DEMO_MODE=true`. Django does not automatically load `.env` in native local runs; Compose loads it. Native production operators must export the variables explicitly.

## Features and architecture

- React/TypeScript/Vite, Tailwind, React Leaflet, React Router, TanStack Query and Lucide. Mobile map and details panel; desktop collapsible sidebar. Student map, routes, stops, timetable and notices. English/Turkish navigation and student messages use one translation dictionary.
- Django/DRF, PostgreSQL in Compose, normalized relational models and migrations. Public projections omit registration plates, tracker identifiers, IMEIs and position history. Staff API uses Django session authentication with CSRF checks.
- One centralized provider worker polls Traccar or simulates fixes. Public requests read stored latest positions and never contact a GPS provider. Validations reject invalid/future fixes and prevent older/duplicate fixes from replacing the latest one.
- One active assignment per physical bus, enforced in the database. Assignment replacement locks the bus and closes the prior assignment transactionally. Routes own independent geometry and ordered stops; combinations are never inferred from location or produced by concatenating lines.
- ETA projects onto assigned route segments and uses cumulative route distance, recent progress, smoothed speed and stop dwell. Heading and recent fixes disambiguate overlapping segments. Unverified real routes, stale/offline fixes, completed trips, deviations and wrong-way movement suppress estimates. Demonstration estimates have low confidence.
- Staff dashboard: overview, device association, bus/line/route/stop/schedule/trip/exception/notice editors, map point selection, ordered route stops, assignment operations, validated preview/import and simulator controls. Django admin supplies account management and read-only audit/assignment history.
- Nginx routes requests to frontend/backend and serves collected static files; optional Caddy terminates HTTPS. PostgreSQL and Traccar have separate persistent volumes. No PostGIS dependency is needed at this scale: the baseline performs bounded local geographic calculations in metres.

```text
backend/                 Django config, migrations, providers, ETA, APIs and tests
frontend/                React application, unit tests and Playwright workflows
infrastructure/          Nginx, Caddy and Traccar configuration
scripts/                 Local launcher, browser fixture server and HTTP load test
tests/                   Test documentation
docs/reference/          Official PDF, reviewed timetable and review image
docs/                    API, operations, hardware guide and implementation status
.github/workflows/       PostgreSQL tests, frontend build, browser tests and audits
docker-compose*.yml      Persistent production topology and isolated demo override
```

## Tests

```powershell
$env:DEBUG='true'
$env:DEMO_MODE='true'
python backend/manage.py test transit
python backend/manage.py makemigrations --check --dry-run
cd frontend
npm ci
npm run build
npm test
npx playwright install chromium
npm run test:e2e
npm audit --audit-level=high
```

Playwright owns ports 8000 and 5173: stop other local servers first. It uses a separate ignored `backend/e2e.sqlite3`, generates a test-only password in process memory, creates its test user and runs a GPS worker. Test tracking thresholds are shortened to 3/7 seconds. No real Traccar or university credentials are required. Five viewport sizes are exercised: 375, 390, 768, 1024 and 1440 pixels. Screenshots and failed traces go to ignored test results.

With an authorized local backend running, measure HTTP behavior:

```powershell
python scripts/load_test.py --requests 100 --concurrency 10
```

This is a small functional concurrency sample, not proof of thousands of users. DRF throttles anonymous requests at 120/minute per client; shared university NAT and proxy forwarding require capacity review. Nginx adds ingress limits. See [implementation status](docs/IMPLEMENTATION_STATUS.md) for measured outcomes and verification limits.

## Connect Traccar and physical trackers

Use a separate production database; never promote demo assignments or coordinates. Keep `DEMO_MODE=false`, `GPS_PROVIDER=traccar`. Configure `TRACCAR_URL`, `TRACCAR_USER` and `TRACCAR_PASSWORD` on the backend/worker only. Open Traccar through an SSH tunnel to its loopback-bound port 8082, create its initial administrator, then create a limited read-only service user with access to university devices. Register each tracker in Traccar and associate its numeric device ID and private identifier in **Staff → devices**. The worker calls `/api/positions` using server-side Basic authentication over the private Compose network (HTTPS for a remote Traccar service), converts knots to km/h and ignores unknown devices.

```powershell
docker compose exec backend python manage.py poll_gps --provider traccar --once
docker compose logs -f gps-worker
```

The FMC920 is listed by Traccar under **teltonika / port 5027**. Do not buy or wire a device solely from that listing: confirm regional cellular compatibility, SIM/APN, vehicle voltage, manufacturer wiring and security features. See [hardware integration](docs/HARDWARE.md) and [operations/deployment](docs/OPERATIONS.md).

## University release requirements

Obtain transportation approval for every line and timetable, semester dates, Saturday ambiguities, second campus service, surveyed geometry/stops and holiday calendar. Install and test hardware and real journeys. Validate ETA against observed arrivals. Train staff, agree a GPS retention policy and obtain university IT/DNS/firewall/HTTPS/tile-provider approvals. Production release requires the checklist in [operations](docs/OPERATIONS.md). No actual university infrastructure is deployed by this repository.
