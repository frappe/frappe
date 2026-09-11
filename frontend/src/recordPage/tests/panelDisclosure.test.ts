// `open` and `close` on the panel surface as executable claims: in-page acts on a section
// with a header, resolved at the call and delivered when the replay settles.
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
import { registerRecordPage, resetRegistry } from "../registry";
import type { PanelSectionItem } from "../types";

/** Two built-ins with no header, and one layout section with one. */
const PANEL: PanelSectionItem[] = [
  { name: "identity" },
  { name: "shares" },
  { name: "organization_section", label: "Organization" },
];

function makePage(overrides: Partial<RecordPageHost> = {}) {
  const disclosed: [string, boolean][] = [];
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({}),
    saved: ref({}),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "",
    activateTab: () => {},
    discloseSection: (name, open) => void disclosed.push([name, open]),
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    ...overrides,
  };
  const controller = createRecordPage(host);
  controller.panelSections.provideBuiltins(() => PANEL);
  return { controller, page: controller.page, disclosed };
}

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) =>
    warnings.push(message),
  );
});

describe("the two acts", () => {
  it("hands the section and the direction to the host", () => {
    const { page, disclosed } = makePage();

    page.panelSections.open("organization_section");
    page.panelSections.close("organization_section");

    expect(disclosed).toEqual([
      ["organization_section", true],
      ["organization_section", false],
    ]);
    expect(warnings).toEqual([]);
  });

  it("opens a section the script itself added, once it has a label", () => {
    const { page, disclosed } = makePage();

    page.panelSections.add({ name: "audit", label: "Audit", opened: false });
    page.panelSections.open("audit");

    expect(disclosed).toEqual([["audit", true]]);
  });
});

describe("the ways to miss", () => {
  it("warns on a name the panel does not carry", () => {
    const { page, disclosed } = makePage();

    page.panelSections.open("nope");

    expect(disclosed).toEqual([]);
    expect(warnings).toEqual([
      '[record-page] page.panelSections.open("nope") — no such section; nothing was opened.',
    ]);
  });

  it("warns on a hidden section — `show()` is that verb", () => {
    const { page, disclosed } = makePage();
    page.panelSections.hide("organization_section");

    page.panelSections.close("organization_section");

    expect(disclosed).toEqual([]);
    expect(warnings[0]).toContain("it is hidden — show() reveals a section");
    expect(warnings[0]).toContain("nothing was shut");
  });

  it("warns on a built-in, which has no header to open", () => {
    const { page, disclosed } = makePage();

    page.panelSections.open("shares");

    expect(disclosed).toEqual([]);
    expect(warnings[0]).toContain('page.panelSections.open("shares") — it has no header');
  });

  it("says so when the host cannot open or shut a section", () => {
    const { page } = makePage({ discloseSection: undefined });

    page.panelSections.open("organization_section");

    expect(warnings[0]).toContain("this host cannot open or shut a section");
  });

  it("reports a host that throws, and never rethrows", () => {
    const errors: unknown[] = [];
    vi.spyOn(console, "error").mockImplementation((...args) => void errors.push(args));
    const { page } = makePage({
      discloseSection: () => {
        throw new Error("boom");
      },
    });

    expect(() => page.panelSections.open("organization_section")).not.toThrow();
    expect(String(errors[0]?.[0])).toContain("the host threw");
  });
});

describe("a replay's disclosure", () => {
  it("is delivered once the panel has settled, not from the middle", async () => {
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.panelSections.add({ name: "audit", label: "Audit", opened: false });
        page.panelSections.open("audit");
      },
    });
    const { controller, disclosed } = makePage();

    const replay = controller.refresh();
    expect(disclosed).toEqual([]);
    await replay;

    expect(disclosed).toEqual([["audit", true]]);
  });

  it("keeps the last act on each section, as the reader's own last click would", async () => {
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.panelSections.open("organization_section");
        page.panelSections.close("organization_section");
      },
    });
    const { controller, disclosed } = makePage();

    await controller.refresh();

    expect(disclosed).toEqual([["organization_section", false]]);
  });

  it("is dropped when a later source hides the section before the commit", async () => {
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.panelSections.open("organization_section");
        page.panelSections.hide("organization_section");
      },
    });
    const { controller, disclosed } = makePage();

    await controller.refresh();

    expect(disclosed).toEqual([]);
    expect(warnings[0]).toContain("it is hidden");
  });

  it("still delivers when a later handler throws", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.panelSections.open("organization_section");
        throw new Error("boom");
      },
    });
    const { controller, disclosed } = makePage();

    await controller.refresh();

    expect(disclosed).toEqual([["organization_section", true]]);
  });
});

describe("one name, one owner", () => {
  it("tells a script reaching for a section through page.fields which verb owns it", () => {
    const { page } = makePage({
      meta: ref({ fields: [{ fieldname: "status", fieldtype: "Data" }] }),
    });

    page.fields.hide("shares");
    page.fields.get("organization_section");

    expect(warnings).toEqual([
      '[record-page] page.fields.hide("shares") — a panel section, not a field; page.panelSections.hide("shares") is the verb.',
      '[record-page] page.fields.get("organization_section") — a panel section, not a field; page.panelSections.has("organization_section") is the verb.',
    ]);
  });
});
