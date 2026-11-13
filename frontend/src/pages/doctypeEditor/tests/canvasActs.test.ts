import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, ref } from "vue";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("frappe-ui", () => ({ toast }));

import { acts } from "@/acts/dispatcher";
import { canvasMove } from "../canvasMoves";
import { DesignCanvas } from "../designCanvas";
import { useEditorActs } from "../editorActs";
import type { EditorState } from "../editorSource";
import { PendingEdits, type EditorTab } from "../pendingEdits";

function state(mode: "Design" | "Customize" = "Design"): EditorState {
	return {
		doctype: "Task Note",
		mode,
		modes: ["Design", "Customize"],
		base_version: { doctype: "", layouts: {}, app_layouts: {} },
		custom: 1,
		module: "Desk",
		app_title: null,
		record_count: 0,
		value_counts: {},
		layouts: {
			Details: [
				{
					name: null,
					source: "fallback",
					omitted: [],
					layout: [
						{
							name: "details",
							sections: [
								{
									name: "main",
									columns: [
										{ name: "column_1", fields: ["subject", "status"] },
										{ name: "column_2", fields: ["due"] },
									],
								},
								{ name: "more", label: "More", columns: [{ name: "column_1", fields: ["notes"] }] },
							],
						},
						{
							name: "activity",
							label: "Activity",
							sections: [{ name: "log", columns: [{ name: "column_1", fields: [] }] }],
						},
					],
				},
			],
		},
		definition: {
			name: "Task Note",
			fields: [
				{ fieldname: "subject", label: "Subject", fieldtype: "Data" },
				{ fieldname: "status", label: "Status", fieldtype: "Select" },
				{ fieldname: "due", label: "Due", fieldtype: "Date" },
				{ fieldname: "notes", label: "Notes", fieldtype: "Text" },
				{ fieldname: "spare", label: "Spare", fieldtype: "Data" },
			],
		},
	};
}

let stop: () => void;

function mount(mode: "Design" | "Customize" = "Design") {
	const tab = ref<EditorTab>("editor");
	const edits = new PendingEdits(
		{ doctype: "Task Note", mode, base_version: { doctype: "", layouts: {}, app_layouts: {} } },
		(opened) => (tab.value = opened),
	);
	const canvas = new DesignCanvas(state(mode), edits);
	const scope = effectScope();
	scope.run(() =>
		useEditorActs({
			edits,
			tab,
			canvas: () => canvas,
			find: () => undefined,
			previewRecord: () => undefined,
			recordOptions: async () => [],
		}),
	);
	stop = () => scope.stop();
	return { canvas, edits, tab };
}

const layoutOf = (canvas: DesignCanvas) =>
	canvas.tabs.value.map((tab) => ({
		tab: tab.name,
		...(tab.label ? { label: tab.label } : {}),
		sections: tab.sections.map((section) => [
			section.name,
			...(section.label ? [section.label] : []),
			section.columns.map((column) => `${column.name}: ${column.fields.join(",")}`),
		]),
	}));

beforeEach(() => toast.error.mockReset());
afterEach(() => stop());

describe("the canvas acts", () => {
	const cases: [act: string, value: Record<string, unknown>, check: (canvas: DesignCanvas) => unknown, expected: unknown][] = [
		["canvas.add_tab", { label: "Billing" }, (c) => c.tabs.value.at(-1)?.name, "billing"],
		["canvas.remove_tab", { tab: "activity" }, (c) => c.tabs.value[0].sections.map((s) => s.name), ["main", "more", "log"]],
		["canvas.move_tab", { tab: "activity", index: 0 }, (c) => c.tabs.value.map((t) => t.name), ["activity", "details"]],
		["canvas.add_section", { tab: "activity", label: "Calls" }, (c) => c.tabs.value[1].sections.map((s) => s.name), ["log", "calls"]],
		["canvas.remove_section", { section: "more" }, (c) => c.tabs.value[0].sections[0].columns[1].fields, ["due", "notes"]],
		["canvas.move_section", { section: "more", tab: "activity", index: 0 }, (c) => c.tabs.value[1].sections.map((s) => s.name), ["more", "log"]],
		["canvas.add_column", { section: "more" }, (c) => c.tabs.value[0].sections[1].columns.map((col) => col.name), ["column_1", "column_2"]],
		["canvas.remove_column", { section: "main", column: "column_2" }, (c) => c.tabs.value[0].sections[0].columns.map((col) => col.fields), [["subject", "status", "due"]]],
		["canvas.move_column", { section: "main", column: "column_2", to_section: "more", index: 0 }, (c) => c.tabs.value[0].sections[1].columns.map((col) => col.fields), [["due"], ["notes"]]],
		["canvas.place_field", { fieldname: "spare", section: "main", column: "column_2", index: 0 }, (c) => c.place("spare"), { tab: "details", section: "main", column: "column_2", index: 0 }],
		["canvas.move_field", { fieldname: "subject", section: "more", column: "column_1" }, (c) => c.place("subject"), { tab: "details", section: "more", column: "column_1", index: 1 }],
		["canvas.move_field", { fieldname: "due", tab: "activity" }, (c) => c.place("due"), { tab: "activity", section: "log", column: "column_1", index: 0 }],
		["canvas.unplace_field", { fieldname: "status" }, (c) => c.offLayout.value.map((row) => row.field.fieldname), ["status", "spare"]],
		["canvas.set_container_property", { container: "more", property: "label", value: "Extra" }, (c) => c.tabs.value[0].sections[1].label, "Extra"],
		["canvas.set_container_property", { container: "column_1", section: "more", property: "label", value: "Left" }, (c) => c.tabs.value[0].sections[1].columns[0].label, "Left"],
		["canvas.set_container_property", { container: "more", property: "label", value: "" }, (c) => c.tabs.value[0].sections[1].label, undefined],
		["canvas.set_container_property", { container: "main", property: "collapsible", value: true }, (c) => c.tabs.value[0].sections[0].collapsible, true],
	];

	it.each(cases)("%s stages one undo step, and undo restores the layout", async (act, value, check, expected) => {
		const { canvas, edits } = mount();
		const before = layoutOf(canvas);
		await acts.run(act, value);
		expect(check(canvas)).toEqual(expected);
		expect(edits.staged.value).toEqual([{ ...value, act, layout: { type: "Details" } }]);
		edits.undo();
		expect(layoutOf(canvas)).toEqual(before);
		expect(edits.canUndo.value).toBe(false);
	});

	it("add a tab or a section where the palette asks, and select it", async () => {
		const { canvas } = mount();
		await acts.run("canvas.add_tab");
		expect(canvas.selection.value).toEqual({ kind: "tab", tab: "tab_3" });
		expect(canvas.openTab.value?.name).toBe("tab_3");
		await acts.run("canvas.select", { kind: "tab", tab: "activity" });
		await acts.run("canvas.add_section");
		expect(canvas.selection.value).toEqual({ kind: "section", section: "section_4" });
		expect(canvas.openTab.value?.sections.map((section) => section.name)).toEqual(["log", "section_4"]);
	});

	it("select a field and open its tab", async () => {
		const { canvas } = mount();
		await acts.run("canvas.select", { kind: "field", fieldname: "status" });
		expect(canvas.selectedField.value?.label).toBe("Status");
		await acts.run("canvas.move_field", { fieldname: "status", tab: "activity" });
		await acts.run("canvas.select", { kind: "field", fieldname: "status" });
		expect(canvas.openTab.value?.name).toBe("activity");
	});

	it("show a refused edit as a translated toast, and stage nothing", async () => {
		const { edits } = mount();
		await acts.perform("canvas.move_field", { fieldname: "ghost", section: "main", column: "column_1" });
		expect(toast.error).toHaveBeenCalledWith("ghost is not a field of Task Note.");
		await acts.perform("canvas.remove_tab", { tab: "activity" });
		await acts.perform("canvas.remove_tab", { tab: "details" });
		expect(toast.error).toHaveBeenLastCalledWith("A layout keeps at least one tab.");
		expect(edits.staged.value).toHaveLength(1);
	});

	it("stay off every surface outside the Editor tab and in Customize", () => {
		const { tab } = mount();
		expect(acts.find("canvas.add_section")).toBeDefined();
		tab.value = "preview";
		expect(acts.find("canvas.add_section")).toBeUndefined();
		expect(acts.find("fields.add_field")).toBeUndefined();
		stop();
		mount("Customize");
		expect(acts.find("canvas.move_field")).toBeUndefined();
		expect(acts.find("canvas.select")).toBeDefined();
	});
});

describe("fields.add_field on the canvas", () => {
	it("adds and places the field as one undo step, and selects it", async () => {
		const { canvas, edits } = mount();
		const value = { label: "Due On", fieldtype: "Date", section: "more", column: "column_1", index: 0 };
		await acts.run("fields.add_field", value);
		expect(canvas.place("due_on")).toEqual({ tab: "details", section: "more", column: "column_1", index: 0 });
		expect(canvas.selection.value).toEqual({ kind: "field", fieldname: "due_on" });
		expect(edits.staged.value).toEqual([{ ...value, act: "fields.add_field", layout: { type: "Details" } }]);
		edits.undo();
		expect(canvas.field("due_on")).toBeUndefined();
		expect(canvas.place("due_on")).toBeNull();
	});

	it("with no value opens Add field in the selected section, else the open tab's last", async () => {
		const { canvas } = mount();
		await acts.run("fields.add_field");
		expect(canvas.adding.value).toBe("more");
		await acts.run("canvas.select", { kind: "field", fieldname: "due" });
		await acts.run("fields.add_field");
		expect(canvas.adding.value).toBe("main");
	});

	it("goes after the selected field of that section, else to its shortest column", async () => {
		const { canvas } = mount();
		expect(canvas.addPlace("main")).toEqual({ section: "main", column: "column_2" });
		canvas.select({ kind: "field", fieldname: "subject" });
		expect(canvas.addPlace("main")).toEqual({ section: "main", column: "column_1", index: 1 });
	});
});

describe("the tray", () => {
	it("marks a field added since the save and one the save asked for", async () => {
		const { canvas } = mount();
		await acts.run("fields.add_field", { label: "Ref", fieldtype: "Data" });
		canvas.askedOnSave.value = ["spare"];
		expect(canvas.offLayout.value.map(({ field, ...marks }) => ({ fieldname: field.fieldname, ...marks }))).toEqual([
			{ fieldname: "spare", new: false, asked: true },
			{ fieldname: "ref", new: true, asked: false },
		]);
	});
});

describe("Alt+Arrow and the menus' moves", () => {
	const tabs = state().layouts.Details![0].layout;

	it("move a field within its column, then across sections and columns", () => {
		const field = (fieldname: string) => ({ kind: "field" as const, fieldname });
		expect(canvasMove(tabs, field("subject"), "down")?.value).toEqual({ fieldname: "subject", section: "main", column: "column_1", index: 1 });
		expect(canvasMove(tabs, field("subject"), "up")).toBeNull();
		expect(canvasMove(tabs, field("status"), "down")?.value).toEqual({ fieldname: "status", section: "main", column: "column_2", index: 0 });
		expect(canvasMove(tabs, field("due"), "down")?.value).toEqual({ fieldname: "due", section: "more", column: "column_1", index: 0 });
		expect(canvasMove(tabs, field("status"), "right")?.value).toEqual({ fieldname: "status", section: "main", column: "column_2", index: 1 });
		expect(canvasMove(tabs, field("due"), "right")).toBeNull();
		expect(canvasMove(tabs, field("notes"), "up")?.act).toBe("canvas.move_field");
	});

	it("move a section within its tab or to the tab beside it, and a column or tab sideways", () => {
		expect(canvasMove(tabs, { kind: "section", section: "more" }, "up")?.value).toEqual({ section: "more", tab: "details", index: 0 });
		expect(canvasMove(tabs, { kind: "section", section: "more" }, "down")).toBeNull();
		expect(canvasMove(tabs, { kind: "section", section: "more" }, "right")?.value).toEqual({ section: "more", tab: "activity", index: 1 });
		expect(canvasMove(tabs, { kind: "column", section: "main", column: "column_1" }, "right")?.value).toEqual({
			section: "main",
			column: "column_1",
			to_section: "main",
			index: 1,
		});
		expect(canvasMove(tabs, { kind: "tab", tab: "activity" }, "left")).toEqual({ act: "canvas.move_tab", value: { tab: "activity", index: 0 } });
		expect(canvasMove(tabs, { kind: "tab", tab: "activity" }, "right")).toBeNull();
	});
});
