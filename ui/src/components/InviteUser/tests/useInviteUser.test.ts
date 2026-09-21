import { describe, expect, it, vi, beforeEach } from "vitest";

const api = vi.hoisted(() => ({
  searchDocuments: vi.fn(),
  listDocuments: vi.fn(),
  runMethod: vi.fn(),
  runDocumentMethod: vi.fn(),
}));

vi.mock("../../../api", () => ({
  searchDocuments: api.searchDocuments,
  listDocuments: api.listDocuments,
  runMethod: api.runMethod,
  runDocumentMethod: api.runDocumentMethod,
}));

import { useInviteUser } from "../useInviteUser";

const PENDING_FIELDS = ["name", "email", "roles.role"];

const emptyResult = {
  invited_emails: [],
  disabled_user_emails: [],
  pending_invite_emails: [],
  accepted_invite_emails: [],
};

/** Calls to listDocuments that read the pending list (as opposed to the invited check). */
function pendingCalls() {
  return api.listDocuments.mock.calls.filter(
    ([, query]) => (query as { fields: string[] }).fields.join() === PENDING_FIELDS.join()
  );
}

/** Answer listDocuments differently for the pending read and the invited check. */
function listAnswers(pending: unknown[], invited: unknown[] = [{ email: "b@y.com" }]) {
  api.listDocuments.mockImplementation((_doctype, query) =>
    Promise.resolve({
      data: query.fields.join() === PENDING_FIELDS.join() ? pending : invited,
      has_next_page: false,
    })
  );
}

function deferred<T = unknown>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

let appCounter = 0;
function freshApp() {
  return `test-app-${appCounter++}`;
}

beforeEach(() => {
  api.searchDocuments.mockReset().mockResolvedValue({
    data: [
      { value: "a@x.com", label: "A" },
      { value: "b@y.com", label: "B" },
    ],
  });
  api.listDocuments.mockReset().mockResolvedValue({ data: [], has_next_page: false });
  api.runMethod.mockReset().mockResolvedValue({ data: emptyResult });
  api.runDocumentMethod.mockReset().mockResolvedValue({ data: null });
});

describe("useInviteUser", () => {
  it("reads the app's pending invitations joined with their roles, oldest first", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    store.load();
    await vi.waitFor(() => expect(pendingCalls()).toHaveLength(1));
    expect(api.listDocuments).toHaveBeenCalledWith("User Invitation", {
      filters: { status: "Pending", app_name: appName },
      fields: PENDING_FIELDS,
      order_by: "creation asc",
      start: 0,
      limit: 500,
    });
  });

  it("groups the joined rows into one invitation per name, roles in row order", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    listAnswers([
      { name: "inv-1", email: "a@x.com", role: "Sales User" },
      { name: "inv-2", email: "b@y.com", role: null },
      { name: "inv-1", email: "a@x.com", role: "Sales Manager" },
    ]);
    store.load();
    await vi.waitFor(() => expect(store.loading).toBe(false));
    expect(store.pendingInvites).toEqual([
      { name: "inv-1", email: "a@x.com", roles: ["Sales User", "Sales Manager"] },
      { name: "inv-2", email: "b@y.com", roles: [] },
    ]);
  });

  it("follows has_next_page to the second page and merges both", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    api.listDocuments
      .mockResolvedValueOnce({
        data: [{ name: "inv-1", email: "a@x.com", role: "Sales User" }],
        has_next_page: true,
      })
      .mockResolvedValueOnce({
        data: [{ name: "inv-1", email: "a@x.com", role: "Sales Manager" }],
        has_next_page: false,
      });
    store.load();
    await vi.waitFor(() => expect(store.loading).toBe(false));
    expect(pendingCalls().map(([, query]) => query.start)).toEqual([0, 500]);
    expect(store.pendingInvites).toEqual([
      { name: "inv-1", email: "a@x.com", roles: ["Sales User", "Sales Manager"] },
    ]);
  });

  it("invite() forwards emails/roles/redirect/app_name and refreshes pending on success", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName, redirectPath: "/crm" });
    api.runMethod.mockResolvedValue({ data: { ...emptyResult, invited_emails: ["a@x.com"] } });

    const result = await store.invite("a@x.com", ["Sales User"]);

    expect(api.runMethod).toHaveBeenCalledWith("frappe.core.api.user_invitation.invite_by_email", {
      emails: "a@x.com",
      roles: ["Sales User"],
      redirect_to_path: "/crm",
      app_name: appName,
    });
    expect(result.invited_emails).toEqual(["a@x.com"]);
    await vi.waitFor(() => expect(pendingCalls()).toHaveLength(1));
  });

  it("invite() re-runs the held user search, so the invited person leaves the suggestions", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    await store.invite("a@x.com", ["Sales User"]);
    expect(api.searchDocuments).not.toHaveBeenCalled();

    await store.searchUsers("a");
    listAnswers([], [{ email: "a@x.com" }]);
    await store.invite("a@x.com", ["Sales User"]);
    await vi.waitFor(() => expect(api.searchDocuments).toHaveBeenCalledTimes(2));
    expect(api.searchDocuments).toHaveBeenLastCalledWith("User", expect.objectContaining({ txt: "a" }));
    await vi.waitFor(() => expect(store.users.map((u) => u.value)).toEqual(["b@y.com"]));
  });

  it("applies transformRoles and merges extraParams", async () => {
    const appName = freshApp();
    const store = useInviteUser({
      appName,
      transformRoles: (roles) => ["Agent", ...roles],
      extraParams: { contact: "C-1" },
    });

    await store.invite("a@x.com", ["Agent Manager"]);

    expect(api.runMethod).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ roles: ["Agent", "Agent Manager"], contact: "C-1" })
    );
  });

  it("spreads extraParams under the core invite params (core wins on conflict)", async () => {
    const appName = freshApp();
    const store = useInviteUser({
      appName,
      redirectPath: "/crm",
      extraParams: { app_name: "other-app", emails: "spoofed@x.com", contact: "C-9" },
    });

    await store.invite("real@x.com", ["Sales User"]);

    expect(api.runMethod).toHaveBeenCalledWith(expect.any(String), {
      contact: "C-9",
      emails: "real@x.com",
      roles: ["Sales User"],
      redirect_to_path: "/crm",
      app_name: appName,
    });
  });

  it("cancel() and resend() run the invitation's document methods", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });

    await store.cancel("inv-1");
    expect(api.runDocumentMethod).toHaveBeenCalledWith("User Invitation", "inv-1", "cancel_invite");

    await store.resend("inv-2");
    expect(api.runDocumentMethod).toHaveBeenCalledWith("User Invitation", "inv-2", "resend_invite");
  });

  it("cancellingName is the busy row while cancel() is in flight, then null", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    const call = deferred();
    api.runDocumentMethod.mockReturnValue(call.promise);

    const done = store.cancel("inv-1");
    expect(store.cancellingName).toBe("inv-1");
    call.resolve({ data: null });
    await done;
    expect(store.cancellingName).toBeNull();
  });

  it("resendingName is the busy row while resend() is in flight, then null", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    const call = deferred();
    api.runDocumentMethod.mockReturnValue(call.promise);

    const done = store.resend("inv-2");
    expect(store.resendingName).toBe("inv-2");
    call.resolve({ data: null });
    await done;
    expect(store.resendingName).toBeNull();
  });

  it("cancel() refreshes the pending list; resend() does not", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });

    await store.resend("inv-2");
    await Promise.resolve();
    expect(pendingCalls()).toHaveLength(0);

    await store.cancel("inv-1");
    await vi.waitFor(() => expect(pendingCalls()).toHaveLength(1));
  });

  it("searchUsers() searches enabled, non-Website users for the typed text", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    await store.searchUsers("ali");
    expect(api.searchDocuments).toHaveBeenCalledWith("User", {
      txt: "ali",
      filters: { enabled: 1, user_type: ["!=", "Website User"] },
      limit: 20,
    });
  });

  it("checks only the found emails against the app's pending and accepted invitations", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    listAnswers([]);
    await store.searchUsers("");
    expect(api.listDocuments).toHaveBeenCalledWith("User Invitation", {
      filters: {
        app_name: appName,
        status: ["in", ["Pending", "Accepted"]],
        email: ["in", ["a@x.com", "b@y.com"]],
      },
      fields: ["email"],
      limit: 2,
    });
    expect(store.users.map((u) => u.value)).toEqual(["a@x.com"]);
  });

  it("skips the invitation check when the search found nobody", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    api.searchDocuments.mockResolvedValue({ data: [] });
    await store.searchUsers("zzz");
    expect(api.listDocuments).not.toHaveBeenCalled();
    expect(store.users).toEqual([]);
  });

  it("returns a fresh controller per call (no module-level cache)", () => {
    const appName = freshApp();
    const a = useInviteUser({ appName });
    const b = useInviteUser({ appName });
    expect(b).not.toBe(a);
    a.load();
    expect(pendingCalls()).toHaveLength(1);
    b.load();
    expect(pendingCalls()).toHaveLength(2);
  });

  it("load() lazily fetches the pending invitations exactly once", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    expect(api.listDocuments).not.toHaveBeenCalled();

    store.load();
    expect(pendingCalls()).toHaveLength(1);

    store.load();
    await vi.waitFor(() => expect(store.loading).toBe(false));
    expect(pendingCalls()).toHaveLength(1);
  });

  it("error exposes only the invite error (the email-field-scoped one)", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    const inviteErr = { messages: ["Not permitted"] };
    api.runMethod.mockRejectedValue(inviteErr);

    await expect(store.invite("a@x.com", ["Sales User"])).rejects.toBe(inviteErr);

    expect(store.error).toEqual(inviteErr);
    expect(store.loadError).toBeNull();
  });

  it("background failures surface on loadError, never on the email field's error", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    const loadErr = { messages: ["pending read failed"] };
    api.listDocuments.mockRejectedValue(loadErr);

    store.load();
    await vi.waitFor(() => expect(store.loadError).toEqual(loadErr));
    expect(store.error).toBeNull();
  });

  it("a failed cancel() or resend() rejects and lands on loadError", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    const err = { messages: ["gone"] };
    api.runDocumentMethod.mockRejectedValue(err);

    await expect(store.cancel("inv-1")).rejects.toBe(err);
    expect(store.loadError).toEqual(err);
    expect(store.error).toBeNull();
    expect(store.cancellingName).toBeNull();
  });

  it("exposes the host-supplied roles as a static list", () => {
    const appName = freshApp();
    const roles = [
      { label: "Sales User", value: "Sales User" },
      { label: "Sales Manager", value: "Sales Manager" },
    ];
    const store = useInviteUser({ appName, roles });
    expect(store.roles).toEqual(roles);
    expect(api.listDocuments).not.toHaveBeenCalled();
    expect(api.runMethod).not.toHaveBeenCalled();
  });
});
