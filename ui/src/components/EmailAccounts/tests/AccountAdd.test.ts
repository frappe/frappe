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
      oneClickProviders: [],
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

it("Back is locked during a one-click connect, and a failure refocuses its tile and shows its error until the next pick", async () => {
  let fail!: (e: Error) => void;
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(AccountAdd, {
    controller: {
      connect: () => new Promise<void>((_, reject) => (fail = reject)),
      oneClickProviders: ["microsoft"],
    },
  });
  app.mount(root);
  const alert = () => root.querySelector('[role="alert"]');

  button("Outlook").focus();
  button("Outlook").click();
  // happy-dom lacks the focus fixup rule that blurs the tile once `loading` disables it
  button("Outlook").blur();
  await nextTick();
  expect(button("Outlook").disabled).toBe(true);
  expect(button("Back:").disabled).toBe(true);
  fail(new Error("Consent denied"));
  await new Promise((resolve) => setTimeout(resolve));
  expect(alert()?.textContent).toContain("Consent denied");
  expect(document.activeElement).toBe(button("Outlook"));

  button("Outlook").click();
  await nextTick();
  expect(alert()).toBeNull();

  fail(new Error("Consent denied"));
  await new Promise((resolve) => setTimeout(resolve));
  expect(alert()?.textContent).toContain("Consent denied");
  button("Gmail").click();
  await nextTick();
  button("Back:").click();
  await nextTick();
  expect(alert()).toBeNull();
});

it("a failed one-click connect leaves focus where the user moved it", async () => {
  let fail!: (e: Error) => void;
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(AccountAdd, {
    controller: {
      connect: () => new Promise<void>((_, reject) => (fail = reject)),
      oneClickProviders: ["microsoft"],
    },
  });
  app.mount(root);
  const outside = document.createElement("button");
  root.after(outside);

  button("Outlook").focus();
  button("Outlook").click();
  await nextTick();
  outside.focus();
  fail(new Error("Consent denied"));
  await new Promise((resolve) => setTimeout(resolve));
  expect(document.activeElement).toBe(outside);
  outside.remove();
});

function mountCreate(create: () => Promise<void>, onCreated?: () => void) {
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(AccountAdd, {
    controller: { create, oneClickProviders: [] },
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

it("a failed create leaves focus where the user moved it", async () => {
  let fail!: (e: Error) => void;
  mountCreate(() => new Promise<void>((_, reject) => (fail = reject)));
  const outside = document.createElement("button");
  root.after(outside);
  await submitGmail();
  outside.focus();
  fail(new Error("Couldn't create"));
  await new Promise((resolve) => setTimeout(resolve));
  expect(document.activeElement).toBe(outside);
  outside.remove();
});
