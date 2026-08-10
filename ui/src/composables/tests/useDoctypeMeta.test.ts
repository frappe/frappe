import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

// Hoisted so the factory passed to `vi.mock` can reference it.
const { createResourceMock } = vi.hoisted(() => ({
  createResourceMock: vi.fn(),
}));

vi.mock("frappe-ui", () => ({
  createResource: createResourceMock,
  frappeRequest: vi.fn(),
}));

createResourceMock.mockImplementation((options: any) => ({
  data: { docs: [{ name: options.params.doctype, fields: [] }] },
  fetched: false,
  loading: false,
  error: null,
  fetch: vi.fn(),
  reload: vi.fn(),
}));

import { resetDoctypeMeta, useDoctypeMeta } from "../useDoctypeMeta";

describe("useDoctypeMeta", () => {
  beforeEach(() => {
    resetDoctypeMeta();
    vi.clearAllMocks();
  });

  it("fetches a doctype's meta once, however many callers ask", () => {
    useDoctypeMeta("Note");
    useDoctypeMeta("Note");

    expect(createResourceMock).toHaveBeenCalledTimes(1);
  });

  it("reads the meta of the doctype it was asked for", () => {
    expect(useDoctypeMeta("Note").meta.value?.name).toBe("Note");
  });

  it("follows a reactive doctype onto the other meta", () => {
    const doctype = ref("Note");
    const { meta } = useDoctypeMeta(doctype);

    expect(meta.value?.name).toBe("Note");

    doctype.value = "Task";

    expect(meta.value?.name).toBe("Task");
    expect(createResourceMock).toHaveBeenCalledTimes(2);
  });

  it("goes back to a meta it already holds rather than refetching it", () => {
    const doctype = ref("Note");
    const { meta } = useDoctypeMeta(doctype);

    doctype.value = "Task";
    expect(meta.value?.name).toBe("Task");
    doctype.value = "Note";

    expect(meta.value?.name).toBe("Note");
    expect(createResourceMock).toHaveBeenCalledTimes(2);
  });
});
