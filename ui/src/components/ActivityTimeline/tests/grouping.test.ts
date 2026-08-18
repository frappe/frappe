import { describe, expect, it } from "vitest";
import { groupActivities } from "../grouping";
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
