import { describe, expect, it, vi } from "vitest";
import {
  applyFirstPage,
  createHistoryPagination,
  createPagedSources,
} from "../pagination";

vi.mock("frappe-ui", () => ({
  createResource: () => ({ loading: false, submit: () => {} }),
}));

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
});
