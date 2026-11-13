// Customize's layout parts: the warning before a type's first site layout, the Reset to app layout
// confirm, and the notice on a site layout whose app layout changed.
import { afterEach, describe, expect, it, vi } from "vitest";

const { dialog, runMethod } = vi.hoisted(() => ({
	dialog: { open: vi.fn(), confirm: vi.fn(), danger: vi.fn() },
	runMethod: vi.fn(),
}));
vi.mock("@/shell/dialog", () => ({ shellDialog: () => dialog }));
vi.mock("@framework/ui/api", () => ({ runMethod }));

import { createApp, defineComponent, h, nextTick, ref, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { DesignCanvas } from "../designCanvas";
import EditorCanvas from "../EditorCanvas.vue";
import type { EditorState } from "../editorSource";
import { editorBase } from "../editorModel";
import { ForkWarning } from "../forkWarning";
import { forkWarningText, runOpenLayoutAct } from "../layoutDialogs";
import { resetSummary, resetWording } from "../layoutMenu";
import { PendingEdits } from "../pendingEdits";
import ResetLayoutDialog from "../ResetLayoutDialog.vue";
import { mountEditor, VERSION } from "./editorFixture";
import { leadNote, tabs } from "./layoutsFixture";

const DETAILS = { type: "Details" } as const;
const apps: App[] = [];
let stop: (() => void) | null = null;

afterEach(() => {
	apps.splice(0).forEach((app) => app.unmount());
	stop?.();
	stop = null;
	dialog.open.mockReset();
	document.body.innerHTML = "";
});

/** Lead Note in Customize with no site row: Details is the app's, Quick entry the fallback. */
function unforked(): EditorState {
	const layouts = leadNote().layouts;
	return leadNote({ mode: "Customize", layouts: { ...layouts, Details: layouts.Details!.slice(1) } });
}

function warned(state: EditorState, answers: boolean[] = []) {
	const confirm = vi.fn<Confirm>(async () => answers.shift() ?? true);
	const edits = new PendingEdits({ doctype: state.doctype, mode: state.mode, base_version: VERSION }, () => undefined);
	const forks = new ForkWarning(confirm);
	return { canvas: new DesignCanvas(state, edits, forks), edits, confirm, forks };
}

type Confirm = ConstructorParameters<typeof ForkWarning>[0];

const addSection = { act: "canvas.add_section", layout: DETAILS, tab: "first_tab" };

describe("the warning before a site layout", () => {
	it("asks once per type, on the first edit that forks it", async () => {
		const { canvas, edits, confirm } = warned(unforked());
		expect(await canvas.stage(addSection)).toBe(true);
		expect(await canvas.stage(addSection)).toBe(true);
		expect(confirm.mock.calls.map(([type]) => type)).toEqual(["Details"]);
		expect(edits.staged.value).toHaveLength(2);
		expect(canvas.working.value.layouts.Details!.layouts.map((layout) => layout.source)).toEqual(["site", "site"]);

		await canvas.stage({ act: "canvas.add_section", layout: { type: "Quick Entry" }, tab: "first_tab" });
		expect(confirm.mock.calls.map(([type]) => type)).toEqual(["Details", "Quick Entry"]);
	});

	it("asks again on another DocType the same page opens", async () => {
		const { canvas, confirm, forks } = warned(unforked());
		await canvas.stage(addSection);
		const other = { ...unforked(), doctype: "Lead Call" };
		const edits = new PendingEdits({ doctype: other.doctype, mode: other.mode, base_version: VERSION }, () => undefined);
		await new DesignCanvas(other, edits, forks).stage(addSection);
		expect(confirm.mock.calls.map(([type]) => type)).toEqual(["Details", "Details"]);
	});

	it("asks on a child table's first edit, about the child's layout", async () => {
		const confirm = vi.fn(async () => true);
		const parent = unforked();
		parent.definition.fields.push({ fieldname: "lines", label: "Lines", fieldtype: "Table", options: "Lead Note Line" });
		const mounted = mountEditor(parent, { forks: new ForkWarning(confirm) });
		stop = mounted.stop;
		const line = leadNote({
			mode: "Customize",
			doctype: "Lead Note Line",
			layouts: { Details: [{ name: null, source: "app", condition: null, omitted: [], layout: tabs("qty") }] },
			definition: { name: "Lead Note Line", istable: 1, fields: [{ fieldname: "qty", label: "Qty", fieldtype: "Float" }] },
		});
		runMethod.mockResolvedValueOnce({ data: line });
		await mounted.children.show("lines");
		await mounted.children.open.value!.canvas.stage(addSection);
		expect(confirm).toHaveBeenCalledOnce();
		expect(confirm).toHaveBeenCalledWith("Details", expect.objectContaining({ doctype: "Lead Note Line" }));
	});

	it("is not asked while a reload stages the edits again", async () => {
		const confirm = vi.fn(async () => true);
		const mounted = mountEditor(leadNote({ mode: "Customize" }), { reloaded: unforked, forks: new ForkWarning(confirm) });
		stop = mounted.stop;
		await mounted.canvas.stage(addSection);
		await mounted.save.reloadAndReapply();
		expect(confirm).not.toHaveBeenCalled();
		expect(mounted.edits.staged.value).toHaveLength(1);
	});

	it("stages nothing on Cancel, and asks again on the next edit", async () => {
		const { canvas, edits, confirm } = warned(unforked(), [false, true]);
		expect(await canvas.stage(addSection)).toBe(false);
		expect(edits.staged.value).toEqual([]);
		expect(canvas.working.value.layouts.Details!.layouts[0].source).toBe("app");
		expect(await canvas.stage(addSection)).toBe(true);
		expect(confirm).toHaveBeenCalledTimes(2);
	});

	it("never asks in Design, nor on a type that has a site row", async () => {
		const design = warned(leadNote());
		await design.canvas.stage(addSection);
		const forked = warned(leadNote({ mode: "Customize" }));
		await forked.canvas.stage(addSection);
		expect(design.confirm).not.toHaveBeenCalled();
		expect(forked.confirm).not.toHaveBeenCalled();
		expect(forked.edits.staged.value).toHaveLength(1);
	});

	it("does not ask for a site field placed on an unforked Details, which only takes an anchor", async () => {
		const state = unforked();
		state.definition.fields.push({ fieldname: "custom_rating", label: "Rating", fieldtype: "Int", is_custom_field: 1 } as never);
		const { canvas, confirm } = warned(state);
		const place = { act: "canvas.place_field", layout: DETAILS, fieldname: "custom_rating", section: "main", column: "column_1" };
		expect(await canvas.stage(place)).toBe(true);
		expect(confirm).not.toHaveBeenCalled();
		expect(canvas.working.value.layouts.Details!.layouts[0].source).toBe("app");

		await canvas.stage({ act: "canvas.place_field", layout: DETAILS, fieldname: "notes", section: "main", column: "column_1" });
		expect(confirm.mock.calls.map(([type]) => type)).toEqual(["Details"]);
	});
});

describe("Reset to app layout", () => {
	const customize = () => leadNote({ mode: "Customize" });

	it("lists the type's site layouts it removes and the app layouts that come back", () => {
		const editor = mountEditor(customize());
		stop = editor.stop;
		void editor.canvas.stage({ act: "layouts.add", type: "Details", id: "new-1", title: "Urgent", condition: "doc.urgent", start: "copy" });
		expect(resetSummary(editor.canvas.working.value, "Details")).toEqual({
			removes: [
				{ name: "Details", condition: null },
				{ name: "Urgent", condition: "doc.urgent" },
			],
			restores: [
				{ name: "Details", condition: null },
				{ name: "Done", condition: "doc.status == 'Done'" },
			],
			fallback: null,
		});
		expect(resetSummary(editor.canvas.working.value, "Quick Entry")).toMatchObject({ restores: [], fallback: "From DocType fields" });
	});

	it("draws the rows in its confirm", async () => {
		const editor = mountEditor(customize());
		stop = editor.stop;
		const root = mount(ResetLayoutDialog, { label: "Details", confirmLabel: "Reset to app layout", summary: resetSummary(editor.canvas.working.value, "Details"), close: () => undefined });
		await nextTick();
		const texts = (selector: string) => [...root.querySelectorAll(`${selector} li`)].map((row) => row.textContent!.trim());
		expect(texts("[data-reset-removes]")).toEqual(["Details"]);
		expect(texts("[data-reset-restores]")).toEqual(["Details", "Done"]);
	});

	it("stages the reset only after the confirm", async () => {
		const editor = mountEditor(customize());
		stop = editor.stop;
		dialog.open.mockResolvedValueOnce(null).mockResolvedValueOnce(true);
		await runOpenLayoutAct(editor.canvas, "reset_to_app");
		expect(editor.edits.staged.value).toEqual([]);
		expect(dialog.open.mock.calls[0][1].summary.removes).toEqual([{ name: "Details", condition: null }]);
		await runOpenLayoutAct(editor.canvas, "reset_to_app");
		expect(editor.edits.staged.value).toEqual([{ act: "layouts.reset_to_app", type: "Details" }]);
	});
});

describe("the wording per source", () => {
	const working = () => editorBase(unforked());

	it("the warning names what the site layout replaces", () => {
		expect(forkWarningText(working(), "Details").message).toBe(
			"Saving creates a site layout for Details that replaces the app layout on this site. Every Details layout becomes a site layout, and later changes from the app do not reach them.",
		);
		expect(forkWarningText(working(), "Quick Entry").message).toBe(
			"Saving creates a site layout for Quick entry that replaces the layout made from the DocType's fields.",
		);
		expect(forkWarningText(working(), "Side Panel").message).toBe(
			"Side panel is not set up yet. Saving creates its first layout, as a site layout.",
		);
		expect(forkWarningText(working(), "New Record").message).toBe(
			"New record shows the Details layout until now. Saving gives it a site layout of its own.",
		);
	});

	it("the reset names what comes back", () => {
		expect(resetWording(working(), "Details")).toEqual({ title: "Reset to app layout?", confirmLabel: "Reset to app layout" });
		expect(resetWording(working(), "Quick Entry")).toEqual({
			title: "Reset to the layout from DocType fields?",
			confirmLabel: "Reset",
		});
		expect(resetWording(working(), "Side Panel")).toEqual({ title: "Remove the Side panel site layouts?", confirmLabel: "Remove" });
		expect(resetWording(working(), "New Record")).toEqual({
			title: "Reset New record to the Details layout?",
			confirmLabel: "Reset",
		});
	});
});

describe("the app layout changed notice", () => {
	const changed = (overrides: Partial<EditorState> = {}) => {
		const state = leadNote(overrides);
		state.layouts.Details![0] = { ...state.layouts.Details![0], source_changed: true };
		return state;
	};

	it("shows only on a site layout whose app layout changed, in Customize", async () => {
		const root = await draw(changed({ mode: "Customize" }));
		await until(() => root.querySelector("[data-app-layout-notice]"));
		expect(root.querySelector("[data-app-layout-notice]")).not.toBeNull();
		expect((await draw(leadNote({ mode: "Customize" }))).querySelector("[data-app-layout-notice]")).toBeNull();
		expect((await draw(changed({ custom: 1 }))).querySelector("[data-app-layout-notice]")).toBeNull();
	});

	it("draws the app layout read-only in the canvas's place", async () => {
		const root = await draw(changed({ mode: "Customize" }));
		await until(() => root.querySelector("[data-app-layout-notice]"));
		expect(root.textContent).toContain("The app's Details layout changed since this site layout was made");
		button(root, "View app layout").click();
		await settle();
		const view = root.querySelector("[data-app-layout-view]")!;
		expect([...view.querySelectorAll("[data-canvas-field]")].map((field) => field.getAttribute("data-canvas-field"))).toEqual([
			"subject",
			"status",
		]);
		expect(view.querySelector("[data-canvas-add-section]")).toBeNull();
		expect(root.textContent).toContain("Reset to app layout");
		button(root, "Back to site layout").click();
		await settle();
		expect(root.querySelector("[data-app-layout-view]")).toBeNull();
	});
});

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

/** Waits for the lazy notice's first import. */
async function until(found: () => unknown) {
	for (let turn = 0; turn < 100 && !found(); turn++) await new Promise((resolve) => setTimeout(resolve, 20));
}

function mount(component: unknown, props: Record<string, unknown>) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const router = createRouter({ history: createMemoryHistory(), routes: [{ path: "/:rest(.*)*", component: { render: () => null } }] });
	const app = createApp(defineComponent({ render: () => h(component as never, props) }));
	app.use(router).provide("addresses", { doctypes: () => ref([]) });
	app.mount(root);
	apps.push(app);
	return root;
}

async function draw(state: EditorState) {
	stop?.();
	const editor = mountEditor(state);
	stop = editor.stop;
	const root = mount(EditorCanvas, { canvas: editor.canvas, save: editor.save, metaLine: "", customize: null });
	await settle();
	return root;
}

function button(root: Element, label: string): HTMLButtonElement {
	return [...root.querySelectorAll("button")].find((one) => one.textContent!.trim() === label)!;
}
