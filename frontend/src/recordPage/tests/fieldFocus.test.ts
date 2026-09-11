// `page.fields.focus` as executable claims: the host lands the reader, a read-only field
// gets no cursor, an unknown or hidden one warns, and a replay's focus waits for the commit.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  createResource: () => ({
    data: null,
    loading: false,
    fetch() {},
    reload() {},
  }),
  frappeRequest: vi.fn(),
}));

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { resetFieldWarnings } from "../fields";
import { registerRecordPage, resetRegistry } from "../registry";
import type { RawMetaField } from "@framework/ui/components/FormLayout/types";

const FIELDS: RawMetaField[] = [
  { fieldname: "status", fieldtype: "Select", options: "Open\nWon" },
  { fieldname: "probability", fieldtype: "Percent" },
  { fieldname: "owner_name", fieldtype: "Data", read_only: 1 },
  { fieldname: "secret", fieldtype: "Data", hidden: 1 },
  { fieldname: "rate", fieldtype: "Currency", depends_on: "eval:doc.status == 'Won'" },
];

function makeHost(overrides: Partial<RecordPageHost> = {}) {
  const landed: [string, boolean][] = [];
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ status: "Open" }),
    saved: ref({ status: "Open" }),
    meta: ref({ fields: FIELDS }),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "",
    activateTab: () => {},
    focusField: (fieldname, cursor) => void landed.push([fieldname, cursor]),
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    ...overrides,
  };
  return { host, landed };
}

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  resetFieldWarnings();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) =>
    warnings.push(message),
  );
});

describe("landing on a field", () => {
  it("hands the host the field with a cursor", () => {
    const { host, landed } = makeHost();
    const { page } = createRecordPage(host);

    page.fields.focus("probability");

    expect(landed).toEqual([["probability", true]]);
    expect(warnings).toEqual([]);
  });

  it("a read-only field gets the tab and the scroll, and no cursor", () => {
    const { host, landed } = makeHost();
    const { page } = createRecordPage(host);

    page.fields.focus("owner_name");

    expect(landed).toEqual([["owner_name", false]]);
  });

  it("a script's read_only override is read the same way", () => {
    const { host, landed } = makeHost();
    const { page } = createRecordPage(host);

    page.fields.update("probability", { read_only: 1 });
    page.fields.focus("probability");

    expect(landed).toEqual([["probability", false]]);
  });
});

describe("three ways to miss", () => {
  it("an unknown field warns and moves nobody", () => {
    const { host, landed } = makeHost();
    const { page } = createRecordPage(host);

    page.fields.focus("nope");

    expect(landed).toEqual([]);
    expect(warnings).toEqual([
      '[record-page] page.fields.focus("nope") — no such field; the reader was not moved.',
    ]);
  });

  it("a hidden field warns and names the verb that reveals it", () => {
    const { host, landed } = makeHost();
    const { page } = createRecordPage(host);

    page.fields.focus("secret");

    expect(landed).toEqual([]);
    expect(warnings[0]).toContain("it is hidden — show() reveals a field");
  });

  it("a field its depends_on hides is hidden", () => {
    const { host, landed } = makeHost();
    const { page } = createRecordPage(host);

    page.fields.focus("rate");

    expect(landed).toEqual([]);
    expect(warnings[0]).toContain("it is hidden");
  });

  it("a host with no form says so instead of swallowing the act", () => {
    const { host } = makeHost({ focusField: undefined });
    const { page } = createRecordPage(host);

    page.fields.focus("status");

    expect(warnings[0]).toContain("this host draws no form");
  });
});

describe("inside a replay", () => {
  it("delivers the focus once the replay commits, and only the last one asked for", async () => {
    const { host, landed } = makeHost();
    const order: string[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.fields.focus("status");
        page.fields.focus("probability");
        order.push("refresh");
      },
    });
    const controller = createRecordPage({
      ...host,
      focusField: (fieldname, cursor) => {
        order.push(`land:${fieldname}`);
        host.focusField!(fieldname, cursor);
      },
    });

    await controller.refresh();

    expect(order).toEqual(["refresh", "land:probability"]);
    expect(landed).toEqual([["probability", true]]);
  });

  it("drops a held focus on a field a later source hid", async () => {
    const { host, landed } = makeHost();
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.fields.focus("probability");
        page.fields.hide("probability");
      },
    });
    const controller = createRecordPage(host);

    await controller.refresh();

    expect(landed).toEqual([]);
    expect(warnings.at(-1)).toContain("it is hidden");
  });
});
