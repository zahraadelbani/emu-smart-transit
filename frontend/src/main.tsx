import React, { useState, useEffect, useMemo } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  NavLink,
  Routes,
  Route as PageRoute,
  Link,
} from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BusFront,
  Map,
  Route as RouteIcon,
  Clock3,
  MapPin,
  Bell,
  LocateFixed,
  Search,
  ChevronRight,
  X,
  Menu,
  ShieldCheck,
  RefreshCw,
  PanelLeftClose,
  PanelLeftOpen,
  Globe,
  Navigation,
} from "lucide-react";
import { useResource } from "./api";
import { messages, type Lang, type Text } from "./i18n";
import type {
  Line,
  Route,
  Stop,
  Bus,
  Schedule,
  Notice,
  List,
  Arrival,
} from "./types";
import { TransitMap } from "./TransitMap";
import { Staff } from "./staff";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import { matchesLine } from "./filter";
import { ageBus } from "./freshness";

export function Badge({ line }: { line: Line }) {
  const rgb = [1, 3, 5]
    .map((i) => parseInt(line.color.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  const luminance = rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  return (
    <span
      className="line-badge"
      style={{
        background: line.color,
        color: luminance > 0.179 ? "#000" : "#fff",
      }}
    >
      {line.code}
    </span>
  );
}
export function State({ state, t }: { state: Bus["status"]; t: Text }) {
  return (
    <span className={"state " + state}>
      <i />
      {t[state]}
    </span>
  );
}
const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: true } },
});

function App() {
  const [lang, setLang] = useState<Lang>(() =>
      localStorage.getItem("language") === "tr" ? "tr" : "en",
    ),
    [menu, setMenu] = useState(false),
    [online, setOnline] = useState(navigator.onLine);
  const t = messages[lang];
  useEffect(() => {
    document.documentElement.lang = lang;
    localStorage.setItem("language", lang);
  }, [lang]);
  useEffect(() => {
    const on = () => setOnline(navigator.onLine);
    window.addEventListener("online", on);
    window.addEventListener("offline", on);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", on);
    };
  }, []);
  const links = [
    ["/", Map, t.map],
    ["/routes", RouteIcon, t.routes],
    ["/timetable", Clock3, t.timetable],
    ["/stops", MapPin, t.stops],
    ["/notices", Bell, t.notices],
  ] as const;
  const status = useResource<{ demo_mode: boolean; timetable_notice: string }>(
    "service-status/",
    30000,
  );
  return (
    <>
      <header className="header">
        <Link to="/" className="brand">
          <span className="brand-icon">
            <BusFront size={25} />
          </span>
          <span>
            EMU <strong>Smart Transit</strong>
            <small>EASTERN MEDITERRANEAN UNIVERSITY</small>
          </span>
        </Link>
        <button
          className="icon-button mobile-menu"
          onClick={() => setMenu(!menu)}
          aria-label="Toggle navigation"
        >
          <Menu />
        </button>
        <nav aria-label="Main navigation" className={menu ? "open" : ""}>
          {links.map(([to, Icon, label]) => (
            <NavLink key={to} to={to} end onClick={() => setMenu(false)}>
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
        </nav>
        <button
          className="language"
          onClick={() => setLang(lang === "en" ? "tr" : "en")}
          aria-label="Switch language"
        >
          <Globe size={16} />
          {lang === "en" ? "TR" : "EN"}
        </button>
      </header>
      {!online && (
        <div className="network-banner" role="status">
          {t.network}
        </div>
      )}
      {status.data?.demo_mode && (
        <div className="demo-banner">
          <ShieldCheck size={16} />
          <strong>{t.demo}</strong>
          <span>{t.demoText}</span>
        </div>
      )}
      <Routes>
        <PageRoute path="/" element={<Live t={t} lang={lang} />} />
        <PageRoute path="/routes" element={<Catalog t={t} lang={lang} />} />
        <PageRoute
          path="/timetable"
          element={
            <Timetable
              t={t}
              lang={lang}
              notice={status.data?.timetable_notice}
            />
          }
        />
        <PageRoute path="/stops" element={<StopPage t={t} lang={lang} />} />
        <PageRoute path="/notices" element={<Notices t={t} lang={lang} />} />
        <PageRoute path="/staff" element={<Staff />} />
        <PageRoute
          path="*"
          element={
            <main className="page">
              <h1>Page unavailable</h1>
              <Link to="/">{t.map}</Link>
            </main>
          }
        />
      </Routes>
      <footer>
        <span>
          EMU Smart Transit <span className="footer-divider">/</span>{" "}
          Transportation Services
        </span>
        <Link to="/staff">
          <ShieldCheck size={14} />
          {t.staff}
        </Link>
      </footer>
    </>
  );
}

function LoadingError({
  loading,
  error,
  t,
  retry,
}: {
  loading: boolean;
  error: unknown;
  t: Text;
  retry: () => void;
}) {
  return loading ? (
    <p className="message">
      <RefreshCw size={18} />
      {t.loading}
    </p>
  ) : error ? (
    <div role="alert" className="message error">
      <p>{t.error}</p>
      <button onClick={retry}>{t.retry}</button>
    </div>
  ) : null;
}
function Filter({
  value,
  onChange,
  t,
}: {
  value: string;
  onChange: (s: string) => void;
  t: Text;
}) {
  return (
    <div className="filters" aria-label="Filter by line">
      {[
        ["all", t.all],
        ["1", "1"],
        ["2", "2"],
        ["4", "4"],
        ["5", "5"],
        ["campus", t.campus],
      ].map(([v, label]) => (
        <button
          key={v}
          aria-pressed={value === v}
          className={value === v ? "selected" : ""}
          onClick={() => onChange(v)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
function useStops() {
  return useResource<List<Stop>>("stops/?limit=500");
}
function useRoutes() {
  return useResource<List<Route>>("routes/?limit=500");
}
function useLocation(t: Text) {
  const [user, setUser] = useState<[number, number] | null>(null),
    [error, setError] = useState("");
  return {
    user,
    error,
    locate: () => {
      if (!navigator.geolocation) {
        setError(t.permission);
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (p) => {
          setUser([p.coords.latitude, p.coords.longitude]);
          setError("");
        },
        () => setError(t.permission),
        { timeout: 10000, maximumAge: 60000 },
      );
    },
  };
}

function ArrivalRows({ arrivals, t }: { arrivals: Arrival[]; t: Text }) {
  return (
    <div className="arrival-list">
      {arrivals.map((a) => (
        <div
          key={`${a.stop_id}-${a.sequence}-${a.bus_id}`}
          className="arrival-row"
        >
          <span>
            <strong>{a.bus_name || a.stop_name}</strong>
            <small>
              {a.demo ? t.demo : "Live estimate"} · {a.confidence} confidence
            </small>
          </span>
          <b>
            {t.arrival} {a.minutes} {t.minutes}
          </b>
        </div>
      ))}
    </div>
  );
}
function StopDetails({ stop, t, lang }: { stop: Stop; t: Text; lang: Lang }) {
  const query = useResource<{
    arrivals: Arrival[];
    unavailable: { bus_id: number; bus_name: string; reason: string }[];
    scheduled_route_departures: Schedule[];
  }>(`stops/${stop.id}/arrivals/`, 5000);
  return (
    <>
      <h2>{lang === "tr" ? stop.name_tr : stop.name_en}</h2>
      <p className="muted">
        {stop.demo ? t.demo : t.verified} ·{" "}
        {stop.accessibility || "Accessibility information unavailable"}
      </p>
      <h3>{t.upcoming}</h3>
      <LoadingError
        loading={query.isLoading}
        error={query.error}
        t={t}
        retry={() => query.refetch()}
      />
      <ArrivalRows arrivals={query.data?.arrivals || []} t={t} />
      {query.data?.arrivals.length === 0 && <p>{t.unavailable}</p>}
      {query.data?.unavailable.map((b) => (
        <p className="muted" key={b.bus_id}>
          {b.bus_name}: {b.reason}
        </p>
      ))}
      {Boolean(query.data?.scheduled_route_departures.length) && (
        <p className="muted">
          Scheduled route departures:{" "}
          {query
            .data!.scheduled_route_departures.map((s) =>
              s.departure_time.slice(0, 5),
            )
            .join(", ")}
          . These are origin departures, not stop arrival times.
        </p>
      )}
    </>
  );
}

function Live({ t, lang }: { t: Text; lang: Lang }) {
  const buses = useResource<{ results: Bus[]; server_time: string }>(
      "buses/live/",
      5000,
    ),
    routes = useRoutes(),
    stops = useStops();
  const status = useResource<{
    thresholds: { live_seconds: number; offline_seconds: number };
  }>("service-status/", 30000);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const [filter, setFilter] = useState("all"),
    [selectedBus, setSelectedBus] = useState<number | null>(null),
    [selectedStop, setSelectedStop] = useState<Stop | null>(null),
    [collapsed, setCollapsed] = useState(false),
    [focus, setFocus] = useState<[number, number] | null>(null);
  const location = useLocation(t);
  const currentBuses = (buses.data?.results || []).map((b) =>
    ageBus(
      b,
      buses.data!.server_time,
      now - buses.dataUpdatedAt,
      status.data?.thresholds.live_seconds,
      status.data?.thresholds.offline_seconds,
    ),
  );
  const visible = currentBuses.filter((b) => matchesLine(b, filter)),
    visibleRoutes = (routes.data?.results || []).filter((r) =>
      matchesLine(r, filter),
    ),
    stopIds = new Set(
      visibleRoutes.flatMap((r) => r.ordered_stops.map((s) => s.stop)),
    ),
    visibleStops = (stops.data?.results || []).filter(
      (s) => filter === "all" || stopIds.has(s.id),
    );
  const bus = currentBuses.find((b) => b.id === selectedBus);
  const selectBus = (b: Bus) => {
    setSelectedBus(b.id);
    setSelectedStop(null);
    setCollapsed(false);
    if (b.position) setFocus([b.position.latitude, b.position.longitude]);
  };
  const selectStop = (s: Stop) => {
    setSelectedStop(s);
    setSelectedBus(null);
    setCollapsed(false);
    setFocus([s.latitude, s.longitude]);
  };
  return (
    <main className="live-layout">
      <section className={"sidebar " + (collapsed ? "collapsed" : "")}>
        <div className="sidebar-heading">
          <span className="eyebrow">MOVE WITH EMU</span>
          <h1>{t.heading}</h1>
          <p>{t.subtitle}</p>
        </div>
        <div className="sidebar-content">
          <div className="section-label">
            <h2>{t.map}</h2>
            <span className="count">{visible.length} buses</span>
          </div>
          <Filter value={filter} onChange={setFilter} t={t} />
          <LoadingError
            loading={buses.isLoading || routes.isLoading || stops.isLoading}
            error={buses.error || routes.error || stops.error}
            t={t}
            retry={() => {
              buses.refetch();
              routes.refetch();
              stops.refetch();
            }}
          />
          {(selectedStop || bus) && (
            <section className="detail-panel" aria-label={t.details}>
              <button
                className="icon-button close-detail"
                aria-label={t.close}
                onClick={() => {
                  setSelectedBus(null);
                  setSelectedStop(null);
                }}
              >
                <X size={18} />
              </button>
              {selectedStop ? (
                <StopDetails stop={selectedStop} t={t} lang={lang} />
              ) : (
                bus && (
                  <>
                    <div className="line-stack">
                      {bus.lines.map((l) => (
                        <Badge key={l.id} line={l} />
                      ))}
                    </div>
                    <h2>{bus.display_name}</h2>
                    <p>
                      {bus.route_name} ·{" "}
                      {t[bus.direction as keyof Text] || bus.direction}
                    </p>
                    <State state={bus.status} t={t} />
                    <p className="muted">
                      {t.updated}:{" "}
                      {bus.position
                        ? new Date(bus.position.fix_time).toLocaleTimeString(
                            lang,
                          )
                        : "—"}
                    </p>
                    <h3>{t.upcoming}</h3>
                    {bus.eta.available ? (
                      <ArrivalRows
                        arrivals={bus.eta.arrivals.slice(0, 3)}
                        t={t}
                      />
                    ) : (
                      <p>{bus.eta.reason}</p>
                    )}
                  </>
                )
              )}
            </section>
          )}
          <div className="bus-list">
            {visible.map((b) => (
              <button
                key={b.id}
                className={"bus-row " + (selectedBus === b.id ? "active" : "")}
                onClick={() => selectBus(b)}
              >
                <span className="bus-symbol">
                  <BusFront size={22} />
                </span>
                <span className="bus-row-main">
                  <span className="bus-title">
                    {b.display_name}
                    <State state={b.status} t={t} />
                  </span>
                  <span className="line-description">
                    {b.lines.map((l) => (
                      <Badge key={l.id} line={l} />
                    ))}
                    <span>
                      {b.lines
                        .map((l) => (lang === "tr" ? l.name_tr : l.name_en))
                        .join(" + ")}
                    </span>
                  </span>
                  <span className="bus-next">
                    {b.trip_status === "delayed" && (
                      <strong>
                        {lang === "tr" ? "Gecikmeli" : "Delayed"} /{" "}
                      </strong>
                    )}
                    {b.eta.available
                      ? `${b.eta.arrivals[0].stop_name} · ~${b.eta.arrivals[0].minutes} ${t.minutes}`
                      : b.eta.reason}
                  </span>
                </span>
                <ChevronRight size={17} />
              </button>
            ))}
          </div>
          {!buses.isLoading && !buses.error && !visible.length && (
            <p className="message">{t.empty}</p>
          )}
          <div className="side-note">
            <Clock3 size={18} />
            <span>
              Updates every 5 seconds
              <small>
                One marker per physical bus, including combined services.
              </small>
            </span>
          </div>
        </div>
      </section>
      <section className="map-area" aria-label={t.map}>
        <TransitMap
          buses={visible}
          routes={visibleRoutes}
          stops={visibleStops}
          onBus={selectBus}
          onStop={selectStop}
          user={location.user}
          focus={focus}
        />
        <div className="map-top-controls">
          <button
            className="map-button"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? t.expand : t.collapse}
          >
            {collapsed ? (
              <PanelLeftOpen size={19} />
            ) : (
              <PanelLeftClose size={19} />
            )}
          </button>
          <div className="map-caption">
            <span className="live-dot" />
            Famagusta <span>·</span> EMU campus
          </div>
        </div>
        <div className="map-bottom-controls">
          <button
            className="map-button"
            onClick={() => {
              location.locate();
            }}
          >
            <LocateFixed size={18} />
            {t.nearby}
          </button>
          <span className="map-key">
            <i /> {t.demo} paths · illustrative colours
          </span>
        </div>
        {location.error && (
          <p className="map-alert" role="status">
            {location.error}
          </p>
        )}
        {location.user && (
          <button
            className="map-button my-location"
            onClick={() => setFocus(location.user)}
          >
            <Navigation size={18} /> My location
          </button>
        )}
        <div className="map-status">
          <span>
            <i className="live-dot" />
            {buses.data
              ? new Date(buses.data.server_time).toLocaleTimeString(lang)
              : "Connecting…"}
          </span>
          <span>© EMU Smart Transit</span>
        </div>
      </section>
    </main>
  );
}

function Catalog({ t, lang }: { t: Text; lang: Lang }) {
  const query = useRoutes(),
    [filter, setFilter] = useState("all"),
    [selected, setSelected] = useState<Route | null>(null);
  return (
    <main className="page">
      <span className="eyebrow">THE NETWORK</span>
      <h1>{t.routes}</h1>
      <p className="intro">
        Explore individual lines, campus services and combined routes.
      </p>
      <Filter value={filter} onChange={setFilter} t={t} />
      <LoadingError
        loading={query.isLoading}
        error={query.error}
        t={t}
        retry={() => query.refetch()}
      />
      <div className="route-grid">
        {query.data?.results
          .filter((r) => matchesLine(r, filter))
          .map((r) => (
            <button
              className="route-card"
              key={r.id}
              onClick={() => setSelected(r)}
            >
              <div className="line-stack">
                {r.lines.map((l) => (
                  <Badge key={l.id} line={l} />
                ))}
              </div>
              <h2>{r.name}</h2>
              <p>
                {r.lines
                  .map((l) => (lang === "tr" ? l.name_tr : l.name_en))
                  .join(" + ")}
              </p>
              <div className="route-meta">
                <span>{t[r.direction as keyof Text]}</span>
                <span>{r.ordered_stops.length} stops</span>
              </div>
              <small>{r.demo ? t.demo : t.unverified}</small>
              <ChevronRight className="route-chevron" size={20} />
            </button>
          ))}
      </div>
      {selected && (
        <section className="route-detail">
          <button
            className="icon-button"
            aria-label={t.close}
            onClick={() => setSelected(null)}
          >
            <X />
          </button>
          <h2>{selected.name}</h2>
          <ol className="stop-sequence">
            {selected.ordered_stops.map((s) => (
              <li key={s.sequence}>
                <MapPin size={18} />
                <span>
                  {lang === "tr"
                    ? s.stop_detail.name_tr
                    : s.stop_detail.name_en}
                  <small>
                    {(s.distance_m / 1000).toFixed(1)} km · {s.dwell_seconds}s
                    dwell
                  </small>
                </span>
              </li>
            ))}
          </ol>
          {!selected.ordered_stops.length && (
            <p>{t.unverified}: no surveyed stops or path published.</p>
          )}
        </section>
      )}
    </main>
  );
}

function Timetable({
  t,
  lang,
  notice,
}: {
  t: Text;
  lang: Lang;
  notice?: string;
}) {
  const [day, setDay] = useState("weekday"),
    [direction, setDirection] = useState("all"),
    [filter, setFilter] = useState("all"),
    [date, setDate] = useState("");
  const query = useResource<List<Schedule>>(
      `schedules/?limit=500&${date ? "date=" + date : "service_day=" + day}`,
    ),
    routes = useRoutes();
  const routeMap = new globalThis.Map(
    routes.data?.results.map((r) => [r.id, r]),
  );
  const shown = (query.data?.results || []).filter((s) => {
    const r = routeMap.get(s.route);
    return (
      r &&
      matchesLine(r, filter) &&
      (direction === "all" || r.direction === direction)
    );
  });
  const now = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Famagusta",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date());
  const todayType = (() => {
    const dateText = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Famagusta",
      weekday: "short",
    }).format(new Date());
    return ["Sat"].includes(dateText)
      ? "saturday"
      : ["Sun"].includes(dateText)
        ? "sunday"
        : "weekday";
  })();
  const next = shown
    .filter(
      (s) => s.departure_time.slice(0, 5) >= now && s.service_day === todayType,
    )
    .sort((a, b) =>
      a.departure_time.localeCompare(b.departure_time),
    )[0]?.departure_time;
  return (
    <main className="page">
      <span className="eyebrow">PLAN YOUR JOURNEY</span>
      <h1>{t.timetable}</h1>
      <p className="intro">{t.timeNote}</p>
      <p className="notice-box">{notice}</p>
      <Filter value={filter} onChange={setFilter} t={t} />
      <div className="toolbar">
        <div className="segmented">
          {["weekday", "saturday", "sunday"].map((d) => (
            <button
              key={d}
              aria-pressed={day === d && !date}
              onClick={() => {
                setDay(d);
                setDate("");
              }}
              className={day === d && !date ? "selected" : ""}
            >
              {t[d as keyof Text]}
            </button>
          ))}
        </div>
        <label>
          {t.today}
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
        <label>
          Direction
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
          >
            <option value="all">All directions</option>
            {["to_emu", "from_emu", "loop", "return"].map((d) => (
              <option key={d} value={d}>
                {t[d as keyof Text]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <LoadingError
        loading={query.isLoading || routes.isLoading}
        error={query.error || routes.error}
        t={t}
        retry={() => query.refetch()}
      />
      {!query.isLoading && !shown.length && (
        <p className="message">{t.noSchedule}</p>
      )}
      <div className="timetable-groups">
        {Array.from(new Set(shown.map((s) => s.route))).map((id) => (
          <section key={id} className="timetable-group">
            <h2>{routeMap.get(id)?.name}</h2>
            <div className="times">
              {shown
                .filter((s) => s.route === id)
                .map((s) => (
                  <span
                    key={s.id}
                    className={
                      s.departure_time === next && !date ? "next-departure" : ""
                    }
                  >
                    {s.departure_time.slice(0, 5)}
                    {s.departure_time === next && !date && (
                      <small>Next scheduled</small>
                    )}
                  </span>
                ))}
            </div>
            <a
              href={shown.find((s) => s.route === id)?.source}
              target="_blank"
              rel="noreferrer"
            >
              {t.source}
            </a>
          </section>
        ))}
      </div>
      <p className="muted">
        No regular services on Sundays or public holidays. Saturday external
        services combine 1 + 4 and 2 + 5. Date selection applies configured
        exceptions. Semester validity must be confirmed by transportation staff.
      </p>
    </main>
  );
}

function StopPage({ t, lang }: { t: Text; lang: Lang }) {
  const query = useStops(),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<Stop | null>(null),
    location = useLocation(t);
  const shown = useMemo(() => {
    const list = (query.data?.results || []).filter((s) =>
      (s.name_en + " " + s.name_tr)
        .toLowerCase()
        .includes(search.toLowerCase()),
    );
    if (location.user) {
      const [lat, lon] = location.user;
      list.sort(
        (a, b) =>
          Math.hypot(
            a.latitude - lat,
            (a.longitude - lon) * Math.cos((lat * Math.PI) / 180),
          ) -
          Math.hypot(
            b.latitude - lat,
            (b.longitude - lon) * Math.cos((lat * Math.PI) / 180),
          ),
      );
    }
    return list;
  }, [query.data, search, location.user]);
  return (
    <main className="page">
      <span className="eyebrow">YOUR NEXT CONNECTION</span>
      <h1>{t.stops}</h1>
      <div className="toolbar">
        <label className="search">
          <Search size={18} />
          <input
            placeholder={t.search}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <button onClick={location.locate}>
          <LocateFixed size={18} />
          {t.nearby}
        </button>
      </div>
      {location.error && <p role="status">{location.error}</p>}
      <LoadingError
        loading={query.isLoading}
        error={query.error}
        t={t}
        retry={() => query.refetch()}
      />
      <div className="stops-layout">
        <div className="stop-list">
          {shown.map((s) => (
            <button key={s.id} onClick={() => setSelected(s)}>
              <MapPin size={20} />
              <span>
                <strong>{lang === "tr" ? s.name_tr : s.name_en}</strong>
                <small>
                  {s.demo ? t.demo : t.verified}
                  {location.user ? " · sorted by proximity" : ""}
                </small>
              </span>
              <ChevronRight size={18} />
            </button>
          ))}
          {!shown.length && !query.isLoading && <p>{t.empty}</p>}
        </div>
        {selected && (
          <section className="stop-detail">
            <StopDetails stop={selected} t={t} lang={lang} />
          </section>
        )}
      </div>
    </main>
  );
}
function Notices({ t, lang }: { t: Text; lang: Lang }) {
  const query = useResource<List<Notice>>("announcements/", 30000);
  return (
    <main className="page narrow">
      <span className="eyebrow">STAY INFORMED</span>
      <h1>{t.notices}</h1>
      <LoadingError
        loading={query.isLoading}
        error={query.error}
        t={t}
        retry={() => query.refetch()}
      />
      {query.data?.results.map((n) => (
        <article className="notice" key={n.id}>
          <Bell size={22} />
          <div>
            <span className="eyebrow">{n.kind.replace("_", " ")}</span>
            <h2>{lang === "tr" && n.title_tr ? n.title_tr : n.title}</h2>
            <p>{lang === "tr" && n.body_tr ? n.body_tr : n.body}</p>
            <small>{new Date(n.starts_at).toLocaleDateString(lang)}</small>
          </div>
        </article>
      ))}
      {query.data?.results.length === 0 && <p>{t.noNotices}</p>}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
