export type Line = {
  id: number;
  code: string;
  name_en: string;
  name_tr: string;
  color: string;
  classification: string;
  verified: boolean;
  color_verified: boolean;
  active: boolean;
};
export type Stop = {
  id: number;
  code: string;
  name_en: string;
  name_tr: string;
  latitude: number;
  longitude: number;
  demo: boolean;
  verified: boolean;
  accessibility: string;
};
export type RouteStop = {
  id: number;
  stop: number;
  sequence: number;
  distance_m: number;
  dwell_seconds: number;
  stop_detail: Stop;
};
export type Route = {
  id: number;
  name: string;
  direction: string;
  geometry: [number, number][];
  lines: Line[];
  ordered_stops: RouteStop[];
  demo: boolean;
  verified: boolean;
  combined: boolean;
  active: boolean;
};
export type Arrival = {
  stop_id: number;
  stop_name: string;
  sequence: number;
  minutes: number;
  confidence: string;
  demo: boolean;
  type: string;
  bus_name?: string;
  bus_id?: number;
};
export type Bus = {
  id: number;
  display_name: string;
  fleet_number: string;
  route_id: number;
  route_name: string;
  direction: string;
  lines: Line[];
  assignment_id: number;
  demo: boolean;
  status: "live" | "stale" | "offline";
  trip_status: string;
  position: {
    latitude: number;
    longitude: number;
    heading: number;
    speed_kmh: number;
    fix_time: string;
    source: string;
  } | null;
  eta: { available: boolean; reason: string; arrivals: Arrival[] };
};
export type Schedule = {
  id: number;
  route: number;
  departure_time: string;
  service_day: string;
  verified: boolean;
  source: string;
  effective_start: string;
  effective_end: string | null;
};
export type Notice = {
  id: number;
  title: string;
  title_tr: string;
  body: string;
  body_tr: string;
  kind: string;
  starts_at: string;
};
export type List<T> = { results: T[]; count: number; next: string | null };
