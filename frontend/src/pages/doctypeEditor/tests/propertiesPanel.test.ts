// The properties panel's own controls: the field-type list, a field's Tab, Title field and Fetched
// rows, a container's Columns and Order rows, and the counts in a container's subtitle.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, type App, type Component } from "vue";
import { fetchedLine } from "../fetchFrom";
import ContainerPanel from "../ContainerPanel.vue";
import { dropField } from "../canvasDrops";
import FieldPanel from "../FieldPanel.vue";
import NewFieldTypes from "../NewFieldTypes.vue";
import type { EditorState } from "../editorSource";
import { mountEditor, taskNote } from "./editorFixture";

let app: App | undefined;
let stop: (() => void) | undefined;
afterEach(() => {
	app?.unmount();
	stop?.();
	app = stop = undefined;
	document.body.innerHTML = "";
});

const TWO_TABS = [
	{
		name: "details_tab",
		label: "Details",
		sections: [{ name: "main", columns: [{ name: "column_1", fields: ["subject", "status"] }] }],
	},
	{
		name: "log_tab",
		label: "Log",
		sections: [
			{ name: "more", columns: [{ name: "column_1", fields: ["notes"] }] },
			{ name: "extra", columns: [{ name: "column_1", fields: [] }] },
		],
	},
];

function state(overrides: Partial<EditorState> = {}) {
	const base = taskNote(overrides);
	base.layouts.Details![0].layout = TWO_TABS as never;
	return base;
}

async function mount(initial: EditorState, component: Component, props: (canvas: never) => object) {
	const editor = mountEditor(initial);
	stop = editor.stop;
	const host = document.body.appendChild(document.createElement("div"));
	app = createApp({ render: () => h(component, props(editor.canvas as never)) });
	app.provide("addresses", { doctypes: () => [] });
	app.mount(host);
	for (let i = 0; i < 4; i++) await nextTick();
	return { ...editor, host };
}

const container = (initial: EditorState, selection: object) =>
	mount(initial, ContainerPanel, (canvas) => ({ canvas, selection }));
const fieldPanel = (initial: EditorState, fieldname: string) =>
	mount(initial, FieldPanel, (canvas: { field(name: string): unknown }) => ({
		canvas,
		field: canvas.field(fieldname),
	}));
const text = (selector: string) => document.querySelector(selector)?.textContent?.trim();

describe("the field-type list", () => {
	it("adds a field of the clicked type at the end of the section in view", async () => {
		const { canvas } = await mount(state(), NewFieldTypes, (canvas) => ({ canvas, label: "Add a field" }));
		expect(document.querySelectorAll("[data-panel-new-type]").length).toBeGreaterThan(20);
		document.querySelector<HTMLElement>('[data-panel-new-type="Date"]')!.click();
		await new Promise((resolve) => setTimeout(resolve, 0));
		const added = canvas.working.value.fields.find((field) => field.fieldtype === "Date")!;
		expect(added.label).toBe("Date");
		expect(canvas.place(added.fieldname)).toMatchObject({ tab: "details_tab", section: "main", index: 2 });
	});

	it("filters the types by what is typed", async () => {
		await mount(state(), NewFieldTypes, (canvas) => ({ canvas, label: "Add a field" }));
		const search = document.querySelector<HTMLInputElement>("input")!;
		search.value = "currency";
		search.dispatchEvent(new Event("input"));
		await nextTick();
		expect([...document.querySelectorAll("[data-panel-new-type]")].map((row) => row.getAttribute("data-panel-new-type"))).toEqual(["Currency"]);
	});

	it("drops a dragged type into a column, or on a tab's name, as a new field", async () => {
		const { canvas } = await mount(state(), NewFieldTypes, (canvas) => ({ canvas, label: "Add a field" }));
		dropField(canvas, { added: { element: { type: "Check" }, newIndex: 1 } } as never, { section: "main", column: "column_1" });
		dropField(canvas, { added: { element: { type: "Int" }, newIndex: 0 } } as never, { tab: "log_tab" });
		await new Promise((resolve) => setTimeout(resolve, 0));
		const place = (type: string) =>
			canvas.place(canvas.working.value.fields.find((field) => field.fieldtype === type)!.fieldname);
		expect(place("Check")).toMatchObject({ tab: "details_tab", section: "main", index: 1 });
		expect(place("Int")).toMatchObject({ tab: "log_tab", section: "more" });
	});
});

describe("a field's Tab row", () => {
	it("names the field's tab and moves the field to the tab picked", async () => {
		const { canvas } = await fieldPanel(state(), "subject");
		expect(text("[data-panel-tab]")).toBe("Details");
		document.querySelector<HTMLElement>("[data-panel-tab]")!.click();
		await vi_waitFor(() => [...document.querySelectorAll("[role=menuitem]")].length === 2);
		[...document.querySelectorAll<HTMLElement>("[role=menuitem]")].find((item) => item.textContent?.includes("Log"))!.click();
		await new Promise((resolve) => setTimeout(resolve, 0));
		expect(canvas.place("subject")).toMatchObject({ tab: "log_tab", section: "more" });
	});

	it("is missing on a form with one tab", async () => {
		await fieldPanel(taskNote(), "subject");
		expect(document.querySelector("[data-panel-tab]")).toBeNull();
	});
});

describe("a field's Title field row", () => {
	it("stages the DocType's title_field, with its hint while on", async () => {
		const { canvas } = await fieldPanel(state(), "subject");
		expect(document.querySelector("[data-panel-title-hint]")).toBeNull();
		document.querySelector<HTMLElement>("[data-panel-title-field]")!.click();
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
		expect(canvas.working.value.settings.properties.title_field).toBe("subject");
		expect(text("[data-panel-title-hint]")).toBe("Lists and links show this instead of the ID.");
	});

	it("follows the field's rename and clears when the field is removed", async () => {
		const { canvas } = await fieldPanel(state(), "subject");
		const title = () => canvas.working.value.settings.properties.title_field;
		document.querySelector<HTMLElement>("[data-panel-title-field]")!.click();
		await new Promise((resolve) => setTimeout(resolve, 0));
		app!.unmount();
		app = undefined;
		await canvas.stage({ act: "fields.rename_field", fieldname: "subject", new_fieldname: "heading" });
		expect(title()).toBe("heading");
		await canvas.stage({ act: "fields.delete_field", fieldname: "heading" });
		expect(title()).toBe("");
	});

	it("is missing on a Single DocType", async () => {
		await fieldPanel(state({ definition: { ...state().definition, issingle: 1 } } as never), "subject");
		expect(document.querySelector("[data-panel-title-field]")).toBeNull();
	});

	it("is missing on a field type that cannot be a title", async () => {
		await fieldPanel(state(), "notes");
		expect(document.querySelector("[data-panel-title-field]")).toBeNull();
	});
});

describe("a standard field's Fieldname in Customize", () => {
	const customize = () => ({ ...state(), mode: "Customize", modes: ["Customize"], custom: 0 }) as EditorState;

	it("is locked in the label lane, with no lock or note beside the name", async () => {
		await fieldPanel(customize(), "subject");
		expect(document.querySelector("[data-row-lock]")).not.toBeNull();
		expect(text("[data-panel-fieldname]")).toBe("subject");
		expect(document.querySelector("[data-panel-fieldname-note]")).toBeNull();
	});

	it("keeps its lock and note beside the name in Design on a standard DocType", async () => {
		await fieldPanel({ ...state(), custom: 0 } as EditorState, "subject");
		expect(document.querySelector("[data-row-lock]")).toBeNull();
		expect(text("[data-panel-fieldname-note]")).toContain("Renaming it needs a patch");
	});
});

describe("a Table field", () => {
	it("has no Default or Placeholder row", async () => {
		const initial = state();
		initial.definition.fields.push({ fieldname: "lines", label: "Lines", fieldtype: "Table", options: "Task Note Line" });
		await fieldPanel(initial, "lines");
		const labels = [...document.querySelectorAll(".group\\/row > div:first-child > span")].map((one) => one.textContent);
		expect(labels).toContain("Required");
		expect(labels).not.toContain("Default");
		expect(labels).not.toContain("Placeholder");
	});
});

describe("the Fetched line", () => {
	const fields = [
		{ fieldname: "owner", fieldtype: "Link", options: "User" },
		{ fieldname: "a", label: "A", fieldtype: "Data", fetch_from: "owner.a" },
		{ fieldname: "b", fieldtype: "Data", fetch_from: "owner.b" },
		{ fieldname: "c", label: "C", fieldtype: "Data", fetch_from: "owner.c" },
		{ fieldname: "d", label: "D", fieldtype: "Data", fetch_from: "owner.d" },
		{ fieldname: "e", label: "E", fieldtype: "Data", fetch_from: "other.e" },
	] as never[];

	it("lists up to three labels, then how many more", () => {
		expect(fetchedLine(fields, "owner")).toBe("Fetched now: A, b, C and 1 more.");
		expect(fetchedLine(fields.slice(0, 3), "owner")).toBe("Fetched now: A, b.");
	});

	it("is empty when nothing fetches through the Link", () => {
		expect(fetchedLine(fields, "nobody")).toBe("");
	});
});

describe("a container's subtitle, Columns and Order", () => {
	it("counts a section's fields and a tab's sections and fields", async () => {
		await container(state(), { kind: "section", section: "main" });
		expect(text("[data-panel-subtitle]")).toBe("Section · 2 fields");
		app!.unmount();
		document.body.innerHTML = "";
		stop!();
		await container(state(), { kind: "tab", tab: "log_tab" });
		expect(text("[data-panel-subtitle]")).toBe("Tab · 2 sections · 1 field");
	});

	it("sets a section's columns by adding and removing the last ones", async () => {
		const { canvas, edits } = await container(state(), { kind: "section", section: "main" });
		const columns = () => canvas.tabs.value[0].sections[0].columns.length;
		const pick = async (count: string) => {
			[...document.querySelectorAll<HTMLElement>("button")].find((one) => one.textContent?.trim() === count)!.click();
			await new Promise((resolve) => setTimeout(resolve, 0));
			await nextTick();
		};
		await pick("3");
		expect([columns(), edits.steps.length]).toEqual([3, 2]);
		await pick("1");
		expect(columns()).toBe(1);
	});

	it("keeps the fields of a column it removes", async () => {
		const { canvas } = await container(state(), { kind: "section", section: "main" });
		const placed = () => canvas.tabs.value[0].sections[0].columns.flatMap((column) => column.fields.map(String));
		[...document.querySelectorAll<HTMLElement>("button")].find((one) => one.textContent?.trim() === "2")!.click();
		await new Promise((resolve) => setTimeout(resolve, 0));
		const second = canvas.tabs.value[0].sections[0].columns[1].name;
		dropField(canvas, { moved: { element: "status", newIndex: 0 } } as never, { section: "main", column: second! });
		await new Promise((resolve) => setTimeout(resolve, 0));
		const before = placed();
		[...document.querySelectorAll<HTMLElement>("button")].find((one) => one.textContent?.trim() === "1")!.click();
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
		expect(canvas.tabs.value[0].sections[0].columns).toHaveLength(1);
		expect(placed().sort()).toEqual(before.sort());
	});

	it("shows the tab hint below Conditions, on a tab only", async () => {
		await container(state(), { kind: "tab", tab: "details_tab" });
		const hint = document.querySelector("[data-panel-tab-hint]")!;
		expect(hint.textContent?.trim()).toBe(
			"To move a field to this tab, drag it onto the tab's name, or pick the tab in the field's settings.",
		);
		const conditions = [...document.querySelectorAll("*")].find((one) => one.textContent?.trim() === "Conditions")!;
		expect(conditions.compareDocumentPosition(hint) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		app!.unmount();
		document.body.innerHTML = "";
		stop!();
		await container(state(), { kind: "section", section: "main" });
		expect(document.querySelector("[data-panel-tab-hint]")).toBeNull();
	});

	it("moves a tab left and right, and disables the move at either end", async () => {
		const { canvas } = await container(state(), { kind: "tab", tab: "details_tab" });
		const move = (label: string) => document.querySelector<HTMLButtonElement>(`[aria-label="${label}"]`)!;
		expect(move("Move left").disabled).toBe(true);
		move("Move right").click();
		await new Promise((resolve) => setTimeout(resolve, 0));
		expect(canvas.tabs.value.map((tab) => tab.name)).toEqual(["log_tab", "details_tab"]);
	});
});

async function vi_waitFor(check: () => boolean) {
	for (let i = 0; i < 40 && !check(); i++) await new Promise((resolve) => setTimeout(resolve, 25));
}
