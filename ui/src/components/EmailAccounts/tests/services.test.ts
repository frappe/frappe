import { afterEach, describe, expect, it, vi } from "vitest";
import {
  authKind,
  credentials,
  emptyForm,
  errorText,
  mailboxAddress,
  newAccount,
  oauthHelpLink,
  oauthMessage,
  reconnectable,
  serviceOf,
  services,
  validate,
} from "../services";
import type { AccountForm, EmailAccountDoc } from "../types";

const service = (name: string) => services.find((s) => s.service === name)!;
const form = (values: Partial<AccountForm> = {}): AccountForm => ({
  ...emptyForm(),
  email_account_name: "Support",
  email_id: "support@example.com",
  password: "secret",
  ...values,
});
const doc = (values: Partial<EmailAccountDoc> = {}) =>
  ({
    name: "Support",
    service: "GMail",
    auth_method: "Basic",
    enable_incoming: 1,
    enable_outgoing: 1,
    ...values,
  }) as EmailAccountDoc;

describe("newAccount", () => {
  it("fills in the provider's servers and routes the inbox to the host's doctype", () => {
    const account = newAccount(service("GMail"), form(), "HD Ticket");
    expect(account).toMatchObject({
      doctype: "Email Account",
      email_account_name: "Support",
      email_id: "support@example.com",
      service: "GMail",
      password: "secret",
      email_server: "imap.gmail.com",
      smtp_server: "smtp.gmail.com",
      use_imap: 1,
      enable_incoming: 1,
      imap_folder: [{ folder_name: "INBOX", append_to: "HD Ticket" }],
    });
  });

  it("never turns on incoming mail for a send-only provider", () => {
    const account = newAccount(
      service("Sendgrid"),
      form({ enable_incoming: true }),
      "ToDo",
    );
    expect(account).toMatchObject({
      enable_incoming: 0,
      use_imap: 0,
      imap_folder: [],
    });
  });

  it("gives Frappe Mail its API key and append_to, and no password", () => {
    const account = newAccount(
      service("Frappe Mail"),
      form({
        frappe_mail_site: "https://mail.example.com",
        api_key: "k",
        api_secret: "s",
      }),
      "ToDo",
    );
    expect(account).toMatchObject({
      api_key: "k",
      api_secret: "s",
      append_to: "ToDo",
      use_imap: 0,
    });
    expect(account).not.toHaveProperty("password");
  });

  it("stores a custom account's servers as Email Account values", () => {
    const account = newAccount(
      service(""),
      form({
        email_server: "imap.example.com",
        incoming_port: "993",
        use_ssl: true,
      }),
      "ToDo",
    );
    expect(account).toMatchObject({
      service: "",
      email_server: "imap.example.com",
      use_ssl: 1,
    });
    expect(account).not.toHaveProperty("append_to");
  });

  it("routes a domain account's mail to the host's doctype even if the domain uses POP", () => {
    const account = newAccount(
      service(""),
      form({ domain: "example.com" }),
      "ToDo",
    );
    expect(account).toMatchObject({
      domain: "example.com",
      append_to: "ToDo",
      imap_folder: [{ folder_name: "INBOX", append_to: "ToDo" }],
    });
  });
});

describe("emptyForm", () => {
  it("starts a new account on the usual ports and encryption, and keeps an existing one's", () => {
    expect(emptyForm()).toMatchObject({
      incoming_port: "993",
      smtp_port: "587",
      use_ssl: true,
      use_tls: true,
    });
    expect(
      emptyForm(
        doc({ incoming_port: 143, smtp_port: 25, use_ssl: 0, use_tls: 0 }),
      ),
    ).toMatchObject({
      incoming_port: "143",
      smtp_port: "25",
      use_ssl: false,
      use_tls: false,
    });
  });
});

describe("credentials", () => {
  it("leaves out a secret left blank, so editing keeps the saved one", () => {
    expect(
      credentials(service("GMail"), form({ password: "" })),
    ).not.toHaveProperty("password");
    expect(credentials(service("Frappe Mail"), form())).not.toHaveProperty(
      "api_secret",
    );
  });
});

describe("validate", () => {
  it("names the first missing field", () => {
    expect(
      validate(service("GMail"), form({ email_account_name: " " })),
    ).toEqual({
      field: "email_account_name",
      message: "Account name is required",
    });
    expect(validate(service("GMail"), form({ email_id: "nope" }))).toEqual({
      field: "email_id",
      message: "Enter a valid email address",
    });
    expect(validate(service("GMail"), form({ password: "" }))).toEqual({
      field: "password",
      message: "Password is required",
    });
    expect(
      validate(
        service("Frappe Mail"),
        form({ frappe_mail_site: "s", api_key: "k" }),
      ),
    ).toEqual({ field: "api_secret", message: "API secret is required" });
    expect(validate(service(""), form())).toEqual({
      field: "domain",
      message: "Pick an email domain or enter the server settings",
    });
    const servers = {
      email_server: "imap.example.com",
      smtp_server: "smtp.example.com",
    };
    expect(
      validate(service(""), form({ ...servers, email_server: "" })),
    ).toEqual({
      field: "email_server",
      message: "Incoming server is required",
    });
    expect(
      validate(service(""), form({ ...servers, smtp_server: "" })),
    ).toEqual({
      field: "smtp_server",
      message: "Outgoing server is required",
    });
    expect(
      validate(
        service(""),
        form({ ...servers, incoming_port: "", smtp_port: "" }),
      ),
    ).toBeUndefined();
  });

  it("asks a custom account only for the servers it uses", () => {
    expect(
      validate(
        service(""),
        form({ smtp_server: "smtp.example.com", enable_incoming: false }),
      ),
    ).toBeUndefined();
    expect(
      validate(
        service(""),
        form({ email_server: "imap.example.com", enable_outgoing: false }),
      ),
    ).toBeUndefined();
  });

  it("checks only the name and address of an OAuth account", () => {
    expect(
      validate(service("Frappe Mail"), form({ api_key: "" }), true, true),
    ).toBeUndefined();
    expect(
      validate(service(""), form({ email_account_name: " " }), true, true),
    ).toEqual({
      field: "email_account_name",
      message: "Account name is required",
    });
  });

  it("lets an edit keep its saved password", () => {
    expect(
      validate(service("GMail"), form({ password: "" }), true),
    ).toBeUndefined();
    expect(
      validate(
        service(""),
        form({ domain: "example.com", password: "" }),
        true,
      ),
    ).toBeUndefined();
  });
});

describe("account state", () => {
  it("tells a Frappe Cloud sign-in from an account's own OAuth app", () => {
    const oauth = (token_uri: string) =>
      doc({ auth_method: "OAuth", connected_app: "app", token_uri });
    expect(authKind(oauth("frappe-cloud-relay:microsoft"))).toBe("oauth");
    expect(authKind(oauth("https://login.example.com/token"))).toBe(
      "oauth-custom",
    );
    expect(authKind(doc())).toBe("password");
    expect(authKind(doc({ service: "Frappe Mail" }))).toBe("frappe-mail");
  });

  it("finds an account's provider, blank service being custom", () => {
    expect(serviceOf(doc({ service: "" })).kind).toBe("custom");
    expect(serviceOf(doc({ service: "Outlook.com" })).label).toBe("Outlook");
  });
});

describe("reconnectable", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reconnects a Frappe Cloud sign-in only on a Frappe Cloud V2 site, an own OAuth app anywhere", () => {
    expect(reconnectable({ authKind: "oauth" })).toBe(false);
    expect(reconnectable({ authKind: "oauth-custom" })).toBe(true);

    vi.stubGlobal("is_v2_site", true);
    expect(reconnectable({ authKind: "oauth" })).toBe(true);
    expect(reconnectable({ authKind: "oauth-custom" })).toBe(true);
    expect(reconnectable({ authKind: "password" })).toBe(false);
  });

  it("reads the V2 flag from Desk's boot when the host page has no global for it", () => {
    vi.stubGlobal("frappe", { boot: { is_v2_site: true } });
    expect(reconnectable({ authKind: "oauth" })).toBe(true);
  });
});

describe("errorText", () => {
  it("shows Frappe's server messages, else the error's own message", () => {
    expect(
      errorText(
        Object.assign(new Error("ValidationError"), {
          messages: ["Not permitted", "Ask your admin"],
        }),
      ),
    ).toBe("Not permitted Ask your admin");
    expect(
      errorText(Object.assign(new Error("Network error"), { messages: [] })),
    ).toBe("Network error");
    expect(errorText(undefined)).toBe("");
  });
});

describe("mailboxAddress", () => {
  it("keeps only an email address from the sign-in URL", () => {
    expect(mailboxAddress("sandeep@example.com")).toBe("sandeep@example.com");
    expect(mailboxAddress("<a href=x>y</a>")).toBeNull();
    expect(mailboxAddress("Click here sandeep@example.com")).toBeNull();
    expect(mailboxAddress(`${"a".repeat(243)}@example.com`)).toBeNull();
    expect(mailboxAddress(null)).toBeNull();
  });
});

describe("oauthMessage", () => {
  it("uses the provider's own words when it has them, else the general ones", () => {
    expect(oauthMessage("admin_approval", "microsoft")).toBe(
      "Your Microsoft 365 admin must approve Frappe first.",
    );
    expect(oauthMessage("admin_approval", "google")).toContain(
      "Google Workspace admin has blocked Frappe",
    );
    expect(oauthMessage("imap_disabled", "yandex")).toContain(
      "Yandex Mail settings",
    );
    expect(oauthMessage("admin_approval", "yahoo")).toBe(
      "Your admin must approve Frappe first.",
    );
    expect(oauthMessage("missing_permission", "google")).toContain(
      "allow access to your mail",
    );
    expect(oauthMessage("admin_approval")).toBe(
      "Your admin must approve Frappe first.",
    );
    expect(oauthMessage("cancelled", "microsoft")).toBe("Sign-in was cancelled.");
    expect(oauthMessage("<b>x</b>", "microsoft")).toBe(
      "Couldn't connect. Please try again.",
    );
  });

  it("links to a help page only for the provider that has one", () => {
    expect(oauthHelpLink("smtp_disabled", "microsoft")).toContain(
      "learn.microsoft.com",
    );
    expect(oauthHelpLink("smtp_disabled", "google")).toBeUndefined();
    expect(oauthHelpLink("imap_disabled", "google")).toContain("mail.google.com");
    expect(oauthHelpLink("imap_disabled", "yandex")).toContain("mail.yandex.com");
    expect(oauthHelpLink("smtp_disabled")).toBeUndefined();
    expect(oauthHelpLink("cancelled", "microsoft")).toBeUndefined();
  });
});
