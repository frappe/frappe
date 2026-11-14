// The New DocType dialog keeps a prefilled module only while the site still has it.
import { afterEach, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";

const { listDocuments } = vi.hoisted(() => ({ listDocuments: vi.fn() }));
vi.mock("@framework/ui/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@framework/ui/api")>()),
  listDocuments,
}));

import NewDoctypeDialog from "../NewDoctypeDialog.vue";

let app: App | undefined;
afterEach(() => {
  app?.unmount();
  app = undefined;
  document.body.innerHTML = "";
});

async function continueDisabled(module: string) {
  listDocuments.mockResolvedValue({ data: [{ name: "Desk" }] });
  const host = document.body.appendChild(document.createElement("div"));
  app = createApp(NewDoctypeDialog, {
    initial: { name: "Route", module },
    close: vi.fn(),
  });
  app.mount(host);
  await vi.waitFor(() => expect(listDocuments).toHaveBeenCalled());
  await nextTick();
  await nextTick();
  const button = [...host.querySelectorAll("button")].find(
    (b) => b.textContent!.trim() === "Continue",
  );
  return button!.disabled;
}

it("clears a prefilled module the site does not have", async () => {
  expect(await continueDisabled("Gone")).toBe(true);
});

it("keeps a prefilled module the site has", async () => {
  expect(await continueDisabled("Desk")).toBe(false);
});

it("says when the module is the one used last", async () => {
  listDocuments.mockResolvedValue({ data: [{ name: "Desk" }, { name: "Core" }] });
  const host = document.body.appendChild(document.createElement("div"));
  app = createApp(NewDoctypeDialog, {
    initial: { module: "Desk" },
    remembered: "Desk",
    close: vi.fn(),
  });
  app.mount(host);
  await vi.waitFor(() => expect(listDocuments).toHaveBeenCalled());
  await nextTick();
  await nextTick();
  const hint = () => host.querySelector("[data-module-hint]")!.textContent!.replace(/\s+/g, " ").trim();
  expect(hint()).toBe("The last one you used. Where its files go.");
});
