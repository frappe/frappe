// The event vocabulary's firing semantics as executable claims.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

// The page only borrows `call` and `toast`; the real barrel drags icon plugins in.
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
import { withRegisteringSource } from "../context";
import { resetCustomizationErrorReports } from "../reportError";
import { resetRowWarnings } from "../rows";
import { call as mockedCall } from "frappe-ui";

function makeHost(overrides: Partial<RecordPageHost> = {}): RecordPageHost {
  return {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ status: "Open" }),
    saved: ref({ status: "Open" }),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "activity",
    activateTab: () => {},
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    ...overrides,
  };
}

function reportedFailures() {
  return (mockedCall as any).mock.calls
    .filter(([method]: [string]) =>
      method.includes("report_customization_error"),
    )
    .map(([, payload]: [string, any]) => `${payload.source}.${payload.event}`);
}

describe("fireEvent", () => {
  beforeEach(() => {
    resetRegistry();
    resetCustomizationErrorReports();
    (mockedCall as any).mockReset();
  });

  it("propagates a beforeSave throw so the host can abort the save", async () => {
    registerRecordPage("CRM Deal", {
      beforeSave: () => {
        throw new Error("Amount required");
      },
    });
    const controller = createRecordPage(makeHost());
    await expect(controller.fireEvent("beforeSave")).rejects.toThrow(
      "Amount required",
    );
  });

  it("stops later beforeSave handlers once one vetoes", async () => {
    const ran: string[] = [];
    await withRegisteringSource("first", async () => {
      registerRecordPage("CRM Deal", {
        beforeSave: () => {
          ran.push("first");
          throw new Error("veto");
        },
      });
    });
    await withRegisteringSource("second", async () => {
      registerRecordPage("CRM Deal", { beforeSave: () => ran.push("second") });
    });
    const controller = createRecordPage(makeHost());
    await expect(controller.fireEvent("beforeSave")).rejects.toThrow("veto");
    expect(ran).toEqual(["first"]);
  });

  it("isolates a throw from every other event", async () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    const ran: string[] = [];
    await withRegisteringSource("first", async () => {
      registerRecordPage("CRM Deal", {
        onRefresh: () => {
          throw new Error("broken script");
        },
      });
    });
    await withRegisteringSource("second", async () => {
      registerRecordPage("CRM Deal", { onRefresh: () => ran.push("second") });
    });
    const controller = createRecordPage(makeHost());
    await controller.refresh();
    expect(ran).toEqual(["second"]);
    expect(errors).toHaveBeenCalled();
    errors.mockRestore();
  });
});

// The four top-level keys are camelCase with no dual-accept: the old spellings
// are legal fieldnames, which is the collision the rename removes.
describe("the event vocabulary is camelCase (ticket 74)", () => {
  beforeEach(() => resetRegistry());

  it("never fires a handler under one of the retired snake_case keys", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const ran: string[] = [];
    registerRecordPage("CRM Deal", {
      refresh: () => ran.push("refresh"),
      before_save: () => ran.push("before_save"),
      after_save: () => ran.push("after_save"),
      on_tab_change: () => ran.push("on_tab_change"),
    });
    const controller = createRecordPage(makeHost());

    await controller.refresh();
    for (const event of ["beforeSave", "afterSave", "onTabChange"])
      await controller.fireEvent(event);

    expect(ran).toEqual([]);
  });

  // `page.refresh()` is a different symbol from the `onRefresh` key and did not
  // move: it is the imperative verb a handler calls to force its own replay.
  it("keeps page.refresh() as the verb that re-fires onRefresh", async () => {
    let fired = 0;
    registerRecordPage("CRM Deal", { onRefresh: () => (fired += 1) });
    const controller = createRecordPage(makeHost());
    await controller.refresh();
    expect(fired).toBe(1);

    await controller.page.refresh();
    expect(fired).toBe(2);
  });
});

describe("page.tabs.active", () => {
  it("reads the tab the host's strip resolves", () => {
    resetRegistry();
    const controller = createRecordPage(
      makeHost({ activeTab: () => "audit_log" }),
    );
    expect(controller.page.tabs.active).toBe("audit_log");
  });
});

describe("unknown handler keys", () => {
  beforeEach(() => resetRegistry());

  const fields = [
    { fieldname: "status", fieldtype: "Select" },
    { fieldname: "items", fieldtype: "Table", options: "Deal Item" },
  ];

  const childFields = [
    { fieldname: "qty", fieldtype: "Int" },
    { fieldname: "rate", fieldtype: "Currency" },
  ];

  it("warns once, after meta arrives, for a key that will never fire", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    registerRecordPage("CRM Deal", { after_svae: () => {} });
    const meta = ref<any>(null);
    const controller = createRecordPage(makeHost({ meta }));
    await controller.refresh();
    meta.value = { fields };
    await controller.refresh();
    await controller.refresh();
    const typoWarnings = warnings.mock.calls.filter((call) =>
      String(call[0]).includes("after_svae"),
    );
    expect(typoWarnings).toHaveLength(1);
    warnings.mockRestore();
  });

  it("accepts events, fieldnames and a table's nested block", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    registerRecordPage("CRM Deal", {
      onRefresh: () => {},
      beforeSave: () => {},
      afterSave: () => {},
      onTabChange: () => {},
      status: () => {},
      items: {
        onAdd: () => {},
        onRemove: () => {},
        qty: () => {},
      },
    });
    const controller = createRecordPage(
      makeHost({ meta: ref({ fields }), childFields: () => childFields }),
    );
    await controller.refresh();
    expect(warnings).not.toHaveBeenCalled();
    warnings.mockRestore();
  });

  // Nothing commits under a table's own name, so its bare fieldname is not a key.
  it("rejects a Table fieldname, its underscore keys, and an unknown child field", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    registerRecordPage("CRM Deal", {
      items: () => {},
      items_add: () => {},
      "items.nope": () => {},
    });
    const controller = createRecordPage(
      makeHost({ meta: ref({ fields }), childFields: () => childFields }),
    );
    await controller.refresh();
    const rejected = warnings.mock.calls.map((call) => String(call[0]));
    expect(rejected.filter((line) => line.includes("never fire"))).toHaveLength(3);
    warnings.mockRestore();
  });

  // A Table MultiSelect has no per-cell editing, so a child-field key on one could never fire.
  it("gives a Table MultiSelect add and remove only", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    registerRecordPage("CRM Deal", {
      labels: {
        onAdd: () => {},
        onRemove: () => {},
        label: () => {},
      },
    });
    const controller = createRecordPage(
      makeHost({
        meta: ref({
          fields: [
            { fieldname: "labels", fieldtype: "Table MultiSelect", options: "Tag Link" },
          ],
        }),
        childFields: () => [{ fieldname: "label", fieldtype: "Link" }],
      }),
    );
    await controller.refresh();
    const rejected = warnings.mock.calls.map((call) => String(call[0]));
    expect(rejected.filter((line) => line.includes("never fire"))).toHaveLength(1);
    expect(rejected[0]).toContain("labels.label");
    warnings.mockRestore();
  });

  // The child meta lands with the parent's, but a host that has none must not
  // accuse a correct key of being a typo.
  it("stays quiet about a table whose child fields it cannot see", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    registerRecordPage("CRM Deal", { "items.anything": () => {} });
    const controller = createRecordPage(makeHost({ meta: ref({ fields }) }));
    await controller.refresh();
    expect(warnings).not.toHaveBeenCalled();
    warnings.mockRestore();
  });

  // Once per child doctype for the session, not once per controller: navigating
  // between records of the same doctype must not restate the same fact.
  it("warns once when a child doctype has a field named trigger (ticket 43 §3)", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    resetRowWarnings();
    registerRecordPage("CRM Deal", { onRefresh: () => {} });
    const controller = createRecordPage(
      makeHost({
        meta: ref({ fields }),
        childFields: () => [
          ...childFields,
          { fieldname: "trigger", fieldtype: "Data" },
        ],
      }),
    );
    await controller.refresh();
    await createRecordPage({
      ...makeHost({
        meta: ref({ fields }),
        childFields: () => [
          ...childFields,
          { fieldname: "trigger", fieldtype: "Data" },
        ],
      }),
    }).refresh();
    const shadowed = warnings.mock.calls.filter((call) =>
      String(call[0]).includes("shadowed by the row handle"),
    );
    expect(shadowed).toHaveLength(1);
    warnings.mockRestore();
  });

  // The two child fieldnames that can still collide are named at load.
  it("warns when a child doctype has a field named onAdd or onRemove (ticket 54)", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    resetRowWarnings();
    registerRecordPage("CRM Deal", { onRefresh: () => {} });
    await createRecordPage(
      makeHost({
        meta: ref({ fields }),
        childFields: () => [
          ...childFields,
          { fieldname: "onAdd", fieldtype: "Check" },
          { fieldname: "onRemove", fieldtype: "Check" },
        ],
      }),
    ).refresh();
    const collisions = warnings.mock.calls
      .map((call) => String(call[0]))
      .filter((line) => line.includes("collides with the table's"));
    expect(collisions).toHaveLength(2);
    expect(collisions[0]).toContain("Deal Item.onAdd");
    warnings.mockRestore();
  });

  // The collision is a misfire: editing the child field commits under the same
  // string the row-added event dispatches.
  it("routes a colliding child field's commit into the table's lifecycle handler", async () => {
    const fired: string[] = [];
    registerRecordPage("CRM Deal", { items: { onAdd: () => fired.push("onAdd") } });
    const controller = createRecordPage(
      makeHost({ meta: ref({ fields }), childFields: () => childFields }),
    );
    await controller.fireEvent("items.onAdd", { parentfield: "items", key: "name:a" });
    expect(fired).toEqual(["onAdd"]);
  });

  // The shadow check reads the child meta, which can land after the parent's,
  // so latching on the parent alone would drop the warning for the session.
  it("still warns when the child meta lands after the parent's", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    resetRowWarnings();
    registerRecordPage("CRM Deal", { onRefresh: () => {} });
    let child: any[] | undefined = undefined;
    const controller = createRecordPage(
      makeHost({ meta: ref({ fields }), childFields: () => child }),
    );
    await controller.refresh();
    child = [...childFields, { fieldname: "onAdd", fieldtype: "Check" }];
    await controller.refresh();
    const collisions = warnings.mock.calls
      .map((call) => String(call[0]))
      .filter((line) => line.includes("collides with the table's"));
    expect(collisions).toHaveLength(1);
    warnings.mockRestore();
  });

  // A block under something that holds no rows is one mistake, not one per
  // handler in it — and naming the table beats naming each dead key.
  it("names the table once when a nested block is not on a child table", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    registerRecordPage("CRM Deal", {
      status: { onAdd: () => {}, qty: () => {} },
    });
    await createRecordPage(
      makeHost({ meta: ref({ fields }), childFields: () => childFields }),
    ).refresh();
    const rejected = warnings.mock.calls
      .map((call) => String(call[0]))
      .filter((line) => line.includes("not a child table"));
    expect(rejected).toHaveLength(1);
    expect(rejected[0]).toContain("status");
    warnings.mockRestore();
  });

  it("reports a handler throw, but never a beforeSave veto (ticket 19 §1)", async () => {
    withRegisteringSource("page-script:A", async () =>
      registerRecordPage("CRM Deal", {
        onRefresh: () => {
          throw new Error("boom");
        },
        beforeSave: () => {
          throw new Error("veto");
        },
      }),
    );
    const controller = createRecordPage(makeHost());
    vi.spyOn(console, "error").mockImplementation(() => {});

    await controller.fireEvent("onRefresh");
    await expect(controller.fireEvent("beforeSave")).rejects.toThrow("veto");

    expect(reportedFailures()).toContain("page-script:A.onRefresh");
    expect(reportedFailures()).not.toContain("page-script:A.beforeSave");
  });
});

describe("the replay clears the field overlay too (ticket 42)", () => {
  it("drops every override before re-firing, so a condition is a plain if", async () => {
    let stage = "Open";
    registerRecordPage("CRM Deal", {
      // No `else` branch anywhere: the overlay is gone before every re-fire.
      onRefresh: (page) => {
        if (stage === "Won") page.fields.hide("discount");
      },
    });
    const controller = createRecordPage(makeHost());

    stage = "Won";
    await controller.refresh();
    expect(controller.fields.resolve()).toEqual({
      discount: { override: { hidden: true } },
    });

    stage = "Open";
    await controller.refresh();
    expect(controller.fields.resolve()).toEqual({});
  });

  // The replay stages its ops, so the commit has to happen on the way out of a
  // failed replay too, or the overlay freezes on the previous one for good.
  it("commits what a failed replay managed to record", async () => {
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.fields.hide("discount");
        throw new Error("boom");
      },
    });
    const controller = createRecordPage(makeHost());
    vi.spyOn(console, "error").mockImplementation(() => {});

    await controller.refresh();

    expect(controller.fields.resolve()).toEqual({
      discount: { override: { hidden: true } },
    });
  });
});
