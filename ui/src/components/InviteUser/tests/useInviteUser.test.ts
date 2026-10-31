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

const PENDING = "frappe.core.api.user_invitation.get_pending_invitations";
const INVITED = "frappe.core.api.user_invitation.get_invited_emails";
const INVITE = "frappe.core.api.user_invitation.invite_by_email";

const emptyResult = {
  invited_emails: [],
  disabled_user_emails: [],
  pending_invite_emails: [],
  accepted_invite_emails: [],
};

function callsTo(method: string) {
  return api.runMethod.mock.calls.filter(([called]) => called === method);
}

function pendingCalls() {
  return callsTo(PENDING);
}

/** Answer each user_invitation method; `invited` is the already-invited emails. */
function methodAnswers(pending: unknown[] = [], invited: string[] = ["b@y.com"]) {
  api.runMethod.mockImplementation((method: string) => {
    if (method === PENDING) return Promise.resolve({ data: pending });
    if (method === INVITED) return Promise.resolve({ data: invited });
    return Promise.resolve({ data: emptyResult });
  });
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
  api.listDocuments.mockReset();
  api.runMethod.mockReset();
  methodAnswers();
  api.runDocumentMethod.mockReset().mockResolvedValue({ data: null });
});

describe("useInviteUser", () => {
  it("reads the app's pending invitations by GET through its inviter-gated method", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    const pending = [
      { name: "inv-1", email: "a@x.com", roles: ["Sales User", "Sales Manager"] },
      { name: "inv-2", email: "b@y.com", roles: [] },
    ];
    methodAnswers(pending);
    store.load();
    await vi.waitFor(() => expect(store.loading).toBe(false));
    expect(api.runMethod).toHaveBeenCalledWith(PENDING, { app_name: appName }, { http: "GET" });
    expect(api.listDocuments).not.toHaveBeenCalled();
    expect(store.pendingInvites).toEqual(pending);
  });

  it("invite() forwards emails/roles/redirect/app_name and refreshes pending on success", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName, redirectPath: "/crm" });
    api.runMethod.mockImplementation((method: string) =>
      Promise.resolve({
        data: method === PENDING ? [] : { ...emptyResult, invited_emails: ["a@x.com"] },
      })
    );

    const result = await store.invite("a@x.com", ["Sales User"]);

    expect(api.runMethod).toHaveBeenCalledWith(INVITE, {
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
    methodAnswers([], ["a@x.com"]);
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
      INVITE,
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

    expect(api.runMethod).toHaveBeenCalledWith(INVITE, {
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
    expect(api.runDocumentMethod).toHaveBeenCalledWith(
      "User Invitation",
      "inv-2",
      "resend_invite",
      {},
      { nullable: true },
    );
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

  it("checks only the found emails against the app's invitations, through its inviter-gated method", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    await store.searchUsers("");
    expect(api.runMethod).toHaveBeenCalledWith(
      INVITED,
      { app_name: appName, emails: ["a@x.com", "b@y.com"] },
      { http: "GET" }
    );
    expect(api.listDocuments).not.toHaveBeenCalled();
    expect(store.users.map((u) => u.value)).toEqual(["a@x.com"]);
  });

  it("skips the invitation check when the search found nobody", async () => {
    const appName = freshApp();
    const store = useInviteUser({ appName });
    api.searchDocuments.mockResolvedValue({ data: [] });
    await store.searchUsers("zzz");
    expect(callsTo(INVITED)).toHaveLength(0);
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
    expect(api.runMethod).not.toHaveBeenCalled();

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
    api.runMethod.mockRejectedValue(loadErr);

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
    expect(api.runMethod).not.toHaveBeenCalled();
  });
});
