import type { Bus } from "./types";

/** Continue aging cached locations if the API itself becomes unreachable. */
export function ageBus(
  bus: Bus,
  serverTime: string,
  elapsedMs: number,
  liveSeconds = 30,
  offlineSeconds = 120,
): Bus {
  const age = bus.position
    ? (Date.parse(serverTime) -
        Date.parse(bus.position.fix_time) +
        Math.max(0, elapsedMs)) /
      1000
    : Infinity;
  const status: Bus["status"] =
    age <= liveSeconds ? "live" : age <= offlineSeconds ? "stale" : "offline";
  return {
    ...bus,
    status,
    eta:
      status === "live"
        ? bus.eta
        : {
            ...bus.eta,
            available: false,
            arrivals: [],
            reason:
              status === "offline"
                ? "Bus currently offline"
                : "Location is stale",
          },
  };
}
