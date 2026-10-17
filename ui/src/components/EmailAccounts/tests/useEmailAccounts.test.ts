import { beforeEach, describe, expect, it, vi } from "vitest";

const call = vi.fn();
const request = vi.fn();
vi.mock("frappe-ui", () => ({
  call: (...args: unknown[]) => call(...args),
  frappeRequest: (...args: unknown[]) => request(...args),
}));

const { useEmailAccounts } = await import("../useEmailAccounts");
const { emptyForm, services } = await import("../services");

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
    if (method === "frappe.client.rename_doc") return args.new_name;
    if (method === "frappe.client.insert")
      return { name: args.doc.email_account_name };
    if (method.endsWith("initiate_mailbox_connect"))
      return "https://login.example.com/authorize";
    return null;
  });
}

const calls = (method: string) =>
  call.mock.calls.filter(([m]) => m === method).map(([, a]) => a);

beforeEach(() => {
  call.mockReset();
  request.mockReset().mockResolvedValue(["microsoft"]);
  backend();
});

describe("useEmailAccounts", () => {
  it("loads accounts with how they sign in and what needs attention", async () => {
    const c = useEmailAccounts("HD Ticket");
    await c.load();

    expect(c.accounts.map((a) => [a.name, a.authKind, a.status])).toEqual([
      ["Support", "oauth", "needs-reconnect"],
      ["Sales", "password", "active"],
      ["Legacy", "oauth-custom", "active"],
    ]);
    expect(c.oneClickProviders).toEqual(["microsoft"]);
    expect(request).toHaveBeenCalledWith({
      url: "frappe.integrations.frappe_providers.email_oauth.get_one_click_providers",
      method: "GET",
    });
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
      "Sales",
      "Legacy",
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
      c.update(c.accounts[1], { enable_outgoing: 1 }, "Sales Team"),
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
      c.update(c.accounts[1], { enable_outgoing: 1 }, "Sales Team"),
    ).rejects.toBe(rejected);
    expect(calls("frappe.client.get_list")).toHaveLength(loads + 1);
  });

  it("saves the changes on the current name, then renames", async () => {
    const c = useEmailAccounts("ToDo");
    await c.load();
    await c.update(c.accounts[1], { enable_incoming: 1 }, "Sales Team");

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
    request.mockResolvedValueOnce([]);

    const first = c.load();
    await c.load();
    finishFirst([]);
    await first;

    expect(c.accounts).toHaveLength(3);
    expect(c.oneClickProviders).toEqual(["microsoft"]);
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
        fieldname: "default_outgoing",
        value: 1,
      },
      {
        doctype: "Email Account",
        name: "Support",
        fieldname: "default_incoming",
        value: 0,
      },
    ]);
  });

  it("starts sign-in for a mailbox to reconnect and lands back on the host, minus the last result", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", {
      ...window.location,
      href: "https://example.com/helpdesk?tab=email&email_oauth=cancelled&email_oauth_mailbox=support%40example.com",
      assign,
    });
    const c = useEmailAccounts("HD Ticket");

    await c.connect("microsoft", "Support");

    expect(
      calls(
        "frappe.integrations.frappe_providers.email_oauth.initiate_mailbox_connect",
      ),
    ).toEqual([
      {
        provider: "microsoft",
        redirect_to: "/helpdesk?tab=email",
        target_doctype: "HD Ticket",
        email_account: "Support",
      },
    ]);
    expect(assign).toHaveBeenCalledWith("https://login.example.com/authorize");
    vi.unstubAllGlobals();
  });
});
