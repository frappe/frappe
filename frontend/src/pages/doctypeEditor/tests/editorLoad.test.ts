// The editor page's loads: a slow one overtaken by a later route, and the first save of a new DocType.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, RouterView } from "vue-router";
import type { EditorState } from "../editorSource";
import { taskNote } from "./editorFixture";

const loads: {
  doctype: string;
  mode?: string;
  resolve: (state: EditorState) => void;
  reject: (error: Error) => void;
}[] = [];
const calls: string[] = [];

vi.mock("@framework/ui/api", () => ({
  listDocuments: async () => ({ data: [] }),
  runMethod: async (method: string) => {
    calls.push(method);
    if (method.endsWith(".create_doctype"))
      return { data: { saved: true, doctype: "Made Up" } };
    return { data: null };
  },
}));
vi.mock("@/router/routeFor", () => ({
  canRoute: () => true,
  routeFor: (doctype: string, name?: string) =>
    name ? `/doctype/${name}` : `/${doctype}`,
}));
const toast = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }));
vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  toast,
}));
vi.mock("@framework/ui/socket", () => ({ getSocketInstance: () => null }));
vi.mock("../editorSource", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../editorSource")>()),
  loadEditor: (doctype: string, mode?: string) =>
    new Promise<EditorState>((resolve, reject) =>
      loads.push({ doctype, mode, resolve, reject }),
    ),
}));
vi.mock("@/shell/PageFrame.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    pageGutter: "",
    default: defineComponent({
      setup:
        (_, { slots }) =>
        () =>
          h("div", [slots.header?.(), slots.default?.()]),
    }),
  };
});
vi.mock("../EditorHeader.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    default: defineComponent({
      emits: ["act"],
      props: ["doctype"],
      setup:
        (props, { emit }) =>
        () =>
          h(
            "button",
            { "data-save": "", onClick: () => emit("act", "editor.save") },
            props.doctype,
          ),
    }),
  };
});
vi.mock("../EditorCanvas.vue", () => ({ default: { render: () => null } }));
vi.mock("../EditorPanel.vue", () => ({ default: { render: () => null } }));
vi.mock("../RowDialogPreview.vue", () => ({ default: { render: () => null } }));
const asked = vi.hoisted(() => vi.fn());
vi.mock("../newDoctypeFlow", () => ({ askNewDoctype: asked }));

import DoctypeEditor from "../DoctypeEditor.vue";
import { lastModule } from "../lastModule";

let app: App | null = null;
const dom = document.createElement("div");

async function mount(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/doctype/:name", component: DoctypeEditor },
      { path: "/DocType", component: { render: () => null } },
    ],
  });
  app = createApp({ render: () => h(RouterView) });
  app
    .use(router)
    .provide("boot", {
      developer_mode: 1,
      session: { user: { name: "Administrator" } },
    })
    .mount(dom);
  await router.push(path);
  return router;
}
const settle = async () => {
  for (let i = 0; i < 6; i++) await Promise.resolve();
  await nextTick();
};

beforeEach(() => {
  loads.length = 0;
  calls.length = 0;
  asked.mockClear();
  toast.error.mockClear();
});
afterEach(() => {
  app?.unmount();
  app = null;
});

it("shows the DocType of the latest route when an earlier one loads last", async () => {
  const router = await mount("/doctype/Slow");
  await router.push("/doctype/Fast");
  await settle();
  const [slow, fast] = loads;
  fast.resolve(taskNote({ doctype: "Fast" }));
  await settle();
  slow.resolve(taskNote({ doctype: "Slow" }));
  await settle();
  expect(dom.querySelector("[data-save]")?.textContent).toBe("Fast");
});

it("hands a bare /doctype/new to the dialog over the list", async () => {
  await mount("/doctype/new");
  await settle();
  expect(asked).toHaveBeenCalledOnce();
  expect(asked.mock.calls[0].slice(1, 3)).toEqual([{}, null]);
});

it("hands a half-answered /doctype/new to the dialog with what it carries", async () => {
  await mount("/doctype/new?name=Made%20Up");
  await settle();
  expect(asked.mock.calls[0][1]).toEqual({ name: "Made Up" });
});

it("opens the DocType a first save made once, without a second load", async () => {
  const router = await mount(
    "/doctype/new?name=Made%20Up&module=Desk&custom=1&naming_rule=Random",
  );
  await settle();
  expect(asked).not.toHaveBeenCalled();
  dom.querySelector<HTMLElement>("[data-save]")!.click();
  await settle();
  expect(
    calls.filter((method) => method.endsWith(".create_doctype")),
  ).toHaveLength(1);
  await vi.waitFor(() =>
    expect(loads.map((load) => load.doctype)).toEqual(["Made Up"]),
  );
  loads[0].resolve(taskNote({ doctype: "Made Up" }));
  await vi.waitFor(() =>
    expect(router.currentRoute.value.path).toBe("/doctype/Made Up"),
  );
  await settle();
  expect(dom.querySelector("[data-save]")?.textContent).toBe("Made Up");
  expect(loads).toHaveLength(1);
  expect(lastModule("Administrator").recall()).toBe("Desk");
});

it("shows the error and goes to the list when the DocType to copy fails to load", async () => {
  const router = await mount("/doctype/new?__copy_of=Source");
  await settle();
  loads[0].reject(new Error("No such DocType"));
  await vi.waitFor(() => expect(toast.error).toHaveBeenCalled());
  await settle();
  expect(asked).not.toHaveBeenCalled();
  expect(dom.querySelector("[data-save]")).toBeNull();
  expect(router.currentRoute.value.path).toBe("/DocType");
});
