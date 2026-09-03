// The script-side permission API as executable claims: what `page.perms` holds,
// what `page.roles` answers, and how `fieldAccess` treats a permlevel and a typo.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { computed, ref } from "vue";

const state = vi.hoisted(() => ({
  roles: null as string[] | null,
  meta: null as any,
}));

// Both composables underneath fetch through `createResource`; here they read
// whatever the test staged, so no request is made.
vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
  createResource: (options: any) => ({
    get data() {
      return options.url.endsWith("get_current_user_roles")
        ? state.roles
        : state.meta && { docs: [state.meta] };
    },
    loading: false,
    fetch() {},
    reload() {},
  }),
}));

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { whenLoaded } from "../pagePermissions";
import { resetRegistry } from "../registry";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetUserRoles } from "@framework/ui/composables/useUserRoles";

const FIELDS = [
  { fieldname: "status", fieldtype: "Select", permlevel: 0 },
  { fieldname: "margin", fieldtype: "Currency", permlevel: 1 },
  { fieldname: "secret", fieldtype: "Data", permlevel: 2 },
];

function makeHost(overrides: Partial<RecordPageHost> = {}): RecordPageHost {
  return {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ status: "Open" }),
    saved: ref({ status: "Open" }),
    meta: ref({ name: "CRM Deal", fields: FIELDS }),
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

describe("page.perms", () => {
  beforeEach(reset);

  it("keeps every right, including a doctype's custom Permission Type", () => {
    const { page } = createRecordPage(
      makeHost({ perms: () => ({ read: 1, write: 0, approve_invoice: 1 }) }),
    );

    expect(page.perms.read).toBe(1);
    expect(page.perms.write).toBe(0);
    expect(page.perms.approve_invoice).toBe(1);
  });

  it("drops the two bookkeeping keys that are not rights", () => {
    const { page } = createRecordPage(
      makeHost({
        perms: () => ({ read: 1, if_owner: 1, has_if_owner_enabled: 1 }),
      }),
    );

    expect(Object.keys(page.perms)).toEqual(["read"]);
  });

  it("warns once per typo'd right, naming the doctype", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { page } = createRecordPage(makeHost({ perms: () => ({ read: 1 }) }));

    void page.perms.wrtie;
    void page.perms.wrtie;

    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toContain(
      "page.perms.wrtie is not a right on CRM Deal.",
    );
  });

  it("stays quiet before the rights have loaded", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { page } = createRecordPage(makeHost({ perms: () => ({}) }));

    expect(page.perms.write).toBeUndefined();
    expect(warn).not.toHaveBeenCalled();
  });

  // Two Proxies on one object: read-only is the outer one, so a write is refused
  // before the advisory underneath gets a say, and a read still reaches it.
  it("still warns on an unknown right through the read-only wrapper", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { page } = createRecordPage(makeHost({ perms: () => ({ read: 1 }) }));

    void page.perms.wrtie;
    expect(warn).toHaveBeenCalledTimes(1);

    expect(() => {
      (page.perms as any).write = 1;
    }).toThrow("page.perms.write is read-only");
    expect(warn).toHaveBeenCalledTimes(1);
  });
});

describe("page.roles", () => {
  beforeEach(reset);

  it("is the session user's roles, plain and synchronous", () => {
    state.roles = ["Sales Manager", "Sales User"];
    const { page } = createRecordPage(makeHost());

    expect(page.roles.includes("Sales Manager")).toBe(true);
  });

  it("is an empty array, never null, when roles are unavailable", () => {
    const { page } = createRecordPage(makeHost());

    expect(page.roles).toEqual([]);
  });
});

describe("page.fieldAccess", () => {
  beforeEach(reset);

  it("reads a permlevel'd field against the roles' DocPerm rows", () => {
    state.roles = ["Sales User"];
    state.meta = {
      name: "CRM Deal",
      fields: FIELDS,
      permissions: [
        { role: "Sales User", permlevel: 0, read: 1, write: 1 },
        { role: "Sales User", permlevel: 1, read: 1, write: 0 },
      ],
    };
    const { page } = createRecordPage(makeHost());

    expect(page.fieldAccess("status")).toBe("write");
    expect(page.fieldAccess("margin")).toBe("read");
    expect(page.fieldAccess("secret")).toBe("none");
  });

  it("answers none for a fieldname the meta does not have, and warns", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { page } = createRecordPage(makeHost());

    expect(page.fieldAccess("staus")).toBe("none");
    expect(warn.mock.calls[0][0]).toContain('page.fieldAccess("staus")');
  });

  it("fails open while the meta is still loading", () => {
    const { page } = createRecordPage(makeHost({ meta: ref(null) }));

    expect(page.fieldAccess("anything")).toBe("write");
  });
});

// The replay waits on this, so a handler never reads roles that have not landed.
describe("the gate the replay waits on", () => {
  it("holds until the permission sources have loaded", async () => {
    const loading = ref(true);
    let resolved = false;
    void whenLoaded(computed(() => loading.value)).then(
      () => (resolved = true),
    );

    await Promise.resolve();
    expect(resolved).toBe(false);

    loading.value = false;
    await new Promise((done) => setTimeout(done));
    expect(resolved).toBe(true);
  });

  it("resolves at once when they already have", async () => {
    await expect(whenLoaded(computed(() => false))).resolves.toBeUndefined();
  });
});

function reset() {
  state.roles = null;
  state.meta = null;
  resetRegistry();
  resetDoctypeMeta();
  resetUserRoles();
  vi.restoreAllMocks();
}
