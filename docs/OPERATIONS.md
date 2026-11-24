# Deployment and operations

## University Linux server

Use a clean production database. Copy `.env.example` to `.env`, set strong distinct secrets and permissions (`chmod 600 .env`), approve hosts/origins, choose a licensed production tile provider and configure its attribution. Vite variables are public build-time values; never put a secret tile token or tracker credential into them. Public OpenStreetMap tiles are a local development default, not an unlimited production service. Review provider attribution, caching and traffic policy before release.

Set `DEBUG=false`, `DEMO_MODE=false`, `GPS_PROVIDER=traccar`, approved Traccar credentials, `PUBLIC_HOST` and `ACME_EMAIL`. Run:

```sh
docker compose --profile https up --build -d
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py check --deploy
docker compose exec backend python manage.py poll_gps --provider traccar --once
docker compose ps
curl -fsS https://bus.emu.edu.tr/health/
```

The one-shot migrate service completes schema migrations and static collection before backend/worker startup. Frontend assets are built into its Nginx image. Caddy obtains/renews HTTPS certificates and proxies to private Nginx. DNS and incoming 80/443 must be approved and reachable for certificate issuance. Proxy port 8080 and Traccar UI 8082 bind only to server loopback; databases have no published port. Only TCP 5027 is published for the selected hardware protocol. Remove that publication if no tracker listener is needed or select another protocol only after compatibility verification. Restrict host firewall, database credentials and SSH access. Do not expose Docker management APIs.

Do not trust arbitrary forwarded-proto headers from the internet. The provided public path is Caddy → Nginx → Django; Nginx is loopback-bound on the host, and backend is private. Keep these trust boundaries if modifying the stack. Secure cookies are enabled when DEBUG is false. HSTS is emitted in production; do not run production mode without HTTPS. Redirect HTTP at Caddy. The optional Django `SECURE_SSL_REDIRECT=true` requires a TLS-aware internal health check; leave it false in this topology because Caddy owns redirects.

## Data commissioning

The demo seed refuses to run without explicit demo mode and does not overwrite existing records. Never seed a production database with demonstration data. Use staff editors or validated timetable import for approved real records. Required ordered data entry: lines → stops → independent routes and line associations → route-stop order/distances → schedules/trips → devices/buses → live assignments. Verified source JSON may guide import, but IDs must match the production routes. Confirm effective semester dates, holiday records and Saturday unresolved departures with staff. Set route verification only after independently reviewing geometry/stops. Assigning an unverified service shows its real location but suppresses ETA.

Active assignments authorize public exposure. Staff must end services after duty. Production additionally hides completed/cancelled trips, deactivated services, demo records and assignments older than `PUBLIC_SERVICE_MAX_HOURS` (16 default). This is a safety cutoff, not an inferred university operating timetable. Tune it to approved operations and train staff accordingly.

## Retention, backup and restore

`GPS_HISTORY_DAYS=7` is a configurable starting value, not an approved university retention policy. Agree the actual period and access rules with university stakeholders. Schedule the following through the server's approved scheduler:

```sh
docker compose exec -T backend python manage.py prune_positions
```

The latest fix per bus is retained even when old, to show an explicit offline timestamp. Historical movement is never exposed publicly. Assignment/audit records have separate operational retention requirements; this baseline does not automatically erase those records. Student geolocation is never sent to the application server or saved in its database.

Create encrypted off-host backups and rehearse restoration. Avoid placing database passwords in shell arguments:

```sh
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/transit.dump
```

For restoration, first stop backend/worker, restore into a clean target database after checking its identity, then migrate and restart:

```sh
docker compose stop backend gps-worker
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backups/transit.dump
docker compose run --rm migrate
docker compose up -d backend gps-worker
```

Restoration overwrites the selected database: obtain operational authorization and verify the backup/target before running it. Back up Traccar independently. For the bundled persistent H2 setup, stop Traccar before snapshotting its `traccar_data` volume; preserve its XML configuration, image version and volume ownership. For larger production operations use Traccar's documented PostgreSQL configuration with a distinct database/account, not the application's tables. Preserve Caddy certificate volumes and protect configuration secrets.

## Monitoring and security review

Use `docker compose logs --since 10m backend gps-worker traccar proxy` and staff overview. The provider worker records attempts, successes and failure type without logging credentials. Worker heartbeat expires after a configurable-interval-aware limit; bus freshness derives from valid GPS fix time. Run exactly one worker for each selected provider. Investigate unknown devices separately from connectivity failure.

Nginx limits API/login ingress; DRF throttles clients. The default Django cache is per process and is not a distributed rate limiter, so Nginx is the shared ingress control. Review shared campus NAT impact and use trusted proxy address handling if deployed behind another load balancer. No untrusted CORS origin is permitted. Set explicit host and CSRF origins. Back up, lock dependency versions, run dependency audits and review pinned container image releases before upgrades. Audit logs are append-only through exposed administration; a database operator can still modify them, so use external log shipping if tamper resistance is required.

## Release checklist

- [ ] University IT authorization, approved domains, DNS, TLS, firewall and server access.
- [ ] Current PDF and semester validity approved; Saturday differences resolved; second campus line confirmed.
- [ ] Stops, all directions and each combined route independently surveyed and verified.
- [ ] Tracker/SIM purchased, installed, registered and mapped; real fixes verified for all participating buses.
- [ ] Real journeys tested: GPS coverage, reporting cadence, wrong-way/deviation behavior, ETA observations and confidence calibrated.
- [ ] Staff permissions/accounts and assignment start/end training approved; operations handbook handed over.
- [ ] Production demo mode disabled, no demo assignments/devices/stops present, secrets replaced, least-privileged integration user.
- [ ] Production tile contract/attribution/quotas approved.
- [ ] Holiday/exception calendar and incident announcements entered; offline/outage workflow rehearsed.
- [ ] PostgreSQL tests, browser suite, container startup and actual deployment smoke tests pass in university staging.
- [ ] Backups/restoration rehearsed; retention and monitoring agreed; measured load meets expected student traffic.

None of these external approvals or hardware checks is implied by software tests.
