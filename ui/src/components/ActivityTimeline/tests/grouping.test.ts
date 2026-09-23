import { describe, expect, it } from "vitest";
import { compareActivities, drawnKey, groupActivities } from "../grouping";
import * as entry from "../index";
import type { Activity, VersionActivity } from "../types";

const at = (min: number) => `2026-01-01 10:${String(min).padStart(2, "0")}:00`;
const author = { email: "a@x", fullname: "A" };

const version = (key: string, min: number, from: string, to: string) =>
  ({
    type: "version",
    key,
    timestamp: at(min),
    author,
    data: {
      fieldname: "status",
      type: "diff",
      prefix: "changed status",
      from,
      to,
    },
  } as VersionActivity);

const comment = (min: number) =>
  ({
    type: "comment",
    key: `c${min}`,
    timestamp: at(min),
    author,
    data: { name: `c${min}`, content: "hi" },
  } as Activity);

describe("groupVersionActivities", () => {
  it("folds consecutive same-author rows into one net summary", () => {
    const out = groupActivities([
      version("v1", 0, "A", "B"),
      version("v2", 1, "B", "C"),
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].key).toBe("v1");
    const data = (out[0] as VersionActivity).data;
    expect(data.type === "diff" && data.from).toBe("A");
    expect(data.type === "diff" && data.to).toBe("C");
    expect(data.type === "diff" && data.history?.length).toBe(2);
  });

  it("splits the fold on any visible row in between", () => {
    const out = groupActivities([
      version("v1", 0, "A", "B"),
      comment(1),
      version("v2", 2, "B", "C"),
    ]);
    expect(out.map((a) => a.type)).toEqual(["version", "comment", "version"]);
  });

  it("splits on a >15m gap between saves", () => {
    const out = groupActivities([
      version("v1", 0, "A", "B"),
      version("v2", 20, "B", "C"),
    ]);
    expect(out).toHaveLength(2);
  });

  it("keeps net no-ops visible", () => {
    const out = groupActivities([
      version("v1", 0, "A", "B"),
      version("v2", 1, "B", "A"),
    ]);
    expect(out).toHaveLength(1);
    const data = (out[0] as VersionActivity).data;
    expect(data.type === "diff" && data.to).toBe("A");
  });
});

describe("drawnKey", () => {
  it("names the run a folded version row draws in, and leaves any other row alone", () => {
    const feed = [version("v1", 0, "Open", "Hold"), version("v2", 5, "Hold", "Closed"), comment(6), version("v3", 7, "Closed", "Open")];
    expect(drawnKey(feed, "v2")).toBe("v1");
    expect(drawnKey(feed, "v1")).toBe("v1");
    expect(drawnKey(feed, "v3")).toBe("v3");
    expect(drawnKey(feed, "c6")).toBe("c6");
    expect(drawnKey(feed, "gone")).toBe("gone");
  });
});

describe("compareActivities", () => {
  const at = (timestamp: string, key: string) => ({ timestamp, key });

  it("orders as the server does: the timestamp string to the microsecond, then the key by code unit", () => {
    const later = at("2026-01-01 10:00:00.000002", "a");
    const earlier = at("2026-01-01 10:00:00.000001", "b");
    expect(compareActivities(later, earlier)).toBeGreaterThan(0);
    const t = "2026-01-01 10:00:00";
    expect(compareActivities(at(t, "comment:B"), at(t, "comment:a"))).toBeLessThan(0);
    expect(compareActivities(at(t, "comment:a"), at(t, "comment:a"))).toBe(0);
  });

  it("is exported from the package entry", () => {
    expect(entry.compareActivities).toBe(compareActivities);
  });
});
