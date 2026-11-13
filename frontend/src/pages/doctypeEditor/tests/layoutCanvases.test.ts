// The canvas and the panel of each layout type: the side panel's frame, the Create dialog's frame,
// and the panel's tray outside Details.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App, type Component } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
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

async function draw(component: Component, layout: LayoutRef, fromNewRecord = false) {
	editor = mountEditor(leadNote());
	if (fromNewRecord) editor.canvas.openForNewRecord(layout);
	else editor.canvas.open(layout);
	const router = createRouter({ history: createMemoryHistory(), routes: [{ path: "/:rest(.*)*", component: { render: () => null } }] });
	const root = document.createElement("div");
	document.body.appendChild(root);
	const props =
		component === EditorCanvas
			? { canvas: editor.canvas, save: editor.save, metaLine: "", customize: null }
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
	});

	it("keeps Details' tray under its canvas", async () => {
		const root = await draw(EditorCanvas, { type: "Details" });
		expect(root.querySelector("[data-canvas-tray]")).not.toBeNull();
		expect(root.querySelector("[data-new-record-note]")).toBeNull();
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

describe("the panel outside Details", () => {
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

	it("shows Details' hint, not the tray", async () => {
		const root = await draw(EditorPanel, { type: "Details" });
		expect(root.querySelector("[data-panel-tray]")).toBeNull();
	});
});
