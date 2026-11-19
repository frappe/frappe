// A child editor that is loading names itself, and one that failed to load gives the address back to the parent.
import { afterEach, expect, it, vi } from "vitest";
import { createApp, defineComponent, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import type { EditorState } from "../editorSource";
import { useChildTables } from "../useChildTables";
import { ForkWarning } from "../forkWarning";
import { mountEditor, taskNote } from "./editorFixture";

const loads = new Map<string, { resolve: (state: EditorState) => void; reject: (error: Error) => void }>();

vi.mock("../editorSource", async (importOriginal) => ({
	...(await importOriginal<typeof import("../editorSource")>()),
	loadEditor: (doctype: string) =>
		new Promise<EditorState>((resolve, reject) => loads.set(doctype, { resolve, reject })),
}));

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { error: vi.fn() },
}));

const parent = () =>
	taskNote({
		definition: {
			...taskNote().definition,
			fields: [{ fieldname: "lines", label: "Lines", fieldtype: "Table", options: "Line" }],
		},
	} as Partial<EditorState>);

let app: ReturnType<typeof createApp> | null = null;
let editor: ReturnType<typeof mountEditor> | null = null;

afterEach(() => {
	app?.unmount();
	editor?.stop();
	app = editor = null;
	loads.clear();
	document.body.innerHTML = "";
});

async function mountPage(path: string) {
	editor = mountEditor(parent());
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:rest(.*)*", component: { render: () => null } }],
	});
	await router.push(path);
	let child!: ReturnType<typeof useChildTables>;
	app = createApp(
		defineComponent({
			setup() {
				child = useChildTables(editor!.edits, () => editor!.canvas, new ForkWarning(async () => true));
				return () => null;
			},
		}),
	);
	app.use(router).mount(document.createElement("div"));
	await nextTick();
	return { router, child };
}

it("names the child while its editor loads, then clears", async () => {
	const { child } = await mountPage("/doctype/task-note?table=lines");
	expect(child.tables.loading.value).toBe("Line");
	loads.get("Line")!.resolve(taskNote({ doctype: "Line", definition: { name: "Line", fields: [] } } as Partial<EditorState>));
	await vi.waitFor(() => expect(child.tables.open.value?.state.doctype).toBe("Line"));
	expect(child.tables.loading.value).toBeNull();
});

it("leaves the address when the child fails to load, so the same Edit opens it again", async () => {
	const { router, child } = await mountPage("/doctype/task-note?table=lines&mode=design");
	loads.get("Line")!.reject(new Error("Could not load"));
	await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({ mode: "design" }));
	expect(child.tables.loading.value).toBeNull();
	expect(child.shown.value).toBe(editor!.canvas);
	child.open("lines");
	await vi.waitFor(() => expect(router.currentRoute.value.query.table).toBe("lines"));
});

it("ignores the failure of a read the address has moved past", async () => {
	const { router, child } = await mountPage("/doctype/task-note?table=lines");
	const first = loads.get("Line")!;
	await router.push("/doctype/task-note");
	await router.push("/doctype/task-note?table=lines");
	await nextTick();
	loads.get("Line")!.resolve(taskNote({ doctype: "Line", definition: { name: "Line", fields: [] } } as Partial<EditorState>));
	await vi.waitFor(() => expect(child.tables.open.value?.state.doctype).toBe("Line"));
	first.reject(new Error("Could not load"));
	await new Promise((done) => setTimeout(done, 20));
	expect(router.currentRoute.value.query.table).toBe("lines");
	expect(child.tables.open.value?.state.doctype).toBe("Line");
});
