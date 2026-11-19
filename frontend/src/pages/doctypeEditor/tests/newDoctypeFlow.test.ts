import { beforeEach, expect, it, vi } from "vitest";

const open = vi.hoisted(() => vi.fn());
const toast = vi.hoisted(() => ({ error: vi.fn() }));
vi.mock("frappe-ui", () => ({ toast }));
vi.mock("@/shell/dialog", () => ({ shellDialog: () => ({ open }) }));
vi.mock("@/router/routeFor", () => ({
  routeFor: () => "/doctype",
  routeForNew: (doctype: string, values: Record<string, unknown>) => ({
    doctype,
    values,
  }),
}));
vi.mock("../NewDoctypeDialog.vue", () => ({
  default: { name: "NewDoctypeDialog" },
}));

import { createMemoryHistory, createRouter } from "vue-router";
import { COPY_OF } from "@/newRecordValues";
import { askNewDoctype } from "../newDoctypeFlow";
import { lastModule } from "../lastModule";

const router = { replace: vi.fn(), push: vi.fn() };
const ask = (initial = {}, copyOf: string | null = null) =>
  askNewDoctype(router as never, initial, copyOf, "Administrator");

beforeEach(() => {
  localStorage.clear();
  open.mockReset();
  router.replace.mockReset();
  router.push.mockReset();
  toast.error.mockReset();
});

it("opens the dialog over the DocType list", async () => {
  open.mockResolvedValue(null);
  await ask();
  expect(router.replace).toHaveBeenCalledWith("/doctype");
  expect(router.replace.mock.invocationCallOrder[0]).toBeLessThan(
    open.mock.invocationCallOrder[0],
  );
  expect(router.push).not.toHaveBeenCalled();
});

it("prefills the module last used, unless the answers carry one", async () => {
  lastModule("Administrator").remember("Core");
  open.mockResolvedValue(null);
  await ask();
  expect(open.mock.calls[0][1]).toEqual({
    initial: { module: "Core" },
    remembered: "Core",
  });
  await ask({ module: "Desk", name: "Route" });
  expect(open.mock.calls[1][1]).toEqual({
    initial: { module: "Desk", name: "Route" },
    remembered: "Core",
  });
});

it("prefills no module for a user who has made none", async () => {
  lastModule("Someone Else").remember("Core");
  open.mockResolvedValue(null);
  await ask();
  expect(open.mock.calls[0][1]).toEqual({
    initial: { module: "" },
    remembered: "",
  });
});

it("pushes /doctype/new with the answers, and the source of a duplicate", async () => {
  open.mockResolvedValue({
    name: "Route",
    module: "Desk",
    custom: false,
    naming_rule: "Random",
  });
  await ask({}, "Source");
  expect(router.push.mock.calls[0][0].doctype).toBe("DocType");
  expect(router.push.mock.calls[0][0].values).toMatchObject({
    name: "Route",
    module: "Desk",
    custom: 0,
    naming_rule: "Random",
  });
  expect(router.push.mock.calls[0][0].values[COPY_OF]).toBe("Source");
});

it("stays on the list when the dialog is dismissed", async () => {
  open.mockResolvedValue(null);
  await ask();
  expect(router.push).not.toHaveBeenCalled();
});

it("does not open the dialog when the list route was refused", async () => {
  const refusing = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/:rest(.*)", component: {} }],
  });
  refusing.beforeEach(() => false);
  await askNewDoctype(refusing, {}, null, "Administrator");
  expect(open).not.toHaveBeenCalled();
  expect(toast.error).not.toHaveBeenCalled();
});

it("shows the error when the dialog fails to load or open", async () => {
  open.mockRejectedValue(new Error("Chunk failed"));
  await ask();
  expect(toast.error).toHaveBeenCalledWith("Chunk failed");
  expect(router.push).not.toHaveBeenCalled();
});
