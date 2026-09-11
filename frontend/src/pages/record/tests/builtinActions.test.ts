// The framework's own actions: which ones a right unlocks, where each sits, and what delete does.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/router/routeFor", () => ({ routeFor: (doctype: string) => ({ name: "list", doctype }) }));

import { headerMenuBuiltins, quickActionBuiltins } from "../builtinActions";

const names = (perms: Record<string, any>, tagged = false) =>
  quickActionBuiltins(perms, tagged).map((a) => a.name);

function fakePage(confirmed: true | null) {
  return {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    dialog: { danger: vi.fn().mockResolvedValue(confirmed) },
    call: vi.fn().mockResolvedValue(null),
    toast: { success: vi.fn(), error: vi.fn() },
    router: { push: vi.fn().mockResolvedValue(undefined) },
  } as any;
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("quickActionBuiltins", () => {
  it("seeds copy_link always and print only with the right; delete is the header's", () => {
    expect(names({})).toEqual(["copy_link"]);
    expect(names({ print: 1, delete: 1 })).toEqual(["print", "copy_link"]);
    expect(headerMenuBuiltins({}).map((item) => item.name)).toEqual([]);
    const [remove] = headerMenuBuiltins({ delete: 1 });
    expect(remove).toMatchObject({ name: "delete", label: "Delete" });
    expect(remove.display).toBeUndefined();
  });

  it("seeds tags with write, only while the record has none", () => {
    expect(names({ write: 1 })).toEqual(["copy_link", "tags"]);
    expect(names({ write: 1 }, true)).toEqual(["copy_link"]);
    expect(names({}, false)).toEqual(["copy_link"]);
    expect(quickActionBuiltins({ write: 1 }).at(-1)).toMatchObject({ tagging: true });
  });

  it("deletes after a confirmed danger dialog, then leaves for the list", async () => {
    const page = fakePage(true);
    await headerMenuBuiltins({ delete: 1 })[0].run!(page);
    expect(page.call).toHaveBeenCalledWith("frappe.client.delete", {
      doctype: "CRM Deal",
      name: "CRM-DEAL-1",
    });
    expect(page.router.push).toHaveBeenCalledWith({ name: "list", doctype: "CRM Deal" });
  });

  it("does nothing when the dialog is dismissed", async () => {
    const page = fakePage(null);
    await headerMenuBuiltins({ delete: 1 })[0].run!(page);
    expect(page.call).not.toHaveBeenCalled();
    expect(page.router.push).not.toHaveBeenCalled();
  });

  it("refuses to copy without a clipboard, and keeps the page", async () => {
    vi.spyOn(navigator, "clipboard", "get").mockReturnValue(undefined as any);
    const page = fakePage(null);
    await quickActionBuiltins({})[0].run!(page);
    expect(page.toast.error).toHaveBeenCalledWith("Copying needs a secure connection");
  });

  it("opens desk v1's print view for the record", () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    quickActionBuiltins({ print: 1 })[0].run!(fakePage(null));
    expect(open).toHaveBeenCalledWith("/printview?doctype=CRM+Deal&name=CRM-DEAL-1", "_blank");
  });

  it("copies the page address and says so", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.spyOn(navigator, "clipboard", "get").mockReturnValue({ writeText } as any);
    const page = fakePage(null);
    await quickActionBuiltins({})[0].run!(page);
    expect(writeText).toHaveBeenCalledWith(window.location.href);
    expect(page.toast.success).toHaveBeenCalledWith("Link copied");
  });
});
