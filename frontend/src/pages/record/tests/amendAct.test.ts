// The Amend act: when the record is open to amending, and what the button says and opens.
import { describe, expect, it, vi } from "vitest";

vi.mock("@/router/routeFor", () => ({
  routeFor: (doctype: string, name: string) => ({ name: "record", doctype, docname: name }),
  routeForNew: (doctype: string, values: Record<string, unknown>) => ({ name: "new-record", doctype, values }),
}));

const { runMethod } = vi.hoisted(() => ({ runMethod: vi.fn() }));
vi.mock("@framework/ui/api", () => ({ runMethod }));

import { amendable, amendItem, amendmentOf } from "../amendAct";

const meta = { fields: [{ fieldname: "amended_from" }] };
const page = () => ({ doctype: "Invoice", docname: "INV-1", router: { push: vi.fn() } }) as any;

describe("amendable", () => {
  it("holds for a cancelled record whose doctype has amended_from", () => {
    expect(amendable({ docstatus: 2 }, meta)).toBe(true);
  });

  it("fails for a draft, a submitted record, or a doctype without amended_from", () => {
    expect(amendable({ docstatus: 0 }, meta)).toBe(false);
    expect(amendable({ docstatus: 1 }, meta)).toBe(false);
    expect(amendable({ docstatus: 2 }, { fields: [] })).toBe(false);
    expect(amendable({ docstatus: 2 }, null)).toBe(false);
  });
});

describe("amendItem", () => {
  it("reads Amend and opens the New Record page with the draft amendment", async () => {
    const item = amendItem(null);
    const current = page();

    await item.run!(current);

    expect(item).toMatchObject({ label: "Amend", right: "amend", props: { variant: "solid" } });
    expect(current.router.push).toHaveBeenCalledWith({
      name: "new-record",
      doctype: "Invoice",
      values: { __amend_of: "INV-1" },
    });
  });

  it("reads Open amendment on an amended record and opens the newer record", async () => {
    const item = amendItem("INV-1-1");
    const current = page();

    await item.run!(current);

    expect(item.label).toBe("Open amendment");
    expect(current.router.push).toHaveBeenCalledWith({ name: "record", doctype: "Invoice", docname: "INV-1-1" });
  });
});

describe("amendmentOf", () => {
  it("asks the server and reads a name, or false, as the amending record or null", async () => {
    runMethod.mockResolvedValueOnce({ data: "INV-1-1" }).mockResolvedValueOnce({ data: false });
    runMethod.mockResolvedValueOnce({ data: null });

    expect(await amendmentOf("Invoice", "INV-1")).toBe("INV-1-1");
    expect(await amendmentOf("Invoice", "INV-2")).toBeNull();
    expect(await amendmentOf("Invoice", "INV-3")).toBeNull();
    expect(runMethod).toHaveBeenCalledWith(
      "frappe.client.is_document_amended",
      { doctype: "Invoice", docname: "INV-1" },
      { nullable: true }
    );
  });
});
