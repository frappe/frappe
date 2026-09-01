import { beforeEach, describe, expect, it, vi } from "vitest";

// Hoisted so the factory passed to `vi.mock` can reference them.
const { createResourceMock, state } = vi.hoisted(() => ({
  createResourceMock: vi.fn(),
  state: {
    roles: null as string[] | null,
    permissions: undefined as Record<string, unknown>[] | undefined,
    loading: false,
  },
}));

vi.mock("frappe-ui", () => ({
  createResource: createResourceMock,
  frappeRequest: vi.fn(),
}));

const ROLES_URL = "frappe.core.doctype.user.user.get_current_user_roles";

createResourceMock.mockImplementation((options: any) => {
  const roles = options.url === ROLES_URL;
  return {
    get data() {
      if (roles) return state.roles ?? undefined;
      return {
        docs: [
          {
            name: options.params.doctype,
            fields: [],
            permissions: state.permissions,
          },
        ],
      };
    },
    get loading() {
      return state.loading;
    },
    fetched: false,
    error: null,
    fetch: vi.fn(),
    reload: vi.fn(),
  };
});

import { useDocPermissions } from "../useDocPermissions";
import { resetDoctypeMeta } from "../useDoctypeMeta";
import { resetUserRoles } from "../useUserRoles";

function reset() {
  resetDoctypeMeta();
  resetUserRoles();
  vi.clearAllMocks();
  state.roles = null;
  state.permissions = undefined;
  state.loading = false;
}

describe("useUserRoles' endpoint", () => {
  beforeEach(reset);

  // The composable is useless if this name drifts from the whitelisted method,
  // and nothing else would notice: every other test here mocks the transport, so
  // the URL is never resolved against a server. It was in fact wrong once — the
  // method was left behind when this code was split out of its original branch.
  it("asks the whitelisted method that returns the session user's roles", () => {
    useDocPermissions("Note");

    const urls = createResourceMock.mock.calls.map(([o]: any[]) => o.url);
    expect(urls).toContain(ROLES_URL);
  });

  it("fetches the roles once, however many callers ask", () => {
    useDocPermissions("Note");
    useDocPermissions("ToDo");

    const rolesCalls = createResourceMock.mock.calls.filter(
      ([o]: any[]) => o.url === ROLES_URL
    );
    expect(rolesCalls).toHaveLength(1);
  });
});

describe("field-level access", () => {
  beforeEach(reset);

  it("leaves permlevel 0 to the doc-level rights", () => {
    state.roles = [];
    state.permissions = [];
    const { fieldAccess } = useDocPermissions("Note");

    expect(fieldAccess({ permlevel: 0 })).toBe("write");
    expect(fieldAccess({})).toBe("write");
  });

  it("grants write on a permlevel one of the user's roles writes", () => {
    state.roles = ["Accounts Manager"];
    state.permissions = [
      { role: "Accounts Manager", permlevel: 1, read: 1, write: 1 },
    ];

    expect(useDocPermissions("Note").fieldAccess({ permlevel: 1 })).toBe(
      "write"
    );
  });

  it("grants read only, when the row reads but does not write", () => {
    state.roles = ["Sales User"];
    state.permissions = [{ role: "Sales User", permlevel: 2, read: 1 }];

    expect(useDocPermissions("Note").fieldAccess({ permlevel: 2 })).toBe(
      "read"
    );
  });

  it("refuses a permlevel no role of the user's holds", () => {
    state.roles = ["Sales User"];
    state.permissions = [
      { role: "Accounts Manager", permlevel: 1, read: 1, write: 1 },
    ];

    expect(useDocPermissions("Note").fieldAccess({ permlevel: 1 })).toBe(
      "none"
    );
  });

  it("ignores a DocPerm row for a role the user does not hold", () => {
    state.roles = ["Sales User"];
    state.permissions = [
      { role: "Sales User", permlevel: 1, read: 1 },
      { role: "Accounts Manager", permlevel: 1, read: 1, write: 1 },
    ];

    expect(useDocPermissions("Note").fieldAccess({ permlevel: 1 })).toBe(
      "read"
    );
  });

  // Better a field the server refuses to save than a form that flashes empty.
  it("fails open while the roles are still loading", () => {
    state.roles = null;
    state.permissions = [
      { role: "Accounts Manager", permlevel: 1, read: 1, write: 1 },
    ];

    expect(useDocPermissions("Note").fieldAccess({ permlevel: 1 })).toBe(
      "write"
    );
  });
});

describe("allowedPermlevels", () => {
  beforeEach(reset);

  it("lists the permlevels the user's roles hold the right on, in order", () => {
    state.roles = ["Sales User", "Accounts Manager"];
    state.permissions = [
      { role: "Accounts Manager", permlevel: 2, read: 1, write: 1 },
      { role: "Sales User", permlevel: 1, read: 1 },
      { role: "Sales User", permlevel: 0, read: 1, write: 1 },
    ];
    const { allowedPermlevels } = useDocPermissions("Note");

    expect(allowedPermlevels("read")).toEqual([0, 1, 2]);
    expect(allowedPermlevels("write")).toEqual([0, 2]);
  });

  it("is empty while the meta is still loading", () => {
    expect(useDocPermissions("Note").allowedPermlevels("read")).toEqual([]);
  });
});

describe("doc-level rights", () => {
  beforeEach(reset);

  it("reads the server-computed docinfo permissions", () => {
    const { can } = useDocPermissions("Note", { write: 1, delete: 0 });

    expect(can("write")).toBe(true);
    expect(can("delete")).toBe(false);
  });

  it("refuses everything until docinfo provides them", () => {
    expect(useDocPermissions("Note").can("write")).toBe(false);
  });
});
