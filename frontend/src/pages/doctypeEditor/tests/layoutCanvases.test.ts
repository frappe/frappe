// The canvas and the panel of each layout type: the side panel's frame, the Create dialog's frame,
// and the panel's group of fields off the layout.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App, type Component } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { acts } from "@/acts/dispatcher";
import EditorCanvas from "../EditorCanvas.vue";
import EditorPanel from "../EditorPanel.vue";
import type { LayoutRef } from "../workingLayouts";
import { mountEditor } from "./editorFixture";
import { leadNote } from "./layoutsFixture";

const apps: App[] = [];
let editor: ReturnType<typeof mountEditor>;

afterEach(() => {
	apps.splice(0).forEach((app) => app.unmount());
	editor.stop();
	document.body.innerHTML = "";
});

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

async function draw(component: Component, layout: LayoutRef, fromNewRecord = false, extra: Record<string, unknown> = {}) {
	editor = mountEditor(leadNote());
	if (extra.table) editor.canvas.state.definition.istable = 1;
	if (extra.readOnly) Object.assign(editor.canvas, { editable: false });
	if (fromNewRecord) editor.canvas.openForNewRecord(layout);
	else editor.canvas.open(layout);
	const router = createRouter({ history: createMemoryHistory(), routes: [{ path: "/:rest(.*)*", component: { render: () => null } }] });
	const root = document.createElement("div");
	document.body.appendChild(root);
	const props =
		component === EditorCanvas
			? { canvas: editor.canvas, save: editor.save, metaLine: "", customize: null, ...(extra.table ? { table: extra.table } : {}) }
			: { canvas: editor.canvas };
	const app = createApp(defineComponent({ render: () => h(component, props) }));
	app.use(router).provide("addresses", { doctypes: () => ref([]) });
	app.mount(root);
	apps.push(app);
	await settle();
	return root;
}

describe("the canvas of each layout type", () => {
	it("draws the side panel's built-ins as one locked block, and asks for a first field", async () => {
		const root = await draw(EditorCanvas, { type: "Side Panel" });
		expect(root.querySelector("[data-canvas-side-panel] [data-canvas-builtins]")).not.toBeNull();
		expect(root.querySelector("[data-canvas-side-panel-empty]")!.textContent).toContain("No fields on the side panel yet");
		expect(root.querySelector("[data-canvas-tray]")).toBeNull();
	});

	it("draws Quick entry inside the Create dialog's frame", async () => {
		const root = await draw(EditorCanvas, { type: "Quick Entry" });
		const frame = root.querySelector("[data-canvas-quick-entry]")!;
		expect(frame.textContent).toContain("New Lead Note");
		expect(frame.querySelector('[data-canvas-field="notes"]')).not.toBeNull();
		const create = [...frame.querySelectorAll("button")].find((one) => one.textContent?.trim() === "Create");
		expect(create).toBeDefined();
		expect(create!.closest("[inert]")).not.toBeNull();
	});

	it("draws no tray under Details' canvas", async () => {
		const root = await draw(EditorCanvas, { type: "Details" });
		expect(root.querySelector("[data-canvas-tray]")).toBeNull();
		expect(root.querySelector("[data-new-record-note]")).toBeNull();
	});

	it("keeps a plain list of the fields off the layout under a read-only canvas", async () => {
		const root = await draw(EditorCanvas, { type: "Details" }, false, { readOnly: true });
		const tray = root.querySelector("[data-canvas-tray]")!;
		expect(tray).not.toBeNull();
		expect(tray.textContent).toContain("Fields not on this layout");
		expect([...tray.querySelectorAll("[data-canvas-tray-field]")].map((row) => row.getAttribute("data-canvas-tray-field"))).toEqual(["notes", "spare"]);
		expect(tray.querySelector("button[class*='opacity-0']")).toBeNull();
	});

	it("notes that a new record uses the Details layout its Edit layout opened", async () => {
		const root = await draw(EditorCanvas, { type: "New Record", id: "app:1" }, true);
		expect(editor.canvas.openLayout.value).toEqual({ type: "Details", id: "app:1" });
		expect(root.querySelector("[data-new-record-note]")!.textContent).toBe("New record uses the Details layout");
		editor.canvas.open({ type: "Details" });
		await nextTick();
		expect(root.querySelector("[data-new-record-note]")).toBeNull();
	});
});

describe("the canvas of a child table", () => {
	const table = { field: { fieldname: "items", label: "Items", fieldtype: "Table", options: "Lead Note" }, parent: "Sales Invoice" };

	it("notes it is the row's dialog and draws the parent's grid under the meta", async () => {
		const root = await draw(EditorCanvas, { type: "Details" }, false, { table });
		expect(root.querySelector("[data-editor-meta]")!.textContent).toContain("Child table · This form is the row's dialog.");
		expect(root.querySelector("[data-child-grid]")!.textContent).toContain("Items in Sales Invoice");
		expect(root.querySelector("[data-editor-site-fields]")).toBeNull();
	});
});

describe("the panel's group of fields off the layout", () => {
	it("lists the fields not on this layout first, and places a clicked one", async () => {
		const root = await draw(EditorPanel, { type: "Quick Entry" });
		const tray = () => [...root.querySelectorAll("[data-panel-tray-field]")].map((row) => row.getAttribute("data-panel-tray-field"));
		expect(tray()).toEqual(["subject", "status"]);
		expect(root.querySelector("[data-panel-new-field]")).not.toBeNull();
		root.querySelector<HTMLButtonElement>('[data-panel-tray-field="status"]')!.click();
		await settle();
		expect(tray()).toEqual(["subject"]);
		expect(editor.canvas.place("status")).not.toBeNull();
	});

	it("adds a field of a picked type to this layout only", async () => {
		const root = await draw(EditorPanel, { type: "Quick Entry" });
		root.querySelector<HTMLButtonElement>('[data-panel-new-type="Date"]')!.click();
		await settle();
		expect(editor.canvas.place("date")).not.toBeNull();
		editor.canvas.open({ type: "Details" });
		expect(editor.canvas.place("date")).toBeNull();
	});

	it("filters the group by what is typed, and forgets the query once the group goes", async () => {
		const root = await draw(EditorPanel, { type: "Details" });
		const rowsNow = () => [...root.querySelectorAll("[data-panel-tray-field]")].map((row) => row.getAttribute("data-panel-tray-field"));
		const search = root.querySelector<HTMLInputElement>("[data-panel-tray-search]")!;
		search.value = "sp";
		search.dispatchEvent(new Event("input", { bubbles: true }));
		await settle();
		expect(rowsNow()).toEqual(["spare"]);
		expect(root.querySelector('[data-panel-tray-field="spare"]')!.getAttribute("title")).toBe("Spare (spare)");
		root.querySelector<HTMLButtonElement>('[data-panel-tray-field="spare"]')!.click();
		await settle();
		expect(root.textContent).toContain("No field matches.");
		await acts.perform("canvas.place_field", { fieldname: "notes", tab: editor.canvas.openTab.value?.name });
		await settle();
		expect(root.querySelector("[data-panel-tray]")).toBeNull();
		await acts.perform("canvas.unplace_field", { fieldname: "notes" });
		await settle();
		expect(rowsNow()).toEqual(["notes"]);
	});

	it("draws no group on Details while every field is on the layout", async () => {
		const root = await draw(EditorPanel, { type: "Details" });
		for (const fieldname of ["notes", "spare"]) {
			root.querySelector<HTMLButtonElement>(`[data-panel-tray-field="${fieldname}"]`)!.click();
			await settle();
		}
		expect(root.querySelector("[data-panel-tray]")).toBeNull();
		expect(root.querySelector("[data-panel-new-field]")!.textContent).toContain("Add a field");
	});

	it("lists Details' off-layout fields first, and places a clicked one back", async () => {
		const root = await draw(EditorPanel, { type: "Details" });
		const tray = () => [...root.querySelectorAll("[data-panel-tray-field]")].map((row) => row.getAttribute("data-panel-tray-field"));
		expect(tray()).toEqual(["notes", "spare"]);
		expect(root.querySelector("[data-panel-new-field]")!.textContent).toContain("New field");
		root.querySelector<HTMLButtonElement>('[data-panel-tray-field="notes"]')!.click();
		await settle();
		expect(tray()).toEqual(["spare"]);
		root.querySelector<HTMLButtonElement>('[data-panel-tray-field="spare"]')!.click();
		await settle();
		expect(root.querySelector("[data-panel-tray]")).toBeNull();
		expect(editor.canvas.place("spare")).not.toBeNull();
	});
});

describe("the canvas scroll on selection", () => {
	it("follows a selected field, and stays put for a section", async () => {
		const scroll = vi.fn();
		Element.prototype.scrollIntoView = scroll;
		const root = await draw(EditorCanvas, { type: "Details" });
		const section = root.querySelector("[data-canvas-section]")!.getAttribute("data-canvas-section")!;
		editor.canvas.select({ kind: "section", section });
		await settle();
		expect(scroll).not.toHaveBeenCalled();
		editor.canvas.select({ kind: "field", fieldname: "subject" });
		await settle();
		expect(scroll).toHaveBeenCalledWith({ block: "nearest" });
	});
});
