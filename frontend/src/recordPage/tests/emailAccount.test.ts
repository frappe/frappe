// Email Account's file script on the record page: what desk v1's form script did, through `page`.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

const server = vi.hoisted(() => ({
  hasToken: false,
  tokenUri: "https://oauth2.googleapis.com/token",
  calls: [] as { method: string; args: any; options?: any }[],
  confirm: true as true | null,
}));

vi.mock("frappe-ui", () => ({
  Alert: { name: "Alert", render: () => null },
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async (method: string, args: any, options?: any) => {
    server.calls.push({ method, args, options });
    return { data: methodReply(method) };
  }),
  runDocumentMethod: vi.fn(async (doctype: string, name: string, method: string, args: any, options?: any) => {
    server.calls.push({ method: `${doctype}:${name}:${method}`, args, options });
    return { data: method === "initiate_web_application_flow" ? null : undefined };
  }),
  getDocumentFields: vi.fn(async () => ({ data: { token_uri: server.tokenUri } })),
  getMeta: vi.fn(async () => ({ data: null, children: [] })),
}));

function methodReply(method: string) {
  if (method.endsWith(".has_token")) return server.hasToken;
  if (method.endsWith(".get_append_to")) return [["Issue"], ["Lead"]];
  if (method.endsWith(".get_max_file_size")) return 10 * 1024 * 1024;
  if (method === "run_doc_method") return { email_server: "imap.example.com", use_imap: 1 };
  return null;
}

import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { createRecordPage } from "../createRecordPage";
import { withRegisteringSource } from "@/pageEngine/context";
import { resetKeptValues } from "../keptValues";
import { registerRecordPage, resetRegistry } from "../registry";
import emailAccount from "../../../../frappe/email/doctype/email_account/frontend/record.js";

const FIELDS = [
  "service",
  "domain",
  "use_imap",
  "email_server",
  "smtp_server",
  "password",
  "api_secret",
  "append_to",
  "enable_incoming",
  "enable_auto_reply",
  "email_sync_option",
  "auth_method",
  "connected_app",
  "connected_user",
  "backend_app_flow",
  "authorize_api_access",
  "validate_frappe_mail_settings",
  "attachment_limit",
].map((fieldname) => ({ fieldname, fieldtype: "Data" }));
const TABLES = [
  { fieldname: "imap_folder", fieldtype: "Table", options: "IMAP Folder" },
  { fieldname: "reply_to_addresses", fieldtype: "Table", options: "Reply To Address" },
];

const controllers: ReturnType<typeof createRecordPage>[] = [];

async function openAccount(
  doc: Record<string, any>,
  {
    perms = { read: 1, write: 1 },
    isNew = false,
    dirty = false,
  }: { perms?: Record<string, number>; isNew?: boolean; dirty?: boolean } = {},
) {
  await withRegisteringSource("frappe", async () => registerRecordPage("Email Account", emailAccount));
  const controller = createRecordPage({
    app: "frappe",
    doctype: "Email Account",
    docname: "Support",
    doc: ref(doc),
    saved: ref({ ...doc }),
    meta: ref({ name: "Email Account", fields: [...FIELDS, ...TABLES] }),
    perms: () => perms,
    isNew: () => isNew,
    isDirty: () => dirty,
    activeTab: () => "details",
    activateTab: () => {},
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
  });
  controllers.push(controller);
  controller.header.provideBuiltins(() => [{ name: "save", label: "Save", run: () => {} }]);
  await controller.refresh();
  await vi.advanceTimersByTimeAsync(0);
  await controller.refresh();
  return { controller, page: controller.page };
}

const headerItem = (controller: ReturnType<typeof createRecordPage>, name: string) =>
  controller.header.visible().find((item) => item.name === name);

const bandNames = (controller: ReturnType<typeof createRecordPage>) =>
  controller.frame.visible().map((item) => item.name);

async function commit(controller: ReturnType<typeof createRecordPage>, fieldname: string, value: any) {
  controller.page.doc[fieldname] = value;
  await controller.commits.commit(fieldname, value);
  await vi.advanceTimersByTimeAsync(0);
}

function confirmWith(controller: ReturnType<typeof createRecordPage>) {
  return vi.spyOn(controller.page.dialog, "confirm").mockImplementation(async () => server.confirm);
}

beforeEach(() => {
  resetRegistry();
  resetDoctypeMeta();
  resetKeptValues();
  Object.assign(server, {
    hasToken: false,
    tokenUri: "https://oauth2.googleapis.com/token",
    calls: [],
    confirm: true,
  });
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.useFakeTimers();
});

afterEach(() => {
  for (const controller of controllers.splice(0)) controller.leave();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("Email Account's record page: service presets", () => {
  it("fills the IMAP server settings of the picked service", async () => {
    const { controller, page } = await openAccount({ use_imap: 0 });

    await commit(controller, "service", "GMail");

    expect(page.doc).toMatchObject({
      email_server: "imap.gmail.com",
      smtp_server: "smtp.gmail.com",
      smtp_port: 587,
      use_imap: 1,
    });
    expect(page.fields.get("password")?.description).toContain("knowledge.workspace.google.com");
  });

  it("fills the POP server of a service that leaves IMAP off", async () => {
    const { controller, page } = await openAccount({ use_imap: 0 });

    await commit(controller, "service", "Sendgrid");
    expect(page.doc.smtp_server).toBe("smtp.sendgrid.net");

    page.doc.service = "Yahoo Mail";
    await commit(controller, "use_imap", 0);
    expect(page.doc.email_server).toBe("pop.mail.yahoo.com");
    await commit(controller, "use_imap", 1);
    expect(page.doc.email_server).toBe("imap.mail.yahoo.com");
  });

  it("fills the server settings from an Email Domain", async () => {
    const { controller, page } = await openAccount({});

    await commit(controller, "domain", "example.com");

    const call = server.calls.find((one) => one.method === "run_doc_method");
    expect(call?.args).toMatchObject({
      method: "get_domain_values",
      document: { doctype: "Email Account", __islocal: 0 },
      kwargs: { domain: "example.com" },
    });
    expect(page.doc.email_server).toBe("imap.example.com");
  });
});

describe("Email Account's record page: a new account", () => {
  it("starts with an INBOX folder, the site's attachment limit and its service's presets", async () => {
    const { page } = await openAccount({ service: "Outlook.com", use_imap: 0 }, { perms: {}, isNew: true });

    expect(page.doc.imap_folder).toEqual([{ folder_name: "INBOX" }]);
    expect(page.doc.attachment_limit).toBe(10);
    expect(page.doc.smtp_server).toBe("smtp-mail.outlook.com");
  });

  it("turns auto reply off when the reader declines it on an incoming account", async () => {
    const { controller, page } = await openAccount({ enable_incoming: 1 }, { perms: {}, isNew: true });
    const confirm = confirmWith(controller);
    server.confirm = null;

    await commit(controller, "enable_auto_reply", 1);

    expect(confirm).toHaveBeenCalledOnce();
    expect(page.doc.enable_auto_reply).toBe(0);
  });
});

describe("Email Account's record page: confirmations", () => {
  it("goes back to UNSEEN when the reader declines syncing every email", async () => {
    const { controller, page } = await openAccount({ use_imap: 1 });
    confirmWith(controller);
    server.confirm = null;

    await commit(controller, "email_sync_option", "ALL");

    expect(page.doc.email_sync_option).toBe("UNSEEN");
  });

  it("offers to move the Reply-To rows to the new address before a save", async () => {
    const { controller, page } = await openAccount({
      email_id: "old@example.com",
      reply_to_addresses: [{ email: "Old@example.com" }, { email: "team@example.com" }],
    });
    const confirm = confirmWith(controller);
    page.doc.email_id = "new@example.com";

    await controller.fireEvent("beforeSave");

    expect(confirm).toHaveBeenCalledOnce();
    expect(page.doc.reply_to_addresses.map((row: any) => row.email)).toEqual([
      "new@example.com",
      "team@example.com",
    ]);
  });
});

describe("Email Account's record page: header acts and the OAuth band", () => {
  const oauth = {
    auth_method: "OAuth",
    connected_app: "Google",
    connected_user: "user@example.com",
  };

  it("asks for authorisation in a band, with the act that starts it", async () => {
    const { controller } = await openAccount(oauth);

    expect(bandNames(controller)).toContain("oauth_status");
    expect(headerItem(controller, "authorize_api_access")?.label).toBe("Authorize API Access");
    expect(controller.page.fields.get("authorize_api_access")?.hidden).toBe(true);

    await controller.page.run("header.authorize_api_access");
    expect(server.calls.at(-1)).toMatchObject({
      method: "Connected App:Google:initiate_web_application_flow",
      args: { user: "user@example.com" },
    });
  });

  it("shows no band once the account holds a token", async () => {
    server.hasToken = true;
    const { controller } = await openAccount(oauth);

    expect(bandNames(controller)).not.toContain("oauth_status");
    expect(headerItem(controller, "authorize_api_access")).toBeTruthy();
  });

  it("offers Reconnect for a signed-out relay mailbox", async () => {
    server.tokenUri = "frappe-cloud-relay:google";
    const { controller } = await openAccount({ ...oauth, connected_user: null });

    expect(headerItem(controller, "authorize_api_access")?.label).toBe("Reconnect");
    await controller.page.run("header.authorize_api_access");
    expect(server.calls.at(-1)?.method).toContain("initiate_mailbox_connect");
  });

  it("checks Frappe Mail settings on a saved, clean account", async () => {
    const { controller } = await openAccount({ service: "Frappe Mail", auth_method: "OAuth" });

    await controller.page.run("header.validate_frappe_mail_settings");

    expect(server.calls.at(-1)).toMatchObject({
      method: "Email Account:Support:validate_frappe_mail_settings",
      options: { nullable: true },
    });
  });

  it("pulls emails on a clean incoming account, and not on a dirty one", async () => {
    const { controller } = await openAccount({ enable_incoming: 1 });
    await controller.page.run("header.pull_emails");
    expect(server.calls.at(-1)).toMatchObject({
      args: { email_account: "Support" },
      options: { nullable: true },
    });

    const dirty = await openAccount({ enable_incoming: 1 }, { dirty: true });
    expect(headerItem(dirty.controller, "pull_emails")).toBeUndefined();
  });

  it("limits Append To to the doctypes that take emails", async () => {
    const { page } = await openAccount({});

    expect(page.fields.get("append_to")?.link_filters).toEqual({ name: ["in", ["Issue", "Lead"]] });
  });
});
