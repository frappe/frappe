import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EmailAccount } from "../types";

const call = vi.fn();
vi.mock("frappe-ui", async (importOriginal) => {
  const ui = await importOriginal<typeof import("frappe-ui")>();
  // the list resource fetches through this, so one fake backend answers it and `call`
  ui.setConfig("resourceFetcher", ({ url, params }: { url: string; params: object }) =>
    call(url, params),
  );
  return { ...ui, call: (...args: unknown[]) => call(...args) };
});

const { useEmailAccounts } = await import("../useEmailAccounts");
const { emptyForm, services, takeSignInStarted } = await import("../services");

const CONNECT =
  "frappe.integrations.frappe_providers.email_oauth.initiate_mailbox_connect";

const ACCOUNTS = [
  {
    name: "Support",
    email_account_name: "Support",
    service: "Outlook.com",
    auth_method: "OAuth",
    connected_app: "relay-app",
    token_uri: "frappe-cloud-relay:microsoft",
    connected_user: "admin@example.com",
    enable_incoming: 1,
    enable_outgoing: 1,
    default_incoming: 1,
    default_outgoing: 0,
  },
  {
    name: "Sales",
    email_account_name: "Sales",
    service: "GMail",
    auth_method: "Basic",
    enable_incoming: 0,
    enable_outgoing: 0,
    default_incoming: 0,
    default_outgoing: 0,
  },
  {
    name: "Legacy",
    email_account_name: "Legacy",
    service: "Outlook.com",
    auth_method: "OAuth",
    connected_app: "own-app",
    token_uri: "https://login.microsoftonline.com/token",
    enable_incoming: 1,
    enable_outgoing: 1,
    default_incoming: 0,
    default_outgoing: 1,
  },
];

function backend({ tokens = { "relay-app": false, "own-app": true } } = {}) {
  call.mockImplementation(async (method: string, args: Record<string, any>) => {
    if (method === "frappe.client.get_list" && args.doctype === "Email Account")
      return ACCOUNTS;
    if (method.endsWith("has_token"))
      return tokens[args.connected_app as keyof typeof tokens];
    if (method === "frappe.client.set_value")
      return { name: args.name, ...args.fieldname };
    if (method === "frappe.client.rename_doc") return args.new_name;
    if (method === "frappe.client.insert")
      return { name: args.doc.email_account_name };
    if (method.endsWith("initiate_mailbox_connect"))
      return "https://login.example.com/authorize";
    return null;
  });
}

const sales = (c: { accounts: EmailAccount[] }) =>
  c.accounts.find((a) => a.name === "Sales")!;

const calls = (method: string) =>
  call.mock.calls.filter(([m]) => m === method).map(([, a]) => a);

beforeEach(() => {
  call.mockReset();
  backend();
});

describe("useEmailAccounts", () => {
  it("loads accounts with how they sign in and what needs attention", async () => {
    const c = useEmailAccounts("HD Ticket");
    await c.load();

    // Sales neither receives nor sends, so it goes last
    expect(c.accounts.map((a) => [a.name, a.authKind, a.status])).toEqual([
      ["Support", "oauth", "needs-reconnect"],
      ["Legacy", "oauth-custom", "active"],
      ["Sales", "password", "active"],
    ]);
    expect(calls("frappe.client.get_list")[0]).toMatchObject({
      order_by: "creation desc",
    });
    expect(
      calls(
        "frappe.integrations.doctype.connected_app.connected_app.has_token",
      ),
    ).toContainEqual({
      connected_app: "relay-app",
      connected_user: "admin@example.com",
    });
  });

  it("makes a new account the default only where no account is", async () => {
    const listed = call.getMockImplementation()!;
    call.mockImplementation(async (method: string, args: Record<string, any>) =>
      method === "frappe.client.get_list" && args.doctype === "Email Account"
        ? ACCOUNTS.map((a) => ({ ...a, default_outgoing: 0 }))
        : listed(method, args),
    );
    const c = useEmailAccounts("HD Ticket");
    await c.load();
    await c.create(services[0], {
      ...emptyForm(),
      email_account_name: "Support Inbox",
    });

    const [{ doc }] = calls("frappe.client.insert");
    expect(doc.default_outgoing).toBe(1);
    expect(doc).not.toHaveProperty("default_incoming");
  });

  it("creates through frappe.client.insert, then reloads", async () => {
    const c = useEmailAccounts("HD Ticket");
    await c.create(services[0], {
      ...emptyForm(),
      email_account_name: "Support Inbox",
    });

    expect(calls("frappe.client.insert")).toEqual([
      {
        doc: expect.objectContaining({
          doctype: "Email Account",
          email_account_name: "Support Inbox",
          service: "GMail",
          imap_folder: [{ folder_name: "INBOX", append_to: "HD Ticket" }],
        }),
      },
    ]);
    expect(c.accounts.map((a) => a.name)).toEqual([
      "Support",
      "Legacy",
      "Sales",
    ]);
  });

  it("keeps the old name for the record when its changes fail to save", async () => {
    const c = useEmailAccounts("ToDo");
    await c.load();
    const rejected = new Error("Could not connect to outgoing email server");
    const save = call.getMockImplementation()!;
    call.mockImplementation(async (method, args) => {
      if (method === "frappe.client.set_value") throw rejected;
      return save(method, args);
    });

    await expect(
      c.update(sales(c), { enable_outgoing: 1 }, "Sales Team"),
    ).rejects.toBe(rejected);
    expect(calls("frappe.client.rename_doc")).toEqual([]);
  });

  it("reloads the saved changes when the rename fails", async () => {
    const c = useEmailAccounts("ToDo");
    await c.load();
    const rejected = new Error("Sales Team already exists");
    const save = call.getMockImplementation()!;
    call.mockImplementation(async (method, args) => {
      if (method === "frappe.client.rename_doc") throw rejected;
      return save(method, args);
    });
    const loads = calls("frappe.client.get_list").length;

    await expect(
      c.update(sales(c), { enable_outgoing: 1 }, "Sales Team"),
    ).rejects.toBe(rejected);
    expect(calls("frappe.client.get_list")).toHaveLength(loads + 1);
  });

  it("saves the changes on the current name, then renames", async () => {
    const c = useEmailAccounts("ToDo");
    await c.load();
    await c.update(sales(c), { enable_incoming: 1 }, "Sales Team");

    expect(
      call.mock.calls
        .map(([method]) => method)
        .filter(
          (m) =>
            m === "frappe.client.set_value" || m === "frappe.client.rename_doc",
        ),
    ).toEqual(["frappe.client.set_value", "frappe.client.rename_doc"]);
    expect(calls("frappe.client.set_value")).toEqual([
      {
        doctype: "Email Account",
        name: "Sales",
        fieldname: { enable_incoming: 1 },
      },
    ]);
    expect(calls("frappe.client.rename_doc")).toEqual([
      { doctype: "Email Account", old_name: "Sales", new_name: "Sales Team" },
    ]);
  });

  it("keeps a failed load's error until a retry succeeds", async () => {
    const c = useEmailAccounts("ToDo");
    const failure = new Error("Not permitted");
    call.mockRejectedValueOnce(failure);

    await c.load();
    expect(c.error).toBe(failure);
    expect(c.loading).toBe(false);

    const retry = c.load();
    expect(c.error).toBe(failure);
    await retry;
    expect(c.error).toBeNull();
    expect(c.accounts).toHaveLength(3);
  });

  it("keeps the latest load when an earlier one finishes after it", async () => {
    const c = useEmailAccounts("ToDo");
    let finishFirst!: (docs: unknown[]) => void;
    call.mockImplementationOnce(
      () => new Promise((resolve) => (finishFirst = resolve)),
    );

    const first = c.load();
    await c.load();
    finishFirst([]);
    await first;

    expect(c.accounts).toHaveLength(3);
    expect(c.loading).toBe(false);
  });

  it("sets a default on the chosen account and clears it on the current one", async () => {
    const c = useEmailAccounts("ToDo");
    await c.load();

    await c.setDefault("outgoing", "Support");
    await c.setDefault("incoming", null);
    expect(calls("frappe.client.set_value")).toEqual([
      {
        doctype: "Email Account",
        name: "Support",
        fieldname: { default_outgoing: 1 },
      },
      {
        doctype: "Email Account",
        name: "Support",
        fieldname: { default_incoming: 0 },
      },
    ]);
  });

  function stubLocation() {
    const assign = vi.fn();
    vi.stubGlobal("location", {
      ...window.location,
      href: "https://example.com/helpdesk?tab=email&email_oauth=cancelled&email_oauth_mailbox=support%40example.com",
      assign,
    });
    return assign;
  }

  it("leaves for a new mailbox's sign-in and marks it started, landing back on the host minus the last result", async () => {
    const assign = stubLocation();
    const c = useEmailAccounts("HD Ticket");

    expect(await c.connect("Outlook.com")).toBe(true);

    expect(calls(CONNECT)).toEqual([
      {
        service: "Outlook.com",
        redirect_to: "/helpdesk?tab=email",
        target_doctype: "HD Ticket",
      },
    ]);
    expect(assign).toHaveBeenCalledWith("https://login.example.com/authorize");
    expect(takeSignInStarted()).toBe(true);
    vi.unstubAllGlobals();
  });

  it("stays on the page when Frappe Cloud can't sign the service in", async () => {
    const assign = stubLocation();
    const listed = call.getMockImplementation()!;
    call.mockImplementation(async (method: string, args: Record<string, any>) =>
      method === CONNECT ? null : listed(method, args),
    );
    const c = useEmailAccounts("HD Ticket");

    expect(await c.connect("Outlook.com")).toBe(false);
    expect(assign).not.toHaveBeenCalled();
    expect(takeSignInStarted()).toBe(false);
    vi.unstubAllGlobals();
  });

  it("starts sign-in again for a mailbox to reconnect", async () => {
    const assign = stubLocation();
    const c = useEmailAccounts("HD Ticket");

    await c.reconnect({ ...ACCOUNTS[0], authKind: "oauth" } as EmailAccount);

    expect(calls(CONNECT)).toEqual([
      {
        email_account: "Support",
        redirect_to: "/helpdesk?tab=email",
        target_doctype: "HD Ticket",
      },
    ]);
    expect(assign).toHaveBeenCalledWith("https://login.example.com/authorize");
    expect(takeSignInStarted()).toBe(false);
    vi.unstubAllGlobals();
  });

  it("signs a mailbox with its own OAuth app in again through that app, as its connected user", async () => {
    const assign = stubLocation();
    call.mockResolvedValue({ message: "https://login.example.com/own-app" });
    const c = useEmailAccounts("HD Ticket");

    await c.reconnect({
      ...ACCOUNTS[2],
      connected_user: "support@example.com",
      authKind: "oauth-custom",
    } as EmailAccount);

    expect(call.mock.calls).toEqual([
      [
        "frappe.handler.run_doc_method",
        {
          dt: "Connected App",
          dn: "own-app",
          method: "initiate_web_application_flow",
          args: {
            success_uri: "/helpdesk?tab=email",
            user: "support@example.com",
          },
        },
      ],
    ]);
    expect(assign).toHaveBeenCalledWith("https://login.example.com/own-app");
    vi.unstubAllGlobals();
  });
});
