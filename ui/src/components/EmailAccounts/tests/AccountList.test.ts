import { toast } from "frappe-ui";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, reactive } from "vue";
import type { App } from "vue";
import AccountList from "../AccountList.vue";

vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  toast: { success: vi.fn(), error: vi.fn() },
}));
const oneClick = vi.hoisted(() => ({ services: {} as Record<string, string> }));
vi.mock("../useEmailAccounts", () => ({
  useOneClick: () => ({ data: oneClick.services }),
}));

let app: App;
let root: HTMLElement;
let setDefault: ReturnType<typeof vi.fn>;

const account = (name: string, default_outgoing: 0 | 1) => ({
  name,
  email_account_name: name,
  email_id: `${name.toLowerCase()}@example.com`,
  service: "GMail",
  auth_method: "Basic",
  authKind: "password",
  status: "active",
  enable_incoming: 0,
  enable_outgoing: 1,
  default_incoming: 0,
  default_outgoing,
});

function mount(controller = {}, props = {}) {
  root = document.createElement("div");
  document.body.append(root);
  app = createApp(AccountList, {
    controller: reactive({
      accounts: [account("Sales", 1), account("Support", 0)],
      loading: false,
      error: null,
      setDefault,
      ...controller,
    }),
    ...props,
  });
  app.mount(root);
}

beforeEach(() => {
  vi.clearAllMocks();
  setDefault = vi.fn().mockResolvedValue(undefined);
  mount();
});

afterEach(() => {
  app.unmount();
  root.remove();
  oneClick.services = {};
});

it("offers reconnect for an own OAuth app anywhere, and for a Frappe Cloud sign-in while its service signs in in one click", () => {
  const signedOut = (name: string, authKind: string) => ({
    ...account(name, 0),
    auth_method: "OAuth",
    authKind,
    status: "needs-reconnect",
  });
  const actions = () =>
    [...root.querySelectorAll("li")].map((li) =>
      li.textContent?.includes("Open in Desk") ? "desk" : li.textContent?.includes("Reconnect") ? "reconnect" : null,
    );
  const accounts = [signedOut("Support", "oauth"), signedOut("Legacy", "oauth-custom")];

  remount({ accounts });
  expect(actions()).toEqual(["desk", "reconnect"]);

  oneClick.services = { GMail: "Gmail" };
  remount({ accounts });
  expect(actions()).toEqual(["reconnect", "reconnect"]);
});

it("turns a direction on from its card's toggle, holding the whole card until it saves", async () => {
  let saved!: () => void;
  const update = vi.fn(() => new Promise<void>((resolve) => (saved = resolve)));
  remount({ update });
  const card = () => root.querySelector("li")!;
  const locked = () =>
    [...card().querySelectorAll<HTMLButtonElement>('[role="switch"], [data-open]')].map((b) => b.disabled);
  (card().querySelector('[role="switch"]') as HTMLButtonElement).click();
  await new Promise((resolve) => setTimeout(resolve));
  expect(update).toHaveBeenCalledWith(expect.objectContaining({ name: "Sales" }), { enable_incoming: 1 });
  expect([card().getAttribute("aria-busy"), ...locked()]).toEqual(["true", true, true, true]);
  // the switch shows what was picked while it saves
  expect(card().querySelector('[role="switch"]')!.getAttribute("aria-checked")).toBe("true");

  saved();
  await new Promise((resolve) => setTimeout(resolve));
  expect([card().getAttribute("aria-busy"), ...locked()]).toEqual(["false", false, false, false]);
});

const button = (name: string) =>
  [...root.querySelectorAll("button")].find(
    (b) => b.textContent?.trim() === name || b.getAttribute("aria-label") === name,
  )!;

function remount(controller = {}, props = {}) {
  app.unmount();
  root.remove();
  mount(controller, props);
}

async function pickDefaultOutgoing(option: string) {
  const label = [...root.querySelectorAll("label")].find(
    (l) => l.textContent?.trim() === "Default outgoing",
  )!;
  const press = (el: Element) =>
    el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  press(document.getElementById(label.htmlFor)!);
  await new Promise((resolve) => setTimeout(resolve));
  press([...document.querySelectorAll('[role="option"]')].find((o) => o.textContent?.trim() === option)!);
  await new Promise((resolve) => setTimeout(resolve));
}

it("ignores a pick of the saved default after a failed change", async () => {
  setDefault.mockRejectedValueOnce(new Error("nope"));
  await pickDefaultOutgoing("Support");
  await pickDefaultOutgoing("Sales");
  expect(setDefault).toHaveBeenCalledTimes(1);
  expect(toast.success).not.toHaveBeenCalled();
});

it("makes another account the default, and says so", async () => {
  await pickDefaultOutgoing("Support");
  expect(setDefault).toHaveBeenCalledWith("outgoing", "Support");
  expect(toast.success).toHaveBeenCalledWith("Default outgoing account updated");
});

it("clears the default when None is picked, and says so", async () => {
  await pickDefaultOutgoing("None");
  expect(setDefault).toHaveBeenCalledWith("outgoing", null);
  expect(toast.success).toHaveBeenCalledWith("Default outgoing account cleared");
});

it("retries a failed load, refocusing Retry while it still fails and New once it loads", async () => {
  let fail = true;
  const load = vi.fn(async function (this: { error: unknown }) {
    if (!fail) this.error = null;
  });
  remount({ accounts: [], error: new Error("Network error"), load });
  const banner = root.querySelector('[role="alert"]')!;
  expect(banner.textContent).toContain("Couldn't load email accounts");
  expect(banner.textContent).toContain("Network error");

  button("Retry").click();
  await new Promise((resolve) => setTimeout(resolve));
  expect(load).toHaveBeenCalledOnce();
  expect(document.activeElement).toBe(button("Retry"));

  fail = false;
  (document.activeElement as HTMLElement).blur();
  button("Retry").click();
  await new Promise((resolve) => setTimeout(resolve));
  expect(root.textContent).not.toContain("Couldn't load email accounts");
  expect(document.activeElement).toBe(button("New"));
});

it("shows ten cards at a time, opening on the page with the card to focus", async () => {
  const accounts = Array.from({ length: 23 }, (_, i) => account(`Box${i}`, 0));
  const cards = () => root.querySelectorAll("[data-open]").length;
  const more = () => [...root.querySelectorAll("button")].find((b) => b.textContent?.includes("Show more"));

  remount({ accounts });
  expect(cards()).toBe(10);
  more()!.click();
  await new Promise((r) => setTimeout(r));
  expect(cards()).toBe(20);
  expect(document.activeElement?.textContent).toContain("Box10");
  more()!.click();
  await new Promise((r) => setTimeout(r));
  expect([cards(), more()]).toEqual([23, undefined]);

  remount({ accounts }, { focus: "Box14" });
  expect(cards()).toBe(20);
  expect(document.activeElement?.textContent).toContain("Box14");
});
