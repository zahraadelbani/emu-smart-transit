import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  useMapEvents,
} from "react-leaflet";
import {
  Plus,
  Save,
  ShieldCheck,
  LogOut,
  Check,
  AlertCircle,
  Upload,
  RotateCcw,
} from "lucide-react";
import { api, useResource } from "./api";
import type { Bus, Route, List } from "./types";

type Row = Record<string, any>;
type Field = {
  key: string;
  label: string;
  type?:
    | "text"
    | "number"
    | "checkbox"
    | "select"
    | "date"
    | "time"
    | "datetime-local"
    | "textarea";
  options?: string[];
  required?: boolean;
  help?: string;
};
const schemas: Record<string, Field[]> = {
  buses: [
    { key: "fleet_number", label: "Fleet number", required: true },
    { key: "display_name", label: "Display name", required: true },
    { key: "registration_number", label: "Registration (staff only)" },
    {
      key: "operational_status",
      label: "Status",
      type: "select",
      options: ["available", "maintenance", "inactive"],
    },
    { key: "active", label: "Active", type: "checkbox" },
    { key: "demo", label: "Demonstration vehicle", type: "checkbox" },
  ],
  devices: [
    { key: "identifier", label: "Tracker identifier", required: true },
    { key: "traccar_device_id", label: "Traccar device ID", type: "number" },
    { key: "imei", label: "IMEI (staff only)" },
    { key: "manufacturer", label: "Manufacturer" },
    { key: "model", label: "Model" },
    { key: "bus", label: "Bus", type: "select" },
  ],
  lines: [
    { key: "code", label: "Line code", required: true },
    { key: "name_en", label: "English name", required: true },
    { key: "name_tr", label: "Turkish name", required: true },
    { key: "color", label: "Display colour (#RRGGBB)", required: true },
    {
      key: "classification",
      label: "Classification",
      type: "select",
      options: ["external", "campus"],
    },
    {
      key: "color_verified",
      label: "Official colour verified against PDF",
      type: "checkbox",
    },
    { key: "verified", label: "Line definition verified", type: "checkbox" },
    { key: "active", label: "Active", type: "checkbox" },
  ],
  routes: [
    { key: "name", label: "Route name", required: true },
    {
      key: "direction",
      label: "Direction",
      type: "select",
      options: ["to_emu", "from_emu", "loop", "return"],
    },
    {
      key: "line_ids",
      label: "Service lines",
      help: "Select each service line below",
    },
    { key: "combined", label: "Combined service", type: "checkbox" },
    {
      key: "duration_minutes",
      label: "Expected duration (minutes)",
      type: "number",
    },
    {
      key: "average_speed_kmh",
      label: "Baseline speed (km/h)",
      type: "number",
    },
    {
      key: "geometry",
      label: "Route geometry",
      help: "Click map points in travel order, or paste a JSON list of [latitude, longitude] pairs",
      type: "textarea",
    },
    {
      key: "verified",
      label: "Geometry and stops independently verified",
      type: "checkbox",
    },
    { key: "demo", label: "Demonstration path", type: "checkbox" },
    { key: "active", label: "Active", type: "checkbox" },
  ],
  stops: [
    { key: "code", label: "Stop code", required: true },
    { key: "name_en", label: "English name", required: true },
    { key: "name_tr", label: "Turkish name", required: true },
    { key: "latitude", label: "Latitude", type: "number", required: true },
    { key: "longitude", label: "Longitude", type: "number", required: true },
    {
      key: "accessibility",
      label: "Accessibility information",
      type: "textarea",
    },
    { key: "verified", label: "Coordinates verified", type: "checkbox" },
    { key: "demo", label: "Demonstration stop", type: "checkbox" },
    { key: "active", label: "Active", type: "checkbox" },
  ],
  "route-stops": [
    { key: "route", label: "Route", type: "select", required: true },
    { key: "stop", label: "Stop", type: "select", required: true },
    {
      key: "sequence",
      label: "Sequence (repeated stops allowed)",
      type: "number",
      required: true,
    },
    {
      key: "distance_m",
      label: "Cumulative route distance (metres)",
      type: "number",
      required: true,
    },
    { key: "dwell_seconds", label: "Expected dwell (seconds)", type: "number" },
  ],
  schedules: [
    { key: "route", label: "Route", type: "select", required: true },
    {
      key: "departure_time",
      label: "Origin departure",
      type: "time",
      required: true,
    },
    {
      key: "service_day",
      label: "Service day",
      type: "select",
      options: ["weekday", "saturday", "sunday"],
    },
    {
      key: "effective_start",
      label: "Valid from",
      type: "date",
      required: true,
    },
    { key: "effective_end", label: "Valid until", type: "date" },
    { key: "source", label: "Official source URL" },
    { key: "verified", label: "Timetable verified", type: "checkbox" },
    { key: "active", label: "Active", type: "checkbox" },
  ],
  trips: [
    { key: "route", label: "Route", type: "select", required: true },
    {
      key: "scheduled_departure",
      label: "Scheduled departure (local time)",
      type: "datetime-local",
      required: true,
    },
    {
      key: "actual_departure",
      label: "Actual departure",
      type: "datetime-local",
    },
    {
      key: "actual_completion",
      label: "Actual completion",
      type: "datetime-local",
    },
    {
      key: "status",
      label: "Trip status",
      type: "select",
      options: ["scheduled", "active", "delayed", "completed", "cancelled"],
    },
  ],
  exceptions: [
    { key: "date", label: "Service date", type: "date", required: true },
    { key: "route", label: "Route (blank means all routes)", type: "select" },
    {
      key: "kind",
      label: "Exception",
      type: "select",
      options: ["holiday", "cancelled", "special", "change"],
    },
    {
      key: "message",
      label: "Service information",
      type: "textarea",
      required: true,
    },
    {
      key: "enabled",
      label: "Enable service on this date (override closure)",
      type: "checkbox",
    },
  ],
  announcements: [
    { key: "title", label: "Title (English)", required: true },
    { key: "title_tr", label: "Title (Turkish)" },
    {
      key: "body",
      label: "Message (English)",
      type: "textarea",
      required: true,
    },
    { key: "body_tr", label: "Message (Turkish)", type: "textarea" },
    {
      key: "kind",
      label: "Notice type",
      type: "select",
      options: [
        "general",
        "delay",
        "cancelled",
        "combined",
        "route_change",
        "stop_closed",
      ],
    },
    {
      key: "starts_at",
      label: "Publish from",
      type: "datetime-local",
      required: true,
    },
    { key: "ends_at", label: "Publish until", type: "datetime-local" },
    { key: "active", label: "Published", type: "checkbox" },
  ],
};
function ClickMap({ onPoint }: { onPoint: (p: [number, number]) => void }) {
  useMapEvents({
    click: (e) =>
      onPoint([
        Number(e.latlng.lat.toFixed(6)),
        Number(e.latlng.lng.toFixed(6)),
      ]),
  });
  return null;
}
function EditorMap({
  points,
  onPoint,
}: {
  points: [number, number][];
  onPoint: (p: [number, number]) => void;
}) {
  return (
    <MapContainer
      center={points[0] || [35.144, 33.91]}
      zoom={14}
      className="editor-map"
    >
      <TileLayer
        url={
          import.meta.env.VITE_TILE_URL ||
          "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        }
        attribution={
          import.meta.env.VITE_TILE_ATTRIBUTION ||
          "&copy; OpenStreetMap contributors"
        }
      />
      <ClickMap onPoint={onPoint} />
      {points.length > 1 && <Polyline positions={points} />}
      {points.map((p, i) => (
        <CircleMarker key={i} center={p} radius={5} />
      ))}
    </MapContainer>
  );
}

export function Staff() {
  const session = useResource<{ staff: boolean; username: string }>(
      "auth/session/",
    ),
    client = useQueryClient(),
    [error, setError] = useState(""),
    [tab, setTab] = useState("overview");
  if (session.isLoading)
    return <main className="page">Checking staff session…</main>;
  if (!session.data?.staff)
    return (
      <main className="page login-page">
        <div className="login-panel">
          <ShieldCheck size={30} />
          <span className="eyebrow">TRANSPORTATION SERVICES</span>
          <h1>Staff sign in</h1>
          <p>Manage services, fleet assignments and university notices.</p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setError("");
              const data = new FormData(e.currentTarget);
              try {
                await api("auth/login/", Object.fromEntries(data));
                await client.invalidateQueries();
              } catch (err) {
                setError((err as Error).message);
              }
            }}
          >
            <label>
              Username
              <input name="username" autoComplete="username" required />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
            <button className="primary">Sign in</button>
          </form>
          <a href="/admin/">Django administration</a>
        </div>
      </main>
    );
  return (
    <main className="page staff-page">
      <div className="staff-heading">
        <div>
          <span className="eyebrow">OPERATIONS</span>
          <h1>Transportation control</h1>
        </div>
        <button
          onClick={async () => {
            await api("auth/logout/", {});
            client.clear();
            await session.refetch();
          }}
        >
          <LogOut size={17} />
          Sign out
        </button>
      </div>
      <div className="staff-tabs" role="tablist">
        {[
          "overview",
          "assignments",
          ...Object.keys(schemas),
          "import",
          "simulation",
        ].map((k) => (
          <button
            role="tab"
            aria-selected={tab === k}
            className={tab === k ? "selected" : ""}
            key={k}
            onClick={() => setTab(k)}
          >
            {k.replaceAll("-", " ")}
          </button>
        ))}
      </div>
      {tab === "overview" ? (
        <Overview />
      ) : tab === "assignments" ? (
        <Assignments />
      ) : tab === "simulation" ? (
        <Simulation />
      ) : tab === "import" ? (
        <ScheduleImport />
      ) : (
        <EntityEditor key={tab} entity={tab} />
      )}
      <p className="muted">
        Signed in as {session.data.username}. Important changes are recorded in
        the audit log. <a href="/admin/transit/auditlog/">View audit history</a>
      </p>
    </main>
  );
}

function Overview() {
  const query = useResource<Row>("staff/overview/", 5000);
  if (query.error) return <p role="alert">{query.error.message}</p>;
  if (!query.data) return <p>Loading operations…</p>;
  const data = query.data;
  return (
    <>
      <div className="metrics">
        {[
          ["Physical buses", data.total],
          ["Active services", data.active],
          ["Offline", data.offline],
          ["Unassigned", data.unassigned],
          ["Current trips", data.current_trips],
          ["Combined services", data.combined],
        ].map(([label, value]) => (
          <div key={label}>
            <small>{label}</small>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <h2>GPS integration health</h2>
      {data.health.length ? (
        data.health.map((h: Row) => (
          <p className="notice-box" key={h.provider}>
            {h.healthy ? <Check size={18} /> : <AlertCircle size={18} />}
            <strong>{h.provider}</strong> · {h.message} ·{" "}
            {h.last_success
              ? new Date(h.last_success).toLocaleString()
              : "No successful poll"}
          </p>
        ))
      ) : (
        <p>No GPS worker has reported. Start a provider worker.</p>
      )}
    </>
  );
}

function Assignments() {
  const buses = useResource<List<Row>>("staff/buses/"),
    routes = useResource<List<Route>>("staff/routes/?limit=500"),
    trips = useResource<List<Row>>("staff/trips/?limit=500"),
    overview = useResource<Row>("staff/overview/", 5000),
    [error, setError] = useState(""),
    [success, setSuccess] = useState(""),
    [pending, setPending] = useState(false),
    client = useQueryClient();
  async function change(data: Row) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      await api("staff/assignments/", data);
      setSuccess(
        "Assignment updated. Public tracking will refresh within 5 seconds.",
      );
      await client.invalidateQueries();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <section>
      <h2>Live bus assignments</h2>
      <p>
        Select a vehicle, route and optional trip. Replacing an assignment
        closes its previous assignment in the same transaction.
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {success && (
        <p role="status" className="success">
          {success}
        </p>
      )}
      <div className="assignment-list">
        {buses.data?.results.map((bus) => {
          const current = overview.data?.buses?.find(
            (b: Bus) => b.id === bus.id,
          );
          return (
            <div key={bus.id} className="assignment-card">
              <div>
                <h3>{bus.display_name}</h3>
                <p>{current?.route_name || "Unassigned"}</p>
                <small>
                  {current?.status || "No tracking"} ·{" "}
                  {current?.direction || "No direction"}
                  {current?.assignment_start
                    ? " / " +
                      Math.floor(
                        (Date.now() - Date.parse(current.assignment_start)) /
                          60000,
                      ) +
                      " min assigned"
                    : ""}
                </small>
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = new FormData(e.currentTarget);
                  change({
                    bus_id: bus.id,
                    route_id: Number(form.get("route")),
                    trip_id: form.get("trip") || null,
                  });
                }}
              >
                <label>
                  Route and direction
                  <select
                    required
                    name="route"
                    aria-label={`Route for ${bus.display_name}`}
                  >
                    <option value="">Select route</option>
                    {routes.data?.results
                      .filter((r) => r.active)
                      .map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} · {r.direction}
                        </option>
                      ))}
                  </select>
                </label>
                <label>
                  Trip (optional)
                  <select name="trip">
                    <option value="">Manual service</option>
                    {trips.data?.results
                      .filter(
                        (t) => !["completed", "cancelled"].includes(t.status),
                      )
                      .map((t) => (
                        <option key={t.id} value={t.id}>
                          #{t.id} · route {t.route} · {t.scheduled_departure}
                        </option>
                      ))}
                  </select>
                </label>
                <button className="primary" disabled={pending}>
                  Activate assignment
                </button>
              </form>
              {current && (
                <div className="assignment-actions">
                  <button
                    disabled={pending}
                    onClick={() =>
                      change({
                        action: "end",
                        assignment_id: current.assignment_id,
                      })
                    }
                  >
                    End service
                  </button>
                  <button
                    disabled={pending}
                    onClick={() =>
                      change({
                        action: "cancel",
                        assignment_id: current.assignment_id,
                      })
                    }
                  >
                    Cancel service
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function EntityEditor({ entity }: { entity: string }) {
  const query = useResource<List<Row>>(`staff/${entity}/?limit=500`),
    [editing, setEditing] = useState<Row | null>(null),
    [error, setError] = useState(""),
    [success, setSuccess] = useState(""),
    [pending, setPending] = useState(false),
    client = useQueryClient();
  const busOptions = useResource<List<Row>>("staff/buses/?limit=500"),
    routeOptions = useResource<List<Row>>("staff/routes/?limit=500"),
    stopOptions = useResource<List<Row>>("staff/stops/?limit=500"),
    lineOptions = useResource<List<Row>>("staff/lines/?limit=500");
  const fields = schemas[entity];
  const options: Record<string, Row[]> = {
    bus: busOptions.data?.results || [],
    route: routeOptions.data?.results || [],
    stop: stopOptions.data?.results || [],
  };
  const open = (row: Row) => {
    setEditing({
      ...Object.fromEntries(
        fields.filter((f) => f.options).map((f) => [f.key, f.options![0]]),
      ),
      duration_minutes: 25,
      average_speed_kmh: 22,
      dwell_seconds: 25,
      starts_at: new Date().toISOString(),
      ...row,
      geometry:
        typeof row.geometry === "object"
          ? JSON.stringify(row.geometry)
          : row.geometry,
      line_ids: row.lines?.map((l: Row) => l.id) || [],
      active: row.active ?? true,
    });
    setError("");
    setSuccess("");
  };
  const update = (key: string, value: any) =>
    setEditing((old) => ({ ...old, [key]: value }));
  let points: [number, number][] = [];
  try {
    points =
      entity === "routes"
        ? JSON.parse(editing?.geometry || "[]")
        : editing?.latitude !== undefined && editing?.longitude !== undefined
          ? [[Number(editing.latitude), Number(editing.longitude)]]
          : [];
  } catch {
    /* Editor validation reports malformed geometry on save. */
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setPending(true);
    setError("");
    try {
      const data: Row = {};
      for (const field of fields) {
        let value = editing[field.key];
        if (field.type === "checkbox") value = !!value;
        if (
          field.type === "number" ||
          (field.type === "select" && !field.options)
        )
          value = value === "" || value === undefined ? null : Number(value);
        if (field.key === "geometry") value = JSON.parse(value || "[]");
        if (field.type === "date" && !value) value = null;
        if (field.type === "datetime-local")
          value = value ? new Date(value).toISOString() : null;
        if (value !== undefined) data[field.key] = value;
      }
      await api(
        `staff/${entity}/${editing.id ? editing.id + "/" : ""}`,
        data,
        editing.id ? "PATCH" : "POST",
      );
      await client.invalidateQueries();
      setEditing(null);
      setSuccess("Saved successfully.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <section>
      <div className="section-label">
        <h2>{entity.replaceAll("-", " ")}</h2>
        <button className="primary" onClick={() => open({})}>
          <Plus size={17} />
          Add new
        </button>
      </div>
      {query.error && <p role="alert">{query.error.message}</p>}
      {success && (
        <p className="success" role="status">
          {success}
        </p>
      )}
      {editing && (
        <form className="entity-form" onSubmit={save}>
          <h3>{editing.id ? "Edit record" : "New record"}</h3>
          <div className="form-grid">
            {fields.map((f) =>
              f.key === "line_ids" ? (
                <fieldset key={f.key}>
                  <legend>Service lines</legend>
                  {lineOptions.data?.results.map((l) => (
                    <label className="check-label" key={l.id}>
                      <input
                        type="checkbox"
                        checked={editing.line_ids?.includes(l.id) || false}
                        onChange={(e) =>
                          update(
                            "line_ids",
                            e.target.checked
                              ? [...(editing.line_ids || []), l.id]
                              : (editing.line_ids || []).filter(
                                  (id: number) => id !== l.id,
                                ),
                          )
                        }
                      />
                      {l.code} · {l.name_en}
                    </label>
                  ))}
                </fieldset>
              ) : (
                <label
                  key={f.key}
                  className={f.type === "checkbox" ? "check-label" : ""}
                >
                  {f.type === "checkbox" ? (
                    <>
                      <input
                        type="checkbox"
                        checked={!!editing[f.key]}
                        onChange={(e) => update(f.key, e.target.checked)}
                      />
                      {f.label}
                    </>
                  ) : (
                    <>
                      {f.label}
                      {f.type === "textarea" ? (
                        <textarea
                          value={editing[f.key] ?? ""}
                          required={f.required}
                          onChange={(e) => update(f.key, e.target.value)}
                        />
                      ) : f.type === "select" ? (
                        <select
                          required={f.required}
                          value={editing[f.key] ?? ""}
                          onChange={(e) => update(f.key, e.target.value)}
                        >
                          <option value="">Select…</option>
                          {f.options
                            ? f.options.map((v) => <option key={v}>{v}</option>)
                            : options[f.key]?.map((v) => (
                                <option key={v.id} value={v.id}>
                                  {v.display_name ||
                                    v.name ||
                                    v.name_en ||
                                    v.id}
                                </option>
                              ))}
                        </select>
                      ) : (
                        <input
                          required={f.required}
                          type={f.type || "text"}
                          step={f.type === "number" ? "any" : undefined}
                          value={
                            f.type === "datetime-local" && editing[f.key]
                              ? localDateValue(editing[f.key])
                              : (editing[f.key] ?? "")
                          }
                          onChange={(e) => update(f.key, e.target.value)}
                        />
                      )}
                      {f.help && <small>{f.help}</small>}
                    </>
                  )}
                </label>
              ),
            )}
          </div>
          {["routes", "stops"].includes(entity) && (
            <div>
              <p>
                Click the map to{" "}
                {entity === "routes"
                  ? "append a route point in travel order"
                  : "set stop coordinates"}
                . Verification requires an independent survey.
              </p>
              <EditorMap
                points={points}
                onPoint={(p) =>
                  entity === "routes"
                    ? update("geometry", JSON.stringify([...points, p]))
                    : setEditing((old) => ({
                        ...old,
                        latitude: p[0],
                        longitude: p[1],
                      }))
                }
              />
              {entity === "routes" && (
                <button
                  type="button"
                  onClick={() =>
                    update("geometry", JSON.stringify(points.slice(0, -1)))
                  }
                >
                  <RotateCcw size={16} />
                  Undo last point
                </button>
              )}
            </div>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <button className="primary" disabled={pending}>
              <Save size={17} />
              Save
            </button>
            <button type="button" onClick={() => setEditing(null)}>
              Close editor
            </button>
          </div>
        </form>
      )}
      <div className="record-list">
        {query.data?.results.map((row) => (
          <button key={row.id} onClick={() => open(row)}>
            <strong>
              {row.display_name ||
                row.name ||
                row.name_en ||
                row.title ||
                row.identifier ||
                `${entity} #${row.id}`}
            </strong>
            <small>
              {row.direction ||
                row.departure_time ||
                row.date ||
                row.status ||
                row.code ||
                ""}
            </small>
            <span>Edit</span>
          </button>
        ))}
      </div>
      {query.data?.results.length === 0 && (
        <p>No records yet. Add a new record to get started.</p>
      )}
    </section>
  );
}
function localDateValue(value: string) {
  if (!value.includes("Z") && !/[+-]\d\d:\d\d$/.test(value)) return value;
  const d = new Date(value);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
function Simulation() {
  const query = useResource<Row>("staff/simulation/", 5000),
    [error, setError] = useState("");
  async function change(data: Row) {
    try {
      await api("staff/simulation/", data);
      await query.refetch();
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (query.error) return <p role="alert">{query.error.message}</p>;
  return (
    <section>
      <h2>Development GPS simulator</h2>
      <p>
        This environment must be isolated from production. One worker simulates
        all demonstration vehicles.
      </p>
      <div className="toolbar">
        <button
          className="primary"
          onClick={() => change({ running: !query.data?.running })}
        >
          {query.data?.running ? "Pause" : "Start"}
        </button>
        <button onClick={() => change({ reset: true, running: true })}>
          <RotateCcw size={17} />
          Reset
        </button>
        <label>
          Speed multiplier
          <select
            value={query.data?.speed || 1}
            onChange={(e) => change({ speed: Number(e.target.value) })}
          >
            {[0.5, 1, 2, 5, 10, 20].map((v) => (
              <option value={v} key={v}>
                {v}×
              </option>
            ))}
          </select>
        </label>
        <label>
          Scenario
          <select
            value={query.data?.scenario || "normal"}
            onChange={(e) => change({ scenario: e.target.value })}
          >
            {[
              "normal",
              "delayed",
              "signal_loss",
              "interruption",
              "reassignment",
            ].map((v) => (
              <option value={v} key={v}>
                {v.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p>
        Tick {query.data?.tick || 0}. Signal loss affects the first vehicle;
        interruption affects all vehicles. Tracking becomes stale after 30
        seconds and offline after 120 seconds.
      </p>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
function ScheduleImport() {
  const [text, setText] = useState(""),
    [preview, setPreview] = useState<Row | null>(null),
    [error, setError] = useState(""),
    client = useQueryClient();
  async function run(commit: boolean) {
    setError("");
    try {
      const result = await api<Row>("staff/import-schedules/", {
        rows: JSON.parse(text),
        commit,
      });
      setPreview(result);
      if (commit) await client.invalidateQueries();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <section>
      <h2>Import verified timetable data</h2>
      <p>
        Paste a JSON array of schedule records with route, departure_time,
        service_day, effective_start, effective_end, verified and source.
        Preview validates every row before any record is written.
      </p>
      <label>
        Schedule records
        <textarea
          className="import-input"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setPreview(null);
          }}
        />
      </label>
      <div className="form-actions">
        <button onClick={() => run(false)}>
          <Upload size={17} />
          Validate and preview
        </button>
        {preview && !preview.committed && (
          <button className="primary" onClick={() => run(true)}>
            Import {preview.count} records
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {preview && (
        <>
          <p role="status">
            {preview.committed ? "Imported" : "Validated"} {preview.count}{" "}
            records.
          </p>
          <pre>{JSON.stringify(preview.preview, null, 2)}</pre>
        </>
      )}
    </section>
  );
}
