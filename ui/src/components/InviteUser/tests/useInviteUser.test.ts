import { describe, expect, it, vi, beforeEach } from "vitest";

// Capture every resource the composable creates so tests can drive submit/reload
// and inspect the params/url each was given.
interface FakeResource {
  url: string;
  method?: string;
  params: Record<string, unknown>;
  transform?: (data: unknown) => unknown;
  data: unknown;
  loading: boolean;
  error: unknown;
  submit: ReturnType<typeof vi.fn>;
  reload: ReturnType<typeof vi.fn>;
  fetch: ReturnType<typeof vi.fn>;
  __result: unknown;
}

const created: FakeResource[] = [];

vi.mock("frappe-ui", () => ({
  createResource: (config: {
    url: string;
    method?: string;
    params?: Record<string, unknown>;
    transform?: (data: unknown) => unknown;
  }) => {
    const res: FakeResource = {
      url: config.url,
      method: config.method,
      params: config.params ?? {},
      transform: config.transform,
      data: null,
      loading: false,
      error: null,
      __result: null,
      submit: vi.fn((params: Record<string, unknown>) => {
        res.params = params;
        return Promise.resolve(res.__result);
      }),
      reload: vi.fn(),
      fetch: vi.fn(),
    };
    created.push(res);
    return res;
  },
}));

import { useInviteUser } from "../useInviteUser";

/** The most recently created resource whose url contains `fragment`. */
function resourceFor(fragment: string): FakeResource {
  const match = [...created].reverse().find((r) => r.url.includes(fragment));
  if (!match) throw new Error(`no resource created for "${fragment}"`);
  return match;
}

/** The `get_list` resource configured for a given doctype (User vs User Invitation). */
function getListFor(doctype: string | null): FakeResource {
  const match = created.find(
    (r) =>
      r.url.includes("frappe.client.get_list") &&
      (doctype === null
        ? !("doctype" in r.params)
        : (r.params as { doctype?: string }).doctype === doctype)
  );
  if (!match) throw new Error(`no get_list resource for doctype "${doctype}"`);
  return match;
}

let appCounter = 0;
/** Unique appName per test — the composable memoises per appName across calls. */
function freshApp() {
  return `test-app-${appCounter++}`;
}

beforeEach(() => {
  created.length = 0;
});

describe("useInviteUser", () => {
  it("creates the backing resources with the right urls and app scope", () => {
    const appName = freshApp();
    useInviteUser({ appName });
    // roles now come from the hook-derived endpoint, not a Role list
    expect(resourceFor("get_invitable_roles").params).toMatchObject({
      app_name: appName,
    });
    expect(resourceFor("get_pending_invitations").params).toMatchObject({
      app_name: appName,
    });
    // already-invited emails are scoped to the app + pending/accepted
    expect(getListFor("User Invitation").params.filters).toMatchObject({
      app_name: appName,
      status: ["in", ["Pending", "Accepted"]],
    });
    expect(resourceFor("invite_by_email").method).toBe("POST");
    expect(resourceFor("cancel_invitation").method).toBe("PATCH");
    expect(resourceFor("resend_invitation").method).toBe("POST");
  });

  it("invite() forwards emails/roles/redirect/app_name and reloads pending on success", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName, redirectPath: "/crm" });
    const invite = resourceFor("invite_by_email");
    const pending = resourceFor("get_pending_invitations");
    invite.__result = {
      invited_emails: ["a@x.com"],
      disabled_user_emails: [],
      pending_invite_emails: [],
      accepted_invite_emails: [],
    };

    const result = await store.invite("a@x.com", ["Sales User"]);

    expect(invite.submit).toHaveBeenCalledWith({
      emails: "a@x.com",
      roles: ["Sales User"],
      redirect_to_path: "/crm",
      app_name: appName,
    });
    expect(result.invited_emails).toEqual(["a@x.com"]);
    expect(pending.reload).toHaveBeenCalled();
  });

  it("applies transformRoles and merges extraParams", async () => {
    const appName = freshApp();
    const store = useInviteUser({
      appName,
      transformRoles: (roles) => ["Agent", ...roles],
      extraParams: { contact: "C-1" },
    });
    const invite = resourceFor("invite_by_email");
    invite.__result = {
      invited_emails: [],
      disabled_user_emails: [],
      pending_invite_emails: [],
      accepted_invite_emails: [],
    };

    await store.invite("a@x.com", ["Agent Manager"]);

    expect(invite.submit).toHaveBeenCalledWith(
      expect.objectContaining({
        roles: ["Agent", "Agent Manager"],
        contact: "C-1",
      })
    );
  });

  it("cancel() and resend() pass name + app_name", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    const cancel = resourceFor("cancel_invitation");
    const resend = resourceFor("resend_invitation");

    await store.cancel("inv-1");
    expect(cancel.submit).toHaveBeenCalledWith({
      name: "inv-1",
      app_name: appName,
    });

    await store.resend("inv-2");
    expect(resend.submit).toHaveBeenCalledWith({
      name: "inv-2",
      app_name: appName,
    });
  });

  it("searchUsers() queries enabled, non-Website users by name and full_name", () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    const usersRes = getListFor(null); // the get_list with no initial params
    store.searchUsers("ali");
    expect(usersRes.submit).toHaveBeenCalledWith(
      expect.objectContaining({
        doctype: "User",
        filters: { enabled: 1, user_type: ["!=", "Website User"] },
        or_filters: [
          ["User", "name", "like", "%ali%"],
          ["User", "full_name", "like", "%ali%"],
        ],
        fields: ["name", "full_name", "user_image"],
      })
    );
  });

  it("excludes already-invited emails from the user suggestions", () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    const usersRes = getListFor(null);
    const invitedRes = getListFor("User Invitation");
    // resource.data holds the transformed result in frappe-ui
    usersRes.data = usersRes.transform!([
      { name: "a@x.com", full_name: "A" },
      { name: "b@y.com", full_name: "B" },
    ]);
    invitedRes.data = invitedRes.transform!([{ email: "b@y.com" }]);
    // first read of the computed evaluates against the data set above
    expect(store.users.map((u) => u.value)).toEqual(["a@x.com"]);
  });

  it("returns a fresh controller per call (no module-level cache)", () => {
    const appName = freshApp();
    const a = useInviteUser({ appName });
    const countAfterFirst = created.length;
    const b = useInviteUser({ appName });
    // the stale/never-evicted module cache is gone: each call is independent
    expect(b).not.toBe(a);
    // ...and builds its own backing resources
    expect(created.length).toBeGreaterThan(countAfterFirst);
  });

  it("load() lazily fetches roles, pending, and already-invited exactly once", () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    const roles = resourceFor("get_invitable_roles");
    const pending = resourceFor("get_pending_invitations");
    const invited = getListFor("User Invitation");

    // nothing fetched on creation — fetching is lazy
    expect(roles.fetch).not.toHaveBeenCalled();
    expect(pending.fetch).not.toHaveBeenCalled();
    expect(invited.fetch).not.toHaveBeenCalled();

    store.load();
    expect(roles.fetch).toHaveBeenCalledTimes(1);
    expect(pending.fetch).toHaveBeenCalledTimes(1);
    expect(invited.fetch).toHaveBeenCalledTimes(1);

    // idempotent — a second load() is a no-op
    store.load();
    expect(roles.fetch).toHaveBeenCalledTimes(1);
  });
});
