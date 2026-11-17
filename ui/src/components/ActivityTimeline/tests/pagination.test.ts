import { describe, expect, it, vi } from "vitest";
import {
  applyFirstPage,
  createHistoryPagination,
  createPagedSources,
} from "../pagination";

const runMethod = vi.hoisted(() => vi.fn());
vi.mock("../../../api", () => ({ runMethod }));

describe("history pagination", () => {
  const paginate = (sources = createPagedSources()) =>
    createHistoryPagination("ToDo", "1", { data: [] } as never, sources);

  it("offers no older page before the first page answers", () => {
    expect(paginate().hasNextPage).toBe(false);
  });

  it("offers older emails once the first page says there are some", () => {
    const sources = createPagedSources();
    const pagination = paginate(sources);
    applyFirstPage(sources, { has_more_emails: true });
    expect(pagination.hasNextPage).toBe(true);
  });

  it("appends the older emails the server returns, once, and clears the flag", async () => {
    runMethod.mockResolvedValue({
      data: { activities: [{ type: "email", name: "e0" }], has_more_emails: false },
    });
    const sources = createPagedSources();
    applyFirstPage(sources, { has_more_emails: true });
    const resource = { data: [{ type: "email", name: "e1" }] } as { data: unknown };
    const pagination = createHistoryPagination("ToDo", "1", resource, sources);
    const first = pagination.fetchNextPage();
    expect(pagination.isFetchingNextPage).toBe(true);
    void pagination.fetchNextPage();
    await first;
    expect(runMethod).toHaveBeenCalledTimes(1);
    expect(runMethod).toHaveBeenCalledWith(
      "frappe.desk.form.activity.get_more_email_activities",
      { doctype: "ToDo", name: "1", start: 1 }
    );
    expect((resource.data as unknown[]).length).toBe(2);
    expect(pagination.hasNextPage).toBe(false);
    expect(pagination.isFetchingNextPage).toBe(false);
  });
});
