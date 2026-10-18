import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { toast } from "frappe-ui";
import { createApp, nextTick } from "vue";
import type { App, VNode } from "vue";
import EmailAccounts from "../EmailAccounts.vue";

const { call, request } = vi.hoisted(() => ({
  call: vi.fn(),
  request: vi.fn(),
}));
vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  toast: { success: vi.fn(), error: vi.fn() },
  call: (...args: unknown[]) => call(...args),
  frappeRequest: (...args: unknown[]) => request(...args),
}));

const CONNECT =
  "frappe.integrations.frappe_providers.email_oauth.initiate_mailbox_connect";

let app: App;
let root: HTMLElement;

beforeEach(() => {
  call.mockReset().mockImplementation(async (method: string) => {
    if (method === "frappe.client.get_list")
      return [
        {
          name: "Sales",
          email_account_name: "Sales",
          email_id: "sales@example.com",
          service: "GMail",
          auth_method: "Basic",
          enable_incoming: 1,
          enable_outgoing: 1,
        },
      ];
    if (method === CONNECT) return "https://login.example.com/authorize";
    return null;
  });
  request.mockReset().mockResolvedValue([]);
  vi.mocked(toast.success).mockClear();
});

afterEach(() => {
  app?.unmount();
  root.remove();
  vi.unstubAllGlobals();
});

const settle = () => new Promise((resolve) => setTimeout(resolve));
const button = (name: string) =>
  [...root.querySelectorAll("button")].find((b) =>
    b.textContent?.trim().startsWith(name),
  )!;

async function mount(props: Record<string, unknown> = {}) {
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(EmailAccounts, { doctype: "HD Ticket", ...props });
  app.mount(root);
  await settle();
}

async function openEdited() {
  const onDirty = vi.fn();
  await mount({ "onUpdate:dirty": onDirty });
  (root.querySelector("li button") as HTMLButtonElement).click();
  await nextTick();
  const name = [...root.querySelectorAll("input")].find((i) =>
    i.labels?.[0]?.textContent?.includes("Account name"),
  )!;
  name.value = "Sales desk";
  name.dispatchEvent(new Event("input"));
  await nextTick();
  return onDirty;
}

async function openTiles(props: Record<string, unknown> = {}) {
  await mount(props);
  button("New").click();
  await nextTick();
  return [...root.querySelectorAll('[role="group"] button')].map((b) =>
    b.textContent?.trim(),
  );
}

it("reports unsaved edits, and clears them once the edit is saved", async () => {
  const onDirty = await openEdited();
  expect(onDirty).toHaveBeenLastCalledWith(true);

  root.querySelector("form")!.dispatchEvent(new Event("submit"));
  await settle();
  expect(onDirty).toHaveBeenLastCalledWith(false);
  expect(root.querySelector("h2")!.textContent).toBe("Email accounts");
});

it("compares later edits with what a half-failed save stored", async () => {
  const saved = {
    name: "Sales",
    email_account_name: "Sales",
    email_id: "sales@example.com",
    service: "GMail",
    auth_method: "Basic",
    enable_incoming: 1,
    enable_outgoing: 1,
  };
  call.mockImplementation(async (method: string, args) => {
    if (method === "frappe.client.get_list") return [{ ...saved }];
    if (method === "frappe.client.set_value")
      Object.assign(saved, args.fieldname);
    if (method === "frappe.client.rename_doc")
      throw new Error("Sales desk exists");
    return null;
  });
  await openEdited();
  const email = root.querySelector('input[type="email"]') as HTMLInputElement;
  const submit = async (value: string) => {
    email.value = value;
    email.dispatchEvent(new Event("input"));
    await nextTick();
    root.querySelector("form")!.dispatchEvent(new Event("submit"));
    await settle();
  };

  await submit("desk@example.com");
  await submit("sales@example.com");

  expect(
    call.mock.calls
      .filter(([method]) => method === "frappe.client.set_value")
      .map(([, args]) => args.fieldname.email_id),
  ).toEqual(["desk@example.com", "sales@example.com"]);
});

it("clears unsaved edits when the host unmounts the panel", async () => {
  const onDirty = await openEdited();
  app.unmount();
  expect(onDirty).toHaveBeenLastCalledWith(false);
  app = undefined!;
});

it("offers every provider by default, and only the host's `providers` when given", async () => {
  expect(await openTiles()).toEqual([
    "Gmail",
    "Outlook",
    "Frappe Mail",
    "Yahoo",
    "Yandex",
    "SendGrid",
    "SparkPost",
    "Custom email",
  ]);
  app.unmount();
  root.remove();

  expect(await openTiles({ providers: ["Outlook.com", ""] })).toEqual([
    "Outlook",
    "Custom email",
  ]);
});

it("signs in to Outlook in one click only when the site offers it", async () => {
  await openTiles();
  button("Outlook").click();
  await settle();
  expect(call.mock.calls.filter(([m]) => m === CONNECT)).toEqual([]);
  expect(root.querySelector("h2")!.textContent).toContain(
    "New Outlook account",
  );
  app.unmount();
  root.remove();

  const assign = vi.fn();
  vi.stubGlobal("location", {
    ...window.location,
    href: "https://example.com/helpdesk/tickets?status=Open",
    assign,
  });
  request.mockResolvedValue(["microsoft", "google"]);
  await openTiles();
  button("Outlook").click();
  await settle();
  expect(call.mock.calls.filter(([m]) => m === CONNECT)).toEqual([
    [
      CONNECT,
      {
        provider: "microsoft",
        redirect_to: "/helpdesk/tickets?status=Open",
        target_doctype: "HD Ticket",
        email_account: undefined,
      },
    ],
  ]);
  expect(assign).toHaveBeenCalledWith("https://login.example.com/authorize");
});

async function landWith(query: string) {
  window.history.replaceState(
    null,
    "",
    `/helpdesk/tickets?status=Open&${query}`,
  );
  const onCreated = vi.fn();
  await mount({ onCreated });
  return onCreated;
}

const toasted = () =>
  vi
    .mocked(toast.success)
    .mock.calls.map(([render]) => (render as () => VNode)().children);

it("reports a new one-click mailbox as created, then drops the result from the URL", async () => {
  const onCreated = await landWith(
    "email_oauth=connected&email_oauth_mailbox=sales%40example.com",
  );
  expect(onCreated).toHaveBeenCalledWith("GMail");
  expect(toasted()).toEqual(["Connected sales@example.com"]);
  expect(window.location.pathname + window.location.search).toBe(
    "/helpdesk/tickets?status=Open",
  );
});

it("reports a new one-click mailbox only once its account loads", async () => {
  const listed = call.getMockImplementation()!;
  call.mockImplementationOnce(async () => {
    throw new Error("Server down");
  });
  call.mockImplementation(listed);
  const onCreated = await landWith(
    "email_oauth=connected&email_oauth_mailbox=sales%40example.com",
  );
  expect(onCreated).not.toHaveBeenCalled();

  button("Retry").click();
  await settle();
  expect(onCreated).toHaveBeenCalledOnce();
  expect(onCreated).toHaveBeenCalledWith("GMail");
});

it("makes a new one-click mailbox the default when no account is", async () => {
  await landWith(
    "email_oauth=connected&email_oauth_mailbox=sales%40example.com",
  );
  await settle();
  expect(
    call.mock.calls
      .filter(([method]) => method === "frappe.client.set_value")
      .map(([, args]) => [args.name, args.fieldname, args.value]),
  ).toEqual([
    ["Sales", "default_incoming", 1],
    ["Sales", "default_outgoing", 1],
  ]);
});

it("does not report a reconnected mailbox as created", async () => {
  const onCreated = await landWith(
    "email_oauth=reconnected&email_oauth_mailbox=sales%40example.com",
  );
  expect(onCreated).not.toHaveBeenCalled();
  expect(toasted()).toEqual(["Reconnected sales@example.com"]);
});

it("shows a failed sign-in in the list", async () => {
  const onCreated = await landWith(
    "email_oauth=cancelled&email_oauth_mailbox=sales%40example.com",
  );
  expect(onCreated).not.toHaveBeenCalled();
  expect(root.textContent).toContain("Couldn't connect sales@example.com");
});
