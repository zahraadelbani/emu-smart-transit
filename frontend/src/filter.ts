import type { Line } from "./types";
export function matchesLine(bus: { lines: Line[] }, filter: string) {
  return (
    filter === "all" ||
    bus.lines.some((l) =>
      filter === "campus" ? l.classification === "campus" : l.code === filter,
    )
  );
}
