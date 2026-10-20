import { toast } from "frappe-ui";
import { afterEach, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import type { App } from "vue";
import AccountAdd from "../AccountAdd.vue";

vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  toast: { success: vi.fn(), error: vi.fn() },
}));

let app: App;
let root: HTMLElement;

afterEach(() => {
  app.unmount();
  root.remove();
  vi.unstubAllGlobals();
});

const button = (name: string) =>
  [...root.querySelectorAll("button")].find((b) =>
    b.textContent?.trim().startsWith(name),
  )!;

function fill(label: string, value: string) {
  const input = [...root.querySelectorAll("input")].find((i) =>
    i.labels?.[0]?.textContent?.includes(label),
  )!;
  input.value = value;
  input.dispatchEvent(new Event("input"));
}

it("Back is disabled while a create is in flight, and `created` is emitted when it resolves", async () => {
  let succeed!: () => void;
  const created = vi.fn();
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(AccountAdd, {
    controller: {
      create: () => new Promise<void>((resolve) => (succeed = resolve)),
    },
    onCreated: created,
  });
  app.mount(root);

  button("Gmail").click();
  await nextTick();
  fill("Account name", "Support");
  fill("Email address", "support@example.com");
  fill("Password", "secret");
  root.querySelector("form")!.dispatchEvent(new Event("submit"));
  await nextTick();
  expect(button("Back:").disabled).toBe(true);
  expect(root.querySelector("fieldset")!.disabled).toBe(true);

  succeed();
  await new Promise((resolve) => setTimeout(resolve));
  expect(created).toHaveBeenCalledWith("GMail");
  expect(button("Back:").disabled).toBe(false);
  expect(root.querySelector("fieldset")!.disabled).toBe(false);
});

function mountOneClick(
  connect: (service: string) => Promise<boolean> = vi.fn(),
) {
  vi.stubGlobal("one_click_email_services", { "Outlook.com": "Outlook" });
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(AccountAdd, { controller: { connect } });
  app.mount(root);
}

const title = () => root.querySelector("h2")!.textContent;
const alert = () => root.querySelector('[role="alert"]');

it("signs in straight from a one-click tile and locks Back meanwhile, opening the form with a note when Frappe Cloud can't sign in", async () => {
  let answer!: (signedIn: boolean) => void;
  const connect = vi.fn(
    () => new Promise<boolean>((resolve) => (answer = resolve)),
  );
  mountOneClick(connect);

  button("Outlook").click();
  await nextTick();
  expect(connect).toHaveBeenCalledWith("Outlook.com");
  expect(button("Outlook").disabled).toBe(true);
  expect(button("Gmail").disabled).toBe(true);
  expect(button("Back:").disabled).toBe(true);
  expect(button("Sign in with")).toBeUndefined();

  answer(false);
  await new Promise((resolve) => setTimeout(resolve));
  expect(title()).toContain("New Outlook account");
  expect(root.querySelector("form")).not.toBeNull();
  expect(root.querySelector('[role="status"]')?.textContent).toContain(
    "Outlook sign-in isn't available right now",
  );
  expect(button("Back:").disabled).toBe(false);

  button("Back:").click();
  await nextTick();
  button("Gmail").click();
  await nextTick();
  expect(root.querySelector('[role="status"]')).toBeNull();
});

it("shows a failed sign-in's error, refocuses its tile, and clears it on the next pick", async () => {
  let fail!: (e: Error) => void;
  mountOneClick(() => new Promise<boolean>((_, reject) => (fail = reject)));

  button("Outlook").focus();
  button("Outlook").click();
  // happy-dom lacks the focus fixup rule that blurs the tile once `loading` disables it
  button("Outlook").blur();
  fail(new Error("Consent denied"));
  await new Promise((resolve) => setTimeout(resolve));
  expect(alert()?.textContent).toContain("Consent denied");
  expect(document.activeElement).toBe(button("Outlook"));
  expect(root.querySelector("form")).toBeNull();

  button("Gmail").click();
  await nextTick();
  expect(alert()).toBeNull();
});

it("opens the form directly for a service without one-click sign-in, and for every service off Frappe Cloud V2", async () => {
  mountOneClick();
  button("Gmail").click();
  await nextTick();
  expect(root.querySelector("form")).not.toBeNull();
  app.unmount();
  root.remove();

  vi.unstubAllGlobals();
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(AccountAdd, { controller: {} });
  app.mount(root);
  button("Outlook").click();
  await nextTick();
  expect(root.querySelector("form")).not.toBeNull();
});

function mountCreate(create: () => Promise<void>, onCreated?: () => void) {
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(AccountAdd, {
    controller: { create },
    onCreated,
  });
  app.mount(root);
}

async function submitGmail() {
  button("Gmail").click();
  await nextTick();
  fill("Account name", "Support");
  fill("Email address", "support@example.com");
  fill("Password", "secret");
  const field = root.querySelector("input")!;
  field.focus();
  root.querySelector("form")!.dispatchEvent(new Event("submit"));
  await nextTick();
  return field;
}

it("reports a failed create in a toast, keeps the form and refocuses the field", async () => {
  let fail!: (e: Error) => void;
  const created = vi.fn();
  mountCreate(() => new Promise<void>((_, reject) => (fail = reject)), created);
  const field = await submitGmail();
  // Chrome blurs a field when its fieldset is disabled; happy-dom doesn't.
  field.blur();
  fail(new Error("Couldn't create"));
  await new Promise((resolve) => setTimeout(resolve));
  expect(toast.error).toHaveBeenCalledWith("Couldn't create");
  expect(root.querySelector('[role="alert"]')).toBeNull();
  expect(created).not.toHaveBeenCalled();
  expect(field.value).toBe("Support");
  expect(document.activeElement).toBe(field);
});
