import { describe, expect, it } from "vitest";
import { toSnapshot, toWire, viewIdFromPath } from "../savedView";
import type { SavedView } from "../types";
import type { FilterField } from "../../../components/Filter/types";
import type { RawMetaField } from "../../../components/FormLayout/types";

const STATUS: FilterField = {
  label: "Status",
  value: "status",
  fieldname: "status",
  fieldtype: "Select",
  options: "Open\nClosed",
};

const RAW_STATUS: RawMetaField = {
  fieldname: "status",
  fieldtype: "Select",
  label: "Status",
  options: "Open\nClosed",
};

function view(overrides: Partial<SavedView> = {}): SavedView {
  return {
    name: "1",
    label: "Open",
    reference_doctype: "Note",
    type: "list",
    ...overrides,
  };
}

describe("toSnapshot", () => {
  it("parses the stored wire shapes into control state", () => {
    const snapshot = toSnapshot(
      view({
        filters: '[["status", "=", "Open"]]',
        order_by: "modified desc",
        columns: '[{"key": "title", "label": "Title", "width": "10rem"}]',
      }),
      [STATUS]
    );

    expect(snapshot.filters).toEqual([
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
    ]);
    expect(snapshot.sort).toEqual([
      { fieldname: "modified", direction: "desc" },
    ]);
    expect(snapshot.columns).toEqual([
      { fieldname: "title", label: "Title", width: "10rem" },
    ]);
  });

  it("accepts already-parsed values as well as JSON strings", () => {
    const snapshot = toSnapshot(
      view({ filters: [["status", "=", "Open"]], columns: [{ key: "title" }] }),
      [STATUS]
    );

    expect(snapshot.filters).toHaveLength(1);
    expect(snapshot.columns).toEqual([
      { fieldname: "title", label: undefined, width: undefined },
    ]);
  });

  it("omits members the view does not store, so restore leaves them at default", () => {
    const snapshot = toSnapshot(view(), [STATUS]);

    expect(snapshot).toEqual({});
  });

  it("never restores quick filter fields — a Saved View carries none", () => {
    const snapshot = toSnapshot(view({ order_by: "name asc" }), [STATUS]);

    expect(snapshot).not.toHaveProperty("quickFilterFields");
  });

  it("treats an empty order_by as unsorted rather than a bogus rule", () => {
    expect(toSnapshot(view({ order_by: "" }), [STATUS])).toEqual({});
  });

  it("survives malformed stored JSON instead of throwing at render time", () => {
    const snapshot = toSnapshot(view({ filters: "{not json", columns: "[" }), [
      STATUS,
    ]);

    expect(snapshot).toEqual({});
  });

  it("drops conditions whose field is missing from Meta", () => {
    const snapshot = toSnapshot(view({ filters: '[["gone", "=", "x"]]' }), [
      STATUS,
    ]);

    expect(snapshot.filters).toEqual([]);
  });
});

describe("toWire", () => {
  it("serializes a snapshot back into the stored wire shapes", () => {
    const snapshot = toSnapshot(
      view({
        filters: '[["status", "=", "Open"]]',
        order_by: "modified desc",
      }),
      [STATUS]
    );

    const wire = toWire(snapshot, [RAW_STATUS]);

    expect(JSON.parse(wire.filters!)).toEqual([["status", "=", "Open"]]);
    expect(wire.order_by).toBe("modified desc");
  });

  it("round-trips a stored view unchanged through parse then serialize", () => {
    const stored = view({ filters: '[["status", "=", "Open"]]' });

    const wire = toWire(toSnapshot(stored, [STATUS]), [RAW_STATUS]);

    expect(JSON.parse(wire.filters!)).toEqual([["status", "=", "Open"]]);
  });

  it("emits an emptied filter list as [] so the server clears the field", () => {
    expect(toWire({ filters: [] }, [RAW_STATUS]).filters).toBe("[]");
  });

  it("omits members the snapshot does not carry", () => {
    expect(
      toWire({ sort: [{ fieldname: "name", direction: "asc" }] }, [])
    ).toEqual({ order_by: "name asc" });
  });

  it("derives the fetch rows from the columns", () => {
    const wire = toWire({ columns: [{ fieldname: "title", label: "Title" }] }, [
      RAW_STATUS,
    ]);

    expect(JSON.parse(wire.rows!)).toEqual(["name", "title"]);
    expect(JSON.parse(wire.columns!)[0].key).toBe("title");
  });
});

describe("viewIdFromPath", () => {
  it("reads the id out of a view path", () => {
    expect(viewIdFromPath("/CRM%20Deal/view/12")).toBe("12");
  });

  it("is null on a list path with no view segment", () => {
    expect(viewIdFromPath("/CRM%20Deal")).toBeNull();
  });

  it("stops at a query string or hash", () => {
    expect(viewIdFromPath("/CRM Deal/view/12?status=Open")).toBe("12");
    expect(viewIdFromPath("/CRM Deal/view/12#top")).toBe("12");
  });

  it("decodes an escaped id", () => {
    expect(viewIdFromPath("/CRM Deal/view/my%20view")).toBe("my view");
  });

  it("ignores a doctype that merely contains the word view", () => {
    expect(viewIdFromPath("/Overview")).toBeNull();
  });
});
