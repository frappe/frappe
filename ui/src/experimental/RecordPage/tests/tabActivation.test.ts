// `activate` on both tab strips (wayfinder ticket 75) as executable claims: a
// verb rather than a writable `active`, three ways to miss, a name resolved at
// the moment of the call, and a replay's move delivered when the strip settles.
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
import type { FormLayoutSchema } from "../../../components/FormLayout/types";

const RECORD_TABS = [
  { name: "activity", label: "Activity" },
  { name: "emails", label: "Emails" },
  { name: "details", label: "Details" },
];

/** One named tab and one the doc's `with_products` decides. */
const LAYOUT: FormLayoutSchema = [
  { name: "lead_details", label: "Lead Details", sections: [] },
  {
    name: "products",
    label: "Products",
    dependsOn: "eval:doc.with_products",
    sections: [],
  },
];

/**
 * The host's two halves of activation, recorded rather than performed: where
 * the reader is *kept* is the host's business, and the engine's claim is only
 * about what it hands over and when.
 */
function makeHost(overrides: Partial<RecordPageHost> = {}) {
  const moved: string[] = [];
  const movedInForm: string[] = [];
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ with_products: 0 }),
    saved: ref({}),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "activity",
    activateTab: (name) => void moved.push(name),
    formLayout: () => LAYOUT,
    activeFormTab: () => "lead_details",
    activateFormTab: (identity) => void movedInForm.push(identity),
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    ...overrides,
  };
  return { host, moved, movedInForm };
}

function makePage(overrides: Partial<RecordPageHost> = {}) {
  const { host, moved, movedInForm } = makeHost(overrides);
  const controller = createRecordPage(host);
  controller.tabs.provideBuiltins(() => RECORD_TABS as any[]);
  return { controller, page: controller.page, moved, movedInForm };
}

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) =>
    warnings.push(message),
  );
});

describe("moving the reader", () => {
  it("hands the record strip's tab to the host, and nothing else", () => {
    const { page, moved, movedInForm } = makePage();

    page.tabs.activate("emails");

    expect(moved).toEqual(["emails"]);
    expect(movedInForm).toEqual([]);
    expect(warnings).toEqual([]);
  });

  it("hands the form strip's identity to its own host hook", () => {
    const { page, moved, movedInForm } = makePage();

    page.formTabs.activate("lead_details");

    expect(movedInForm).toEqual(["lead_details"]);
    expect(moved).toEqual([]);
  });

  it("moves the reader to a tab the script itself added", () => {
    const { page, moved } = makePage();

    page.tabs.add({ name: "audit", label: "Audit" });
    page.tabs.activate("audit");

    expect(moved).toEqual(["audit"]);
  });

  it("resolves during load against the strip the host has, not the one it draws", () => {
    // The gap the pre-ready window opens: the host renders nothing until the
    // first replay commits, while the surface already holds the built-ins. The
    // strip a name resolves against is the surface's, so an activation before
    // `ready` lands — and the reader arrives on it when the strip paints.
    const { controller, page, moved } = makePage();

    expect(controller.ready.value).toBe(false);
    page.tabs.activate("details");

    expect(moved).toEqual(["details"]);
  });

  it("writes the form strip's intent even where the reader is not in the form", () => {
    // Not a queued activation: the identity resolved against the layout now,
    // and this is the answer to the question the strip asks when it mounts.
    const { page, movedInForm } = makePage({ activeFormTab: () => "" });

    page.formTabs.activate("lead_details");

    expect(movedInForm).toEqual(["lead_details"]);
  });
});

describe("the three ways to miss", () => {
  it("warns and stays put on a tab the strip does not carry", () => {
    const { page, moved } = makePage();

    page.tabs.activate("nope");

    expect(moved).toEqual([]);
    expect(warnings).toEqual([
      '[record-page] page.tabs.activate("nope") — no such tab; the reader was not moved.',
    ]);
  });

  it("warns and stays put on a hidden tab — `show()` is that verb", () => {
    const { page, moved } = makePage();
    page.tabs.hide("emails");

    page.tabs.activate("emails");

    expect(moved).toEqual([]);
    expect(warnings[0]).toContain("it is hidden — show() reveals a tab");
  });

  it("counts a tab `depends_on` has closed as hidden on the form strip too", () => {
    const { page, movedInForm } = makePage();

    page.formTabs.activate("products");

    expect(movedInForm).toEqual([]);
    expect(warnings[0]).toContain("it is hidden");
  });

  it("names the other strip when the name belongs to it", () => {
    const { page, moved, movedInForm } = makePage();

    page.tabs.activate("lead_details");
    page.formTabs.activate("emails");

    expect(moved).toEqual([]);
    expect(movedInForm).toEqual([]);
    expect(warnings[0]).toContain(
      `it is on the form's strip — page.formTabs.activate("lead_details")`,
    );
    expect(warnings[1]).toContain(
      `it is on the record's strip — page.tabs.activate("emails")`,
    );
  });

  it("says nothing about the form's strip while its layout is still loading", () => {
    // "The administrator never authored this" and "it has not arrived yet" are
    // the same answer in that window, and `hide`/`show`/`update` already keep
    // quiet in it. The move is dropped, not queued.
    const { page, movedInForm } = makePage({ formLayout: () => [] });

    page.formTabs.activate("lead_details");

    expect(movedInForm).toEqual([]);
    expect(warnings).toEqual([]);
  });

  it("says so when the host draws the form's strip but cannot move it", () => {
    const { page } = makePage({ activateFormTab: undefined });

    page.formTabs.activate("lead_details");

    expect(warnings[0]).toContain("cannot move the reader on that strip");
  });

  it("says so every time, because each miss is a move that did not happen", () => {
    const { page } = makePage();

    page.tabs.activate("nope");
    page.tabs.activate("nope");

    expect(warnings).toHaveLength(2);
  });
});

describe("why this is a verb and not a writable `active`", () => {
  it("leaves `active` reading the tab the reader is really on", () => {
    // The round trip an assignment could not survive: `active` is derived from
    // what the strip can show, so `page.tabs.active = 'nope'` would read back
    // as something the script never wrote. A verb can say so instead.
    const { page } = makePage();

    page.tabs.activate("nope");

    expect(page.tabs.active).toBe("activity");
    expect(warnings).toHaveLength(1);
  });
});

describe("a replay's activation", () => {
  it("is delivered once the strip has settled, not from the middle", async () => {
    // The name resolves against the staged strip — the script can see its own
    // work — but the reader is moved only after the commit, since until then
    // the host is still rendering the strip the tab is not on yet.
    const seen: boolean[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.tabs.add({ name: "audit", label: "Audit" });
        page.tabs.activate("audit");
        seen.push(page.tabs.has("audit"));
      },
    });
    const { controller, moved } = makePage();

    const replay = controller.refresh();
    expect(moved).toEqual([]);
    await replay;

    expect(seen).toEqual([true]);
    expect(moved).toEqual(["audit"]);
    expect(controller.tabs.visible().map((tab) => tab.name)).toContain("audit");
  });

  it("keeps the last move on each strip, as the reader's own last click would", async () => {
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.tabs.activate("emails");
        page.tabs.activate("details");
        page.formTabs.activate("lead_details");
      },
    });
    const { controller, moved, movedInForm } = makePage();

    await controller.refresh();

    expect(moved).toEqual(["details"]);
    expect(movedInForm).toEqual(["lead_details"]);
  });

  it("still moves the reader when a later handler throws", async () => {
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.tabs.activate("emails");
        throw new Error("boom");
      },
    });
    const { controller, moved } = makePage();

    await controller.refresh();

    expect(moved).toEqual(["emails"]);
  });

  it("is dropped when a later source takes the tab off the strip", async () => {
    // The held move is re-read against the strip that settled, not delivered on
    // the strength of the strip it was decided against — otherwise the reader
    // lands on `?tab=emails` with no `emails` to resolve it, which is the
    // fallback-tab dumping a miss exists to prevent.
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.tabs.activate("emails");
        page.tabs.hide("emails");
      },
    });
    const { controller, moved } = makePage();

    await controller.refresh();

    expect(moved).toEqual([]);
    expect(warnings[0]).toContain("it left the strip before the replay settled");
  });

  it("keeps the page up when the host's own navigation throws", async () => {
    // The release runs inside `refresh`'s `finally`: a throw escaping it would
    // strand `ready` false and leave the strip a skeleton for good.
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => page.tabs.activate("emails"),
    });
    const { controller } = makePage({
      activateTab: () => {
        throw new Error("a router guard said no");
      },
    });
    vi.spyOn(console, "error").mockImplementation(() => {});

    await expect(controller.refresh()).resolves.toBeUndefined();
    expect(controller.ready.value).toBe(true);
  });

  it("misses a tab that only appears in the *next* replay, and is not queued", async () => {
    let addAudit = false;
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        if (addAudit) page.tabs.add({ name: "audit", label: "Audit" });
      },
    });
    const { controller, page, moved } = makePage();

    page.tabs.activate("audit");
    addAudit = true;
    await controller.refresh();

    expect(moved).toEqual([]);
    expect(warnings[0]).toContain("no such tab");
  });
});
