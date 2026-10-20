import { toast } from "frappe-ui";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import type { App } from "vue";
import AccountEdit from "../AccountEdit.vue";

const { confirm } = vi.hoisted(() => ({ confirm: vi.fn() }));
vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  dialog: { confirm },
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: async () => [],
}));

const reconnect = vi.fn();
const pull = vi.fn();
const update = vi.fn();
const onBack = vi.fn();
const account = {
  name: "Support",
  email_account_name: "Support",
  email_id: "support@example.com",
  service: "Outlook.com",
  auth_method: "OAuth",
  connected_app: "relay-app",
  token_uri: "frappe-cloud-relay:microsoft",
  enable_incoming: 1,
  enable_outgoing: 1,
  authKind: "oauth",
  status: "needs-reconnect",
};

let app: App;
let root: HTMLElement;

function mount(overrides = {}) {
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(AccountEdit, {
    account: { ...account, ...overrides },
    controller: { reconnect, pull, update },
    onBack,
  });
  app.mount(root);
  const button = (label: string) =>
    [...root.querySelectorAll("button")].find((b) => b.textContent === label)!;
  const name = [...root.querySelectorAll("input")].find((i) =>
    i.labels?.[0]?.textContent?.includes("Account name"),
  )!;
  return {
    button,
    name,
    reconnect: button("Reconnect"),
    rename(value: string) {
      name.value = value;
      name.dispatchEvent(new Event("input"));
    },
  };
}

beforeEach(() => {
  confirm.mockReset();
  reconnect.mockReset();
  vi.stubGlobal("is_v2_site", true);
  pull.mockReset();
  update.mockReset();
  onBack.mockReset();
  vi.mocked(toast.error).mockReset();
});

afterEach(() => {
  app.unmount();
  root.remove();
  vi.unstubAllGlobals();
});

it("reconnects straight away when nothing is edited", () => {
  mount().reconnect.click();
  expect(confirm).not.toHaveBeenCalled();
  expect(reconnect).toHaveBeenCalledWith(expect.objectContaining({ name: "Support" }));
});

it("reports a failed reconnect in a toast and refocuses Reconnect", async () => {
  let fail!: (e: Error) => void;
  reconnect.mockReturnValue(new Promise<void>((_, reject) => (fail = reject)));
  const button = mount().reconnect;

  button.focus();
  button.click();
  // happy-dom lacks the focus fixup rule that blurs the button once `loading` disables it
  button.blur();
  await nextTick();
  expect((root.querySelector("h2 button") as HTMLButtonElement).disabled).toBe(true);
  fail(new Error("Sign in with Microsoft isn't available right now"));
  await new Promise((resolve) => setTimeout(resolve));
  expect(toast.error).toHaveBeenCalledWith(
    "Sign in with Microsoft isn't available right now",
  );
  expect(document.activeElement).toBe(button);
});

it("asks before reconnect drops edits, and Cancel refocuses the button", async () => {
  const { reconnect: button, rename } = mount();
  rename("Support desk");
  await nextTick();

  button.click();
  expect(reconnect).not.toHaveBeenCalled();
  expect(confirm.mock.calls[0][0]).toMatchObject({
    title: "Unsaved changes",
    message: "Are you sure you want to leave? Unsaved changes will be lost.",
  });
  await confirm.mock.calls[0][0].onCancel();
  expect(document.activeElement).toBe(button);

  reconnect.mockRejectedValue(new Error("Consent denied"));
  button.click();
  // stands in for the confirm's button, which keeps focus while the dialog animates out
  const confirmButton = document.createElement("button");
  root.after(confirmButton);
  confirmButton.focus();
  await confirm.mock.calls[1][0].onConfirm({ close: vi.fn() });
  expect(reconnect).toHaveBeenCalledWith(expect.objectContaining({ name: "Support" }));
  await new Promise((resolve) => setTimeout(resolve));
  expect(document.activeElement).toBe(button);
  confirmButton.remove();
});

it("locks Back, the fields and Reconnect while saving, then goes back under the new name", async () => {
  let save!: () => void;
  update.mockReturnValue(new Promise<void>((resolve) => (save = resolve)));
  const { name, reconnect, rename } = mount();
  rename("Support desk");
  await nextTick();

  root.querySelector("form")!.dispatchEvent(new Event("submit"));
  await nextTick();
  const back = root.querySelector("h2 button") as HTMLButtonElement;
  expect(back.disabled).toBe(true);
  expect(name.closest("fieldset")!.disabled).toBe(true);
  expect(reconnect.disabled).toBe(true);

  save();
  await new Promise((resolve) => setTimeout(resolve));
  expect(back.disabled).toBe(false);
  expect(name.closest("fieldset")!.disabled).toBe(false);
  expect(reconnect.disabled).toBe(false);
  expect(onBack).toHaveBeenCalledWith("Support desk");
});

it("reports a failed save in a toast, keeps the edits and refocuses the field", async () => {
  let fail!: (e: Error) => void;
  update.mockReturnValue(new Promise<void>((_, reject) => (fail = reject)));
  const { name, rename } = mount();
  rename("Support desk");
  await nextTick();

  name.focus();
  root.querySelector("form")!.dispatchEvent(new Event("submit"));
  await nextTick();
  // Chrome blurs a field when its fieldset is disabled; happy-dom doesn't.
  name.blur();
  fail(new Error("Couldn't save"));
  await new Promise((resolve) => setTimeout(resolve));
  expect(toast.error).toHaveBeenCalledWith("Couldn't save");
  expect(onBack).not.toHaveBeenCalled();
  expect(name.value).toBe("Support desk");
  expect(document.activeElement).toBe(name);
});

it("sends Desk a Frappe Cloud sign-in off Frappe Cloud V2", () => {
  vi.stubGlobal("is_v2_site", false);
  const { reconnect: button } = mount();
  expect(root.querySelector(".bg-surface-amber-1")!.textContent).toContain(
    "Reconnect it in Desk.",
  );
  expect(
    root.querySelector('[href="/desk/email-account/Support"]')?.textContent,
  ).toContain("Open in Desk");
  expect(button).toBeUndefined();
});

it("reconnects a mailbox with its own OAuth app, on or off Frappe Cloud V2", () => {
  vi.stubGlobal("is_v2_site", false);
  const { reconnect: button } = mount({
    authKind: "oauth-custom",
    token_uri: "https://login.microsoftonline.com/token",
  });
  const notice = root.querySelector(".bg-surface-amber-1")!.textContent;
  expect(notice).toContain("This mailbox needs to be reconnected");
  expect(notice).toContain("Sign in again to keep email flowing.");
  expect(root.querySelector('[href="/desk/email-account/Support"]')).toBeNull();

  button.click();
  expect(reconnect).toHaveBeenCalledWith(
    expect.objectContaining({ name: "Support", authKind: "oauth-custom" }),
  );
});

it("badges a manually set up account on Frappe Cloud V2, not a one-click one", () => {
  const badged = () => root.textContent!.includes("Manual setup");
  mount();
  expect(badged()).toBe(false);
  app.unmount();
  root.remove();

  mount({ authKind: "oauth-custom", token_uri: "https://login.microsoftonline.com/token" });
  expect(badged()).toBe(true);
  app.unmount();
  root.remove();

  vi.stubGlobal("is_v2_site", false);
  mount({ authKind: "oauth-custom", token_uri: "https://login.microsoftonline.com/token" });
  expect(badged()).toBe(false);
});

it("has nothing to save after retyping a saved port", async () => {
  const { button } = mount({
    service: "",
    auth_method: "Basic",
    authKind: "password",
    status: "active",
    email_server: "imap.example.com",
    incoming_port: 993,
    smtp_server: "smtp.example.com",
    smtp_port: 587,
  });
  const port = [...root.querySelectorAll("input")].find((i) =>
    i.labels?.[0]?.textContent?.includes("Incoming port"),
  )!;
  port.value = "993";
  port.dispatchEvent(new Event("input"));
  await nextTick();
  expect(button("Save").disabled).toBe(true);
});
