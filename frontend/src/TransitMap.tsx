import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Marker,
  Tooltip,
  useMap,
  ZoomControl,
} from "react-leaflet";
import { useEffect, useState } from "react";
import L from "leaflet";
import type { Bus, Route, Stop } from "./types";

function Focus({ point }: { point: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (point) map.flyTo(point, 15, { duration: 0.5 });
  }, [point?.[0], point?.[1], map]);
  return null;
}
export function TransitMap({
  buses,
  routes,
  stops,
  onBus,
  onStop,
  user,
  focus,
}: {
  buses: Bus[];
  routes: Route[];
  stops: Stop[];
  onBus: (b: Bus) => void;
  onStop: (s: Stop) => void;
  user: [number, number] | null;
  focus: [number, number] | null;
}) {
  const [tilesUnavailable, setTilesUnavailable] = useState(false);
  const tile =
    import.meta.env.VITE_TILE_URL ||
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  return (
    <>
      <MapContainer
        center={[35.137, 33.918]}
        zoom={14}
        zoomControl={false}
        className="transit-map"
        aria-label="University bus map"
      >
        <TileLayer
          url={tile}
          eventHandlers={{ tileerror: () => setTilesUnavailable(true) }}
          attribution={
            import.meta.env.VITE_TILE_ATTRIBUTION ||
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          }
        />
        <Focus point={focus} />
        <ZoomControl position="bottomright" />
        {routes
          .filter((r) => r.geometry.length > 1)
          .map((r) => (
            <Polyline
              key={r.id}
              positions={r.geometry}
              pathOptions={{
                color: r.lines[0]?.color || "#64748b",
                weight: 4,
                opacity: 0.65,
                dashArray: r.demo ? "7 7" : undefined,
              }}
            />
          ))}
        {stops.map((s) => (
          <CircleMarker
            key={s.id}
            center={[s.latitude, s.longitude]}
            radius={6}
            pathOptions={{
              color: "#112d50",
              fillColor: "#fff",
              fillOpacity: 1,
              weight: 2,
            }}
            eventHandlers={{ click: () => onStop(s) }}
          >
            <Tooltip>{s.name_en}</Tooltip>
          </CircleMarker>
        ))}
        {buses
          .filter((b) => b.position)
          .map((b) => {
            const p = b.position!;
            const color = b.status === "live" ? "#112d50" : "#64748b";
            return (
              <Marker
                key={b.id}
                position={[p.latitude, p.longitude]}
                icon={L.divIcon({
                  className: "vehicle-icon",
                  html: `<div class="vehicle-marker" style="background:${color}"><span style="transform:rotate(${p.heading}deg)">▲</span><b>${String(
                    b.fleet_number,
                  )
                    .replace(/[^0-9]/g, "")
                    .slice(-2)}</b></div>`,
                  iconSize: [44, 44],
                  iconAnchor: [22, 22],
                })}
                eventHandlers={{ click: () => onBus(b) }}
              >
                <Tooltip>
                  {b.display_name} · {b.status}
                </Tooltip>
              </Marker>
            );
          })}
        {user && (
          <CircleMarker
            center={user}
            radius={8}
            pathOptions={{
              color: "#fff",
              fillColor: "#2563eb",
              fillOpacity: 1,
              weight: 3,
            }}
          >
            <Tooltip>Your location</Tooltip>
          </CircleMarker>
        )}
      </MapContainer>
      {tilesUnavailable && (
        <p className="tile-warning">
          Base map tiles unavailable. Bus and service data remain available.
        </p>
      )}
    </>
  );
}
