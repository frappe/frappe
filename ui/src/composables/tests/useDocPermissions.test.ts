import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Session } from "../../api";

// Hoisted so the factory passed to `vi.mock` can reference them.
const { getMeta, getSession, state } = vi.hoisted(() => ({
  getMeta: vi.fn(),
  getSession: vi.fn(),
  state: {
    roles: null as string[] | null,
    permissions: undefined as Record<string, unknown>[] | undefined,
  },
}));

// Roles and meta both come through the v2 wrapper now.
vi.mock("../../api", () => ({ getMeta, getSession }));

function aSession(roles: string[]): Session {
  return {
    user: {
      name: "alice@example.com",
      full_name: "Alice",
      email: "alice@example.com",
      user_image: null,
    },
    roles,
    lang: "en",
    timezone: "Asia/Kolkata",
    defaults: {},
  };
}

// `roles: null` stands for a session still in flight, so the fetch never settles.
getSession.mockImplementation(() =>
  state.roles === null
    ? new Promise(() => {})
    : Promise.resolve({ data: aSession(state.roles) })
);

getMeta.mockImplementation(async (doctype: string) => ({
  data: { name: doctype, fields: [], permissions: state.permissions },
  children: [],
}));

/** Field access reads the session and the meta once they land, a tick after the call. */
async function access(doctype = "Note") {
  const perms = useDocPermissions(doctype);
  await new Promise((resolve) => setTimeout(resolve, 0));
  return perms;
}

import { useDocPermissions } from "../useDocPermissions";
import { resetDoctypeMeta } from "../useDoctypeMeta";
import { setSession } from "../useSession";
import { resetUserRoles } from "../useUserRoles";

function reset() {
  resetDoctypeMeta();
  resetUserRoles();
  vi.clearAllMocks();
  state.roles = null;
  state.permissions = undefined;
}

describe("where the roles come from", () => {
  beforeEach(reset);

  it("reads the roles a host already published, without fetching", async () => {
    setSession(aSession(["Accounts Manager"]));
    state.permissions = [
      { role: "Accounts Manager", permlevel: 1, read: 1, write: 1 },
    ];

    expect((await access()).fieldAccess({ permlevel: 1 })).toBe("write");
    expect(getSession).not.toHaveBeenCalled();
  });

  it("fetches the session once, however many callers ask", async () => {
    state.roles = [];
    useDocPermissions("Note");
    useDocPermissions("ToDo");
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(getSession).toHaveBeenCalledTimes(1);
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

  it("grants write on a permlevel one of the user's roles writes", async () => {
    state.roles = ["Accounts Manager"];
    state.permissions = [
      { role: "Accounts Manager", permlevel: 1, read: 1, write: 1 },
    ];

    expect((await access()).fieldAccess({ permlevel: 1 })).toBe("write");
  });

  it("grants read only, when the row reads but does not write", async () => {
    state.roles = ["Sales User"];
    state.permissions = [{ role: "Sales User", permlevel: 2, read: 1 }];

    expect((await access()).fieldAccess({ permlevel: 2 })).toBe("read");
  });

  it("refuses a permlevel no role of the user's holds", async () => {
    state.roles = ["Sales User"];
    state.permissions = [
      { role: "Accounts Manager", permlevel: 1, read: 1, write: 1 },
    ];

    expect((await access()).fieldAccess({ permlevel: 1 })).toBe("none");
  });

  it("ignores a DocPerm row for a role the user does not hold", async () => {
    state.roles = ["Sales User"];
    state.permissions = [
      { role: "Sales User", permlevel: 1, read: 1 },
      { role: "Accounts Manager", permlevel: 1, read: 1, write: 1 },
    ];

    expect((await access()).fieldAccess({ permlevel: 1 })).toBe("read");
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

  it("lists the permlevels the user's roles hold the right on, in order", async () => {
    state.roles = ["Sales User", "Accounts Manager"];
    state.permissions = [
      { role: "Accounts Manager", permlevel: 2, read: 1, write: 1 },
      { role: "Sales User", permlevel: 1, read: 1 },
      { role: "Sales User", permlevel: 0, read: 1, write: 1 },
    ];
    const { allowedPermlevels } = await access();

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
