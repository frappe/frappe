import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Activity } from "../types";

const api = vi.hoisted(() => ({ getDocumentPart: vi.fn() }));
vi.mock("../../../api", () => ({ getDocumentPart: api.getDocumentPart }));
vi.mock("../../../socket", () => ({ getSocketInstance: () => null }));

import { useActivityTimeline } from "../useActivityTimeline";

let docCounter = 0;
/** A fresh document per test: the composable keeps one store per document for the session. */
function freshDoc() {
  return `T-${docCounter++}`;
}

function row(type: Activity["type"], key: string, timestamp: string, subtype?: string): Activity {
  return {
    type,
    key,
    timestamp,
    author: { email: "a@x.com", fullname: "A" },
    data: subtype ? { subtype } : {},
  } as Activity;
}

const firstPage = {
  activities: [row("comment", "comment:1", "2026-01-02"), row("email", "email:1", "2026-01-03")],
  has_more_emails: true,
  has_more_milestones: true,
  next_milestone_start: 5,
};

beforeEach(() => {
  api.getDocumentPart.mockReset().mockResolvedValue({ data: firstPage });
});

describe("useActivityTimeline", () => {
  it("reads the activity part with the visible types and sorts the rows", async () => {
    const name = freshDoc();
    const timeline = useActivityTimeline("ToDo", name, ["comment", "email"]);
    expect(api.getDocumentPart).toHaveBeenCalledWith("ToDo", name, "activity", {
      types: ["comment", "email"],
    });
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));
    expect(timeline.activities.value.map((a) => a.key)).toEqual(["comment:1", "email:1"]);
    expect(timeline.paginate.hasNextPage).toBe(true);
  });

  it("pages both streams at once and appends the older rows", async () => {
    const name = freshDoc();
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));

    api.getDocumentPart.mockImplementation(async (_dt, _name, _part, params) => {
      if (params.stream === "emails") {
        return { data: { activities: [row("email", "email:0", "2026-01-01")], has_more_emails: false } };
      }
      return {
        data: {
          activities: [row("log", "log:m1", "2025-12-31", "milestone")],
          has_more_milestones: false,
          next_milestone_start: 9,
        },
      };
    });
    timeline.paginate.fetchNextPage();
    await vi.waitFor(() => expect(timeline.paginate.isFetchingNextPage).toBe(false));

    expect(api.getDocumentPart).toHaveBeenCalledWith("ToDo", name, "activity", { stream: "emails", start: 1 });
    expect(api.getDocumentPart).toHaveBeenCalledWith("ToDo", name, "activity", {
      stream: "milestones",
      start: 5,
    });
    expect(timeline.activities.value.map((a) => a.key)).toEqual([
      "log:m1",
      "email:0",
      "comment:1",
      "email:1",
    ]);
    expect(timeline.paginate.hasNextPage).toBe(false);
  });

  it("keeps the older paged rows when the first page reloads", async () => {
    const name = freshDoc();
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));

    api.getDocumentPart.mockResolvedValueOnce({
      data: { activities: [row("email", "email:0", "2026-01-01")], has_more_emails: false },
    });
    timeline.paginate.fetchNextPage();
    await vi.waitFor(() => expect(timeline.paginate.isFetchingNextPage).toBe(false));

    api.getDocumentPart.mockResolvedValue({
      data: { ...firstPage, activities: [...firstPage.activities, row("comment", "comment:2", "2026-01-04")] },
    });
    await timeline.reload();
    expect(timeline.activities.value.map((a) => a.key)).toEqual([
      "email:0",
      "comment:1",
      "email:1",
      "comment:2",
    ]);
  });

  it("records a failed read instead of throwing", async () => {
    const name = freshDoc();
    api.getDocumentPart.mockRejectedValue(new Error("no"));
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));
    expect(timeline.error.value).toBeInstanceOf(Error);
    expect(timeline.activities.value).toEqual([]);
  });
});
