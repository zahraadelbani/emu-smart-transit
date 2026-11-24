import { describe, it, expect } from "vitest";
import { ageBus } from "./freshness";
import type { Bus } from "./types";
const time = "2026-11-24T08:00:00Z";
const bus = {
  status: "live",
  position: { fix_time: time },
  eta: { available: true, arrivals: [{ minutes: 3 }], reason: "" },
} as Bus;
describe("cached location freshness", () => {
  it("ages live data into stale and offline even without another API response", () => {
    expect(ageBus(bus, time, 0).status).toBe("live");
    expect(ageBus(bus, time, 31000).status).toBe("stale");
    expect(ageBus(bus, time, 121000).status).toBe("offline");
  });
  it("suppresses cached ETAs when the location becomes stale", () => {
    const value = ageBus(bus, time, 31000);
    expect(value.eta.available).toBe(false);
    expect(value.eta.arrivals).toEqual([]);
  });
  it("honours reporting thresholds and missing fixes", () => {
    expect(ageBus(bus, time, 8000, 3, 7).status).toBe("offline");
    expect(ageBus({ ...bus, position: null }, time, 0).status).toBe("offline");
  });
});
