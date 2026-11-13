import { describe, expect, it } from "vitest";
import {
	editorBase,
	fieldsOffLayout,
	reqdInConditional,
	workingState,
	type FlatEdit,
	type WorkingState,
} from "../editorModel";
import type { EditorState } from "../editorSource";

const DETAILS = { type: "Details" };

function state(): EditorState {
	return {
		doctype: "Task Note",
		mode: "Design",
		modes: ["Design"],
		base_version: { doctype: "", layouts: {}, app_layouts: {} },
		custom: 1,
		module: "Desk",
		app_title: null,
		record_count: 3,
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
			description: "Notes on tasks",
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

function deepFreeze<T>(value: T): T {
	if (value && typeof value === "object") {
		Object.values(value).forEach(deepFreeze);
		Object.freeze(value);
	}
	return value;
}

const base = deepFreeze(editorBase(state()));

const canvas = (act: string, value: Record<string, unknown>): FlatEdit => ({
	act: `canvas.${act}`,
	layout: DETAILS,
	...value,
});

/** Replays the edits, and checks that undoing the last one gives back the state before it. */
function replay(...edits: FlatEdit[]): WorkingState {
	const before = workingState(base, edits.slice(0, -1));
	const snapshot = structuredClone(before);
	const after = workingState(before, edits.slice(-1));
	expect(before).toEqual(snapshot);
	expect(workingState(base, edits)).toEqual(after);
	expect(after).not.toEqual(snapshot);
	expect(workingState(base, edits.slice(0, -1))).toEqual(snapshot);
	return after;
}

const tabNames = (working: WorkingState) => working.layout.map((tab) => tab.name);
const sectionsOf = (working: WorkingState, tab: string) =>
	working.layout.find((each) => each.name === tab)!.sections;
const columnsOf = (working: WorkingState, section: string) =>
	working.layout.flatMap((tab) => tab.sections).find((each) => each.name === section)!.columns;

describe("editorBase", () => {
	it("starts from the definition's fields, the Details layout and the description", () => {
		expect(base.fields.map((field) => field.fieldname)).toEqual(["subject", "status", "due", "notes", "spare"]);
		expect(tabNames(base)).toEqual(["details", "activity"]);
		expect(base.description).toBe("Notes on tasks");
	});

	it("starts with no tabs when the DocType has no Details layout", () => {
		const bare = { ...state(), layouts: {} };
		expect(editorBase(bare).layout).toEqual([]);
	});
});

describe("canvas tabs", () => {
	it("adds a tab at the end, named from its label", () => {
		const working = replay(canvas("add_tab", { label: "Billing Info" }));
		expect(working.layout.at(-1)).toEqual({ name: "billing_info", label: "Billing Info", sections: [] });
	});

	it("names an unlabelled tab by its position, suffixed when taken", () => {
		const first = replay(canvas("add_tab", { index: 0 }));
		expect(tabNames(first)).toEqual(["tab_1", "details", "activity"]);
		const clash = replay(canvas("add_tab", { label: "Activity" }));
		expect(tabNames(clash)).toEqual(["details", "activity", "activity_3"]);
	});

	it("removes a tab and gives its sections to the tab before", () => {
		const working = replay(canvas("remove_tab", { tab: "activity" }));
		expect(tabNames(working)).toEqual(["details"]);
		expect(sectionsOf(working, "details").map((section) => section.name)).toEqual(["main", "more", "log"]);
	});

	it("gives the first tab's sections to the tab after", () => {
		const working = replay(canvas("remove_tab", { tab: "details" }));
		expect(sectionsOf(working, "activity").map((section) => section.name)).toEqual(["log", "main", "more"]);
	});

	it("keeps the last tab", () => {
		const one = workingState(base, [canvas("remove_tab", { tab: "activity" })]);
		expect(() => workingState(one, [canvas("remove_tab", { tab: "details" })])).toThrow(
			"A layout keeps at least one tab.",
		);
	});

	it("moves a tab", () => {
		expect(tabNames(replay(canvas("move_tab", { tab: "activity", index: 0 })))).toEqual(["activity", "details"]);
	});
});

describe("canvas sections", () => {
	it("adds a section with one empty column, named across the layout", () => {
		const working = replay(canvas("add_section", { tab: "activity", label: "Main" }));
		expect(sectionsOf(working, "activity").at(-1)).toEqual({
			name: "main_4",
			label: "Main",
			columns: [{ name: "column_1", fields: [] }],
		});
	});

	it("removes a section and gives its fields to the section before", () => {
		const working = replay(canvas("remove_section", { section: "more" }));
		expect(sectionsOf(working, "details").map((section) => section.name)).toEqual(["main"]);
		expect(columnsOf(working, "main")[1].fields).toEqual(["due", "notes"]);
	});

	it("gives the first section's fields to the section after it", () => {
		const working = replay(canvas("remove_section", { section: "main" }));
		expect(columnsOf(working, "more")[0].fields).toEqual(["notes", "subject", "status", "due"]);
	});

	it("drops the fields of a tab's only section off the layout", () => {
		const working = replay(
			canvas("place_field", { fieldname: "spare", column: "column_1", section: "log" }),
			canvas("remove_section", { section: "log" }),
		);
		expect(sectionsOf(working, "activity")).toEqual([]);
		expect(JSON.stringify(working.layout)).not.toContain("spare");
	});

	it("moves a section into another tab", () => {
		const working = replay(canvas("move_section", { section: "more", tab: "activity", index: 0 }));
		expect(sectionsOf(working, "activity").map((section) => section.name)).toEqual(["more", "log"]);
		expect(sectionsOf(working, "details").map((section) => section.name)).toEqual(["main"]);
	});
});

describe("canvas columns", () => {
	it("adds a column named within its section", () => {
		const working = replay(canvas("add_column", { section: "main" }));
		expect(columnsOf(working, "main").map((column) => column.name)).toEqual(["column_1", "column_2", "column_3"]);
	});

	it("removes a column and gives its fields to the column before", () => {
		const working = replay(canvas("remove_column", { column: "column_2", section: "main" }));
		expect(columnsOf(working, "main")).toEqual([{ name: "column_1", fields: ["subject", "status", "due"] }]);
	});

	it("needs the section of a column whose name repeats", () => {
		expect(() => workingState(base, [canvas("remove_column", { column: "column_1" })])).toThrow(
			"Name the section of column column_1.",
		);
	});

	it("moves a column into another section", () => {
		const working = replay(
			canvas("move_column", { column: "column_2", section: "main", to_section: "log", index: 0 }),
		);
		expect(columnsOf(working, "log").map((column) => column.name)).toEqual(["column_2", "column_1"]);
		expect(columnsOf(working, "main").map((column) => column.name)).toEqual(["column_1"]);
	});
});

describe("canvas fields", () => {
	it("places a field in a column at an index", () => {
		const working = replay(canvas("place_field", { fieldname: "spare", column: "column_1", section: "main", index: 1 }));
		expect(columnsOf(working, "main")[0].fields).toEqual(["subject", "spare", "status"]);
	});

	it("places a field on a tab at the end of its first section's last column", () => {
		const working = replay(canvas("place_field", { fieldname: "spare", tab: "details" }));
		expect(columnsOf(working, "main")[1].fields).toEqual(["due", "spare"]);
	});

	it("adds a section to an empty tab a field is placed on", () => {
		const working = replay(
			canvas("add_tab", { label: "Extra" }),
			canvas("place_field", { fieldname: "spare", tab: "extra" }),
		);
		expect(sectionsOf(working, "extra")).toEqual([{ name: "section_4", columns: [{ name: "column_1", fields: ["spare"] }] }]);
	});

	it("moves a field, taking it from where it was", () => {
		const working = replay(canvas("move_field", { fieldname: "subject", column: "column_1", section: "log" }));
		expect(columnsOf(working, "main")[0].fields).toEqual(["status"]);
		expect(columnsOf(working, "log")[0].fields).toEqual(["subject"]);
	});

	it("unplaces a field", () => {
		const working = replay(canvas("unplace_field", { fieldname: "status" }));
		expect(columnsOf(working, "main")[0].fields).toEqual(["subject"]);
	});

	it("refuses a field the DocType does not have", () => {
		expect(() => workingState(base, [canvas("unplace_field", { fieldname: "ghost" })])).toThrow(
			"ghost is not a field of Task Note.",
		);
	});
});

describe("canvas container properties", () => {
	it("sets a section's property and drops a falsy one", () => {
		const set = replay(canvas("set_container_property", { container: "main", property: "collapsible", value: 1 }));
		expect(sectionsOf(set, "details")[0].collapsible).toBe(1);
		const cleared = replay(canvas("set_container_property", { container: "more", property: "label", value: "" }));
		expect(sectionsOf(cleared, "details")[1]).not.toHaveProperty("label");
	});

	it("sets a column's property by its section", () => {
		const working = replay(
			canvas("set_container_property", { container: "column_2", section: "main", property: "label", value: "Dates" }),
		);
		expect(columnsOf(working, "main")[1].label).toBe("Dates");
	});

	it("refuses a key that is not a container property", () => {
		expect(() =>
			workingState(base, [canvas("set_container_property", { container: "main", property: "fields", value: [] })]),
		).toThrow("fields is not a container property.");
	});
});

const fieldnames = (working: WorkingState) => working.fields.map((field) => field.fieldname);
const placed = (working: WorkingState) => JSON.stringify(working.layout);

describe("field acts", () => {
	it("adds a field named from its label and places it", () => {
		const working = replay({
			act: "fields.add_field",
			label: "Due Date",
			fieldtype: "Date",
			properties: { reqd: 1 },
			layout: DETAILS,
			column: "column_1",
			section: "log",
		});
		expect(working.fields.at(-1)).toEqual({ fieldname: "due_date", label: "Due Date", fieldtype: "Date", reqd: 1 });
		expect(columnsOf(working, "log")[0].fields).toEqual(["due_date"]);
	});

	it("adds a field off the layout when the edit names no layout", () => {
		const working = replay({ act: "fields.add_field", label: "Kind", fieldtype: "Link", options: "DocType", fieldname: "kind" });
		expect(working.fields.at(-1)).toEqual({ fieldname: "kind", label: "Kind", fieldtype: "Link", options: "DocType" });
		expect(placed(working)).not.toContain("kind");
	});

	it("refuses a taken or invalid fieldname", () => {
		expect(() => workingState(base, [{ act: "fields.add_field", label: "Subject", fieldtype: "Data" }])).toThrow(
			"Task Note already has a field subject.",
		);
		expect(() =>
			workingState(base, [{ act: "fields.add_field", label: "X", fieldtype: "Data", fieldname: "Big" }]),
		).toThrow("Big is not a valid fieldname.");
	});

	it("sets a field property, but not its fieldname", () => {
		const working = replay({ act: "fields.set_field_property", fieldname: "status", property: "fieldtype", value: "Data" });
		expect(working.fields[1].fieldtype).toBe("Data");
		expect(() =>
			workingState(base, [{ act: "fields.set_field_property", fieldname: "status", property: "fieldname", value: "x" }]),
		).toThrow("Rename the field to change its fieldname.");
	});

	it("renames a field added in this session everywhere the layout places it", () => {
		const working = replay(
			{ act: "fields.add_field", label: "Ref", fieldtype: "Data", layout: DETAILS, tab: "activity" },
			{ act: "fields.rename_field", fieldname: "ref", new_fieldname: "reference" },
		);
		expect(fieldnames(working).at(-1)).toBe("reference");
		expect(columnsOf(working, "log")[0].fields).toEqual(["reference"]);
	});

	it("renames a saved field of a custom DocType and remembers its saved name", () => {
		const working = replay({ act: "fields.rename_field", fieldname: "due", new_fieldname: "due_on" });
		expect(columnsOf(working, "main")[1].fields).toEqual(["due_on"]);
		expect(working.renames).toEqual([["due", "due_on"]]);
		const back = workingState(working, [{ act: "fields.rename_field", fieldname: "due_on", new_fieldname: "due" }]);
		expect(back.renames).toEqual([]);
	});

	it("refuses to rename a saved field of a standard DocType", () => {
		const standard = editorBase({ ...state(), custom: 0 });
		expect(() =>
			workingState(standard, [{ act: "fields.rename_field", fieldname: "due", new_fieldname: "due_on" }]),
		).toThrow("Renaming a saved field of a standard DocType needs a patch.");
	});

	it("deletes a field and takes it off the layout", () => {
		const working = replay({ act: "fields.delete_field", fieldname: "status" });
		expect(fieldnames(working)).toEqual(["subject", "due", "notes", "spare"]);
		expect(columnsOf(working, "main")[0].fields).toEqual(["subject"]);
	});

	it("leaves the Details canvas alone for an edit to another layout", () => {
		const working = replay(
			{ act: "canvas.unplace_field", layout: { type: "Details", id: "Wide" }, fieldname: "status" },
			{ act: "fields.set_field_property", fieldname: "status", property: "reqd", value: 1 },
		);
		expect(columnsOf(working, "main")[0].fields).toEqual(["subject", "status"]);
	});
});

describe("settings acts", () => {
	it("sets the DocType's description", () => {
		const working = replay({ act: "settings.set_doctype_property", property: "description", value: "Task notes" });
		expect(working.description).toBe("Task notes");
	});

	it("refuses an act it does not know", () => {
		expect(() => workingState(base, [{ act: "danger.delete" }])).toThrow("danger.delete is not a Design edit.");
	});
});

describe("fieldsOffLayout", () => {
	it("lists the fields the layout does not place, marking new and asked ones", () => {
		const working = workingState(base, [
			{ act: "fields.add_field", label: "Ref", fieldtype: "Data" },
			{ act: "fields.add_field", label: "Break", fieldtype: "Section Break" },
			{ act: "fields.rename_field", fieldname: "spare", new_fieldname: "extra" },
		]);
		expect(
			fieldsOffLayout(working, ["ref"]).map(({ field, ...marks }) => ({ fieldname: field.fieldname, ...marks })),
		).toEqual([
			{ fieldname: "extra", new: false, asked: false },
			{ fieldname: "ref", new: true, asked: true },
		]);
	});
});

describe("reqdInConditional", () => {
	it("names each mandatory field a tab, section or column condition can hide", () => {
		const working = workingState(base, [
			{ act: "fields.set_field_property", fieldname: "notes", property: "reqd", value: 1 },
			{ act: "fields.set_field_property", fieldname: "subject", property: "reqd", value: 1 },
			canvas("set_container_property", { container: "more", property: "dependsOn", value: "eval:doc.status" }),
		]);
		expect(reqdInConditional(working)).toEqual([{ fieldname: "notes", container: "more" }]);
	});
});

describe("workingState", () => {
	it("never changes the base", () => {
		const before = JSON.stringify(base);
		workingState(base, [canvas("remove_tab", { tab: "activity" }), canvas("unplace_field", { fieldname: "due" })]);
		expect(JSON.stringify(base)).toBe(before);
	});
});
