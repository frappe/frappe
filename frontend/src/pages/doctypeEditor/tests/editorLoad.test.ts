// The editor page's loads: a slow one overtaken by a later route, and the first save of a new DocType.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, RouterView } from "vue-router";
import type { EditorState } from "../editorSource";
import { taskNote } from "./editorFixture";

const loads: { doctype: string; mode?: string; resolve: (state: EditorState) => void }[] = [];
const calls: string[] = [];

vi.mock("@framework/ui/api", () => ({
	listDocuments: async () => ({ data: [] }),
	runMethod: async (method: string) => {
		calls.push(method);
		if (method.endsWith(".create_doctype")) return { data: { saved: true, doctype: "Made Up" } };
		return { data: null };
	},
}));
vi.mock("@/router/routeFor", () => ({
	canRoute: () => true,
	routeFor: (doctype: string, name?: string) => (name ? `/doctype/${name}` : `/${doctype}`),
}));
vi.mock("@framework/ui/socket", () => ({ getSocketInstance: () => null }));
vi.mock("../editorSource", async (importOriginal) => ({
	...(await importOriginal<typeof import("../editorSource")>()),
	loadEditor: (doctype: string, mode?: string) =>
		new Promise<EditorState>((resolve) => loads.push({ doctype, mode, resolve })),
}));
vi.mock("@/shell/PageFrame.vue", async () => {
	const { defineComponent, h } = await import("vue");
	return {
		pageGutter: "",
		default: defineComponent({ setup: (_, { slots }) => () => h("div", [slots.header?.(), slots.default?.()]) }),
	};
});
vi.mock("../EditorHeader.vue", async () => {
	const { defineComponent, h } = await import("vue");
	return {
		default: defineComponent({
			emits: ["act"],
			props: ["doctype"],
			setup: (props, { emit }) => () =>
				h("button", { "data-save": "", onClick: () => emit("act", "editor.save") }, props.doctype),
		}),
	};
});
vi.mock("../EditorCanvas.vue", () => ({ default: { render: () => null } }));
vi.mock("../EditorPanel.vue", () => ({ default: { render: () => null } }));
vi.mock("../RowDialogPreview.vue", () => ({ default: { render: () => null } }));
vi.mock("../NewDoctypeDialog.vue", async () => {
	const { defineComponent, h } = await import("vue");
	const answers = { name: "Made Up", module: "Desk", custom: true, naming_rule: "Random" };
	return {
		default: defineComponent({
			emits: ["create"],
			setup: (_, { emit }) => () => h("button", { "data-create": "", onClick: () => emit("create", answers) }),
		}),
	};
});

import DoctypeEditor from "../DoctypeEditor.vue";

let app: App | null = null;
const dom = document.createElement("div");

async function mount(path: string) {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/doctype/:name", component: DoctypeEditor }],
	});
	app = createApp({ render: () => h(RouterView) });
	app.use(router).provide("boot", { developer_mode: 1 }).mount(dom);
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

it("opens the DocType a first save made once, without a second load", async () => {
	const router = await mount("/doctype/new");
	await settle();
	dom.querySelector<HTMLElement>("[data-create]")!.click();
	await settle();
	dom.querySelector<HTMLElement>("[data-save]")!.click();
	await settle();
	expect(calls.filter((method) => method.endsWith(".create_doctype"))).toHaveLength(1);
	await vi.waitFor(() => expect(loads.map((load) => load.doctype)).toEqual(["Made Up"]));
	loads[0].resolve(taskNote({ doctype: "Made Up" }));
	await vi.waitFor(() => expect(router.currentRoute.value.path).toBe("/doctype/Made Up"));
	await settle();
	expect(dom.querySelector("[data-save]")?.textContent).toBe("Made Up");
	expect(loads).toHaveLength(1);
});
