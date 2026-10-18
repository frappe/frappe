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

const connect = vi.fn();
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

function mount(overrides = {}, oneClickProviders = ["microsoft"]) {
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(AccountEdit, {
    account: { ...account, ...overrides },
    controller: {
      connect,
      pull,
      update,
      oneClickProviders,
    },
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
  connect.mockReset();
  pull.mockReset();
  update.mockReset();
  onBack.mockReset();
  vi.mocked(toast.error).mockReset();
});

afterEach(() => {
  app.unmount();
  root.remove();
});

it("reconnects straight away when nothing is edited", () => {
  mount().reconnect.click();
  expect(confirm).not.toHaveBeenCalled();
  expect(connect).toHaveBeenCalledWith("microsoft", "Support");
});

it("reports a failed reconnect in a toast and refocuses Reconnect", async () => {
  let fail!: (e: Error) => void;
  connect.mockReturnValue(new Promise<void>((_, reject) => (fail = reject)));
  const { reconnect } = mount();

  reconnect.focus();
  reconnect.click();
  // happy-dom lacks the focus fixup rule that blurs the button once `loading` disables it
  reconnect.blur();
  await nextTick();
  expect((root.querySelector("h2 button") as HTMLButtonElement).disabled).toBe(true);
  fail(new Error("Consent denied"));
  await new Promise((resolve) => setTimeout(resolve));
  expect(toast.error).toHaveBeenCalledWith("Consent denied");
  expect(document.activeElement).toBe(reconnect);
});

it("asks before reconnect drops edits, and Cancel refocuses the button", async () => {
  const { reconnect, rename } = mount();
  rename("Support desk");
  await nextTick();

  reconnect.click();
  expect(connect).not.toHaveBeenCalled();
  expect(confirm.mock.calls[0][0]).toMatchObject({
    title: "Unsaved changes",
    message: "Are you sure you want to leave? Unsaved changes will be lost.",
  });
  await confirm.mock.calls[0][0].onCancel();
  expect(document.activeElement).toBe(reconnect);

  connect.mockRejectedValue(new Error("Consent denied"));
  reconnect.click();
  // stands in for the confirm's button, which keeps focus while the dialog animates out
  const confirmButton = document.createElement("button");
  root.after(confirmButton);
  confirmButton.focus();
  await confirm.mock.calls[1][0].onConfirm({ close: vi.fn() });
  expect(connect).toHaveBeenCalledWith("microsoft", "Support");
  await new Promise((resolve) => setTimeout(resolve));
  expect(document.activeElement).toBe(reconnect);
  confirmButton.remove();
});

it("reconnects a signed-out account on its own OAuth app through Frappe Cloud", () => {
  const custom = { authKind: "oauth-custom", token_uri: "https://login.microsoftonline.com/token" };
  const { reconnect } = mount(custom);
  expect(root.querySelector(".bg-surface-amber-1")!.textContent).toContain(
    "This mailbox needs to be reconnected",
  );
  reconnect.click();
  expect(connect).toHaveBeenCalledWith("microsoft", "Support");
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

it("sends Desk an account it can't reconnect, naming its own OAuth app only when it has one", () => {
  const notice = () => root.querySelector(".bg-surface-amber-1")!.textContent;
  const openInDesk = () =>
    root.querySelector('[href="/desk/email-account/Support"]')?.textContent;
  mount({ service: "GMail" });
  expect(notice()).toContain("Reconnect it in Desk.");
  expect(notice()).not.toContain("own OAuth app");
  app.unmount();
  root.remove();

  mount({ authKind: "oauth-custom" }, []);
  expect(notice()).toContain("This mailbox needs to be authorized again");
  expect(notice()).toContain("It uses its own OAuth app. Authorize it again in Desk.");
  expect(openInDesk()).toContain("Open in Desk");
  expect(connect).not.toHaveBeenCalled();
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
