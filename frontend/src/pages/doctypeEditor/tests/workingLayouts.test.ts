import { describe, expect, it } from "vitest";
import { editorBase, workingState, type FlatEdit } from "../editorModel";
import { emptyTabs, layoutOf, tabsOf } from "../workingLayouts";
import { leadNote, tabs } from "./layoutsFixture";
import { taskNote } from "./editorFixture";

const design = editorBase(leadNote());
const customize = editorBase(leadNote({ mode: "Customize" }));
const DETAILS = { type: "Details" } as const;
const DONE = { type: "Details", id: "app:1" } as const;

const ids = (working: ReturnType<typeof editorBase>, type: keyof typeof working.layouts) =>
	working.layouts[type]!.layouts.map((layout) => [layout.id ?? null, layout.source]);

describe("the layouts a load gives", () => {
	it("Design on a standard DocType keeps the app's entries, named by their index", () => {
		expect(ids(design, "Details")).toEqual([
			["app:0", "app"],
			["app:1", "app"],
		]);
		expect(layoutOf(design, DONE)).toMatchObject({ title: "Done", condition: "doc.status == 'Done'" });
	});

	it("Customize keeps the site rows, named by the row", () => {
		expect(ids(customize, "Details")).toEqual([["FL-1", "site"]]);
		expect(tabsOf(customize, DETAILS)).toEqual(tabs("subject"));
	});

	it("an empty entry is the type's default, with no id", () => {
		expect(layoutOf(design, { type: "Side Panel" })).toMatchObject({ source: "none", tabs: emptyTabs() });
		expect(layoutOf(design, { type: "Quick Entry" })).toMatchObject({ source: "fallback" });
		expect(layoutOf(design, { type: "New Record" })).toMatchObject({ source: "same as Details" });
		expect(tabsOf(design, { type: "New Record" })).toEqual(tabs("subject", "status"));
		expect(ids(design, "Side Panel")).toEqual([]);
	});

	it("an app file with only conditional Details layouts gets a default drawn from the fields, as the record draws it", () => {
		const fields = [
			{ fieldname: "subject", label: "Subject", fieldtype: "Small Text" },
			{ fieldname: "more", label: "More", fieldtype: "Section Break", depends_on: "eval:doc.status" },
			{ fieldname: "status", label: "Status", fieldtype: "Select" },
			{ fieldname: "side", fieldtype: "Column Break" },
			{ fieldname: "notes", label: "Notes", fieldtype: "Text" },
		];
		const done = { name: null, source: "app" as const, title: "Done", condition: "doc.done", omitted: [], layout: tabs("subject") };
		const lead = leadNote();
		const working = editorBase(
			leadNote({
				layouts: { ...lead.layouts, Details: [done] },
				definition: { ...lead.definition, fields } as never,
			}),
		);
		const drawn = [
			{
				name: "first_tab",
				sections: [
					{ name: "section_1", columns: [{ name: "column_1", fields: ["subject"] }] },
					{
						name: "more",
						label: "More",
						dependsOn: "eval:doc.status",
						columns: [
							{ name: "column_1", fields: ["status"] },
							{ name: "side", fields: ["notes"] },
						],
					},
				],
			},
		];
		expect(layoutOf(working, DETAILS)).toMatchObject({ source: "fallback", tabs: drawn });
		expect(tabsOf(working, { type: "New Record" })).toEqual(drawn);
	});

	it("a child table has Details only, a Single Details and Side Panel", () => {
		const child = editorBase(taskNote({ definition: { ...taskNote().definition, istable: 1 } }));
		const single = editorBase(taskNote({ definition: { ...taskNote().definition, issingle: 1 } }));
		expect(Object.keys(child.layouts)).toEqual(["Details"]);
		expect(Object.keys(single.layouts)).toEqual(["Details", "Side Panel"]);
	});
});

describe("canvas edits on any layout", () => {
	const place = (layout: object, fieldname: string): FlatEdit => ({
		act: "canvas.place_field",
		layout,
		fieldname,
		section: "main",
		column: "column_1",
	});

	it("go to the layout the ref names, leaving the others alone", () => {
		const working = workingState(design, [place(DONE, "notes")]);
		expect(tabsOf(working, DONE)).toEqual(tabs("subject", "notes"));
		expect(tabsOf(working, DETAILS)).toEqual(tabs("subject", "status"));
	});

	it("refuse a layout that does not exist, and a type the DocType does not have", () => {
		expect(() => workingState(design, [place({ type: "Details", id: "Wide" }, "notes")])).toThrow(
			"This Details layout no longer exists.",
		);
		const child = editorBase(taskNote({ definition: { ...taskNote().definition, istable: 1 } }));
		expect(() => workingState(child, [place({ type: "Side Panel" }, "notes")])).toThrow(
			"Task Note is a child table, so it has only a Details layout.",
		);
	});

	it("make a missing default from the fallback: Quick Entry from its fields, New Record from Details", () => {
		const working = workingState(design, [
			{ act: "canvas.unplace_field", layout: DETAILS, fieldname: "status" },
			place({ type: "New Record" }, "notes"),
			{ act: "canvas.add_tab", layout: { type: "Quick Entry" }, name: "more" },
		]);
		expect(tabsOf(working, { type: "New Record" })).toEqual(tabs("subject", "notes"));
		expect(tabsOf(working, DETAILS)).toEqual(tabs("subject"));
		expect(layoutOf(working, { type: "New Record" })).toMatchObject({ source: "app" });
		const quick = tabsOf(working, { type: "Quick Entry" });
		expect(quick.map((tab) => tab.name)).toEqual(["first_tab", "more"]);
		expect(quick[0].sections[0]).toMatchObject({ name: "section_1", hideBorder: true });
		expect(quick[0].sections[0].columns[0].fields).toEqual(["notes", "spare"]);
	});

	it("make one empty tab for a Quick Entry with no fields to ask", () => {
		const fields = taskNote().definition.fields.map((field) => ({ ...field, reqd: 0 as const }));
		const plain = editorBase(taskNote({ definition: { ...taskNote().definition, fields } }));
		expect(tabsOf(plain, { type: "Quick Entry" })).toEqual(emptyTabs());
	});

	it("make a Side Panel of one section with a header to place the first field on", () => {
		const working = workingState(design, [
			{ ...place({ type: "Side Panel" }, "notes"), section: "section_1" },
		]);
		expect(tabsOf(working, { type: "Side Panel" })).toEqual([
			{
				name: "first_tab",
				sections: [{ name: "section_1", label: "Details", columns: [{ name: "column_1", fields: ["notes"] }] }],
			},
		]);
	});

	it("place a new field on the layout its add names", () => {
		const working = workingState(design, [
			{ act: "fields.add_field", label: "Ref", fieldtype: "Data", layout: DONE, section: "main", column: "column_1" },
		]);
		expect(tabsOf(working, DONE)).toEqual(tabs("subject", "ref"));
		expect(tabsOf(working, DETAILS)).toEqual(tabs("subject", "status"));
	});

	it("rename and delete a field on every layout", () => {
		const custom = editorBase(leadNote({ custom: 1, mode: "Design" }));
		const working = workingState(custom, [
			{ act: "fields.rename_field", fieldname: "subject", new_fieldname: "topic" },
			{ act: "fields.delete_field", fieldname: "status" },
		]);
		expect(tabsOf(working, DETAILS)).toEqual(tabs("topic"));
		expect(tabsOf(working, { type: "New Record" })).toEqual(tabs("topic"));
	});
});

describe("layouts acts", () => {
	const add = (keys: Record<string, unknown>): FlatEdit => ({ act: "layouts.add", type: "Details", id: "new-1", ...keys });
	const WIDE = { type: "Details", id: "new-1" } as const;

	it("add a layout from a copy of the type's default, or from one empty tab", () => {
		const copied = workingState(design, [add({ title: "Wide", condition: "doc.wide", start: "copy" })]);
		expect(layoutOf(copied, WIDE)).toMatchObject({ title: "Wide", condition: "doc.wide", source: "app" });
		expect(tabsOf(copied, WIDE)).toEqual(tabs("subject", "status"));
		const empty = workingState(design, [add({ condition: "doc.wide", start: "empty" })]);
		expect(tabsOf(empty, WIDE)).toEqual(emptyTabs());
	});

	it("refuse a second default, a taken id and a type the DocType does not have", () => {
		expect(() => workingState(design, [add({ title: "Wide" })])).toThrow(
			"Only one Details layout can have no condition.",
		);
		expect(() => workingState(design, [add({ id: "app:1", condition: "doc.wide" })])).toThrow(
			"A new layout needs an id of its own.",
		);
		const single = editorBase(taskNote({ definition: { ...taskNote().definition, issingle: 1 } }));
		expect(() => workingState(single, [add({ type: "Quick Entry", condition: "doc.x" })])).toThrow(
			"Task Note is a Single, which is never created, so it has no Quick Entry layout.",
		);
	});

	it("give a type with no default one, from a layout with no condition", () => {
		const working = workingState(design, [add({ type: "Side Panel", start: "empty" })]);
		expect(layoutOf(working, { type: "Side Panel" })).toMatchObject({ id: "new-1", source: "app" });
	});

	it("rename a layout and change its condition, but never to a second default", () => {
		const working = workingState(design, [
			{ act: "layouts.rename", layout: DONE, title: "Finished" },
			{ act: "layouts.set_condition", layout: DONE, condition: "doc.done" },
		]);
		expect(layoutOf(working, DONE)).toMatchObject({ title: "Finished", condition: "doc.done" });
		expect(() =>
			workingState(design, [{ act: "layouts.set_condition", layout: DONE, condition: "" }]),
		).toThrow("Only one Details layout can have no condition.");
		const moved = workingState(design, [
			{ act: "layouts.set_condition", layout: { type: "Details", id: "app:0" }, condition: "doc.old" },
			{ act: "layouts.set_condition", layout: DONE, condition: null },
		]);
		expect(layoutOf(moved, DETAILS)).toMatchObject({ id: "app:1", title: "Done" });
	});

	it("delete a conditional layout, never the default, and refuse one that is gone", () => {
		const working = workingState(design, [{ act: "layouts.delete", layout: DONE }]);
		expect(layoutOf(working, DONE)).toBeNull();
		expect(() => workingState(design, [{ act: "layouts.delete", layout: DETAILS }])).toThrow(
			"The default Details layout cannot be deleted.",
		);
		expect(() =>
			workingState(working, [{ act: "layouts.rename", layout: DONE, title: "Again" }]),
		).toThrow("This Details layout no longer exists.");
	});

	it("Customize forks a type it touches, and a reset gives back the app's entries", () => {
		const unforked = editorBase(leadNote({ mode: "Customize", layouts: { ...leadNote().layouts, Details: leadNote().layouts.Details!.slice(1) } }));
		expect(ids(unforked, "Details")).toEqual([
			["app:0", "app"],
			["app:1", "app"],
		]);
		const forked = workingState(unforked, [{ act: "layouts.rename", layout: DONE, title: "Finished" }]);
		expect(ids(forked, "Details")).toEqual([
			["app:0", "site"],
			["app:1", "site"],
		]);
		const reset = workingState(customize, [
			{ act: "canvas.unplace_field", layout: DETAILS, fieldname: "subject" },
			{ act: "layouts.reset_to_app", type: "Details" },
		]);
		expect(ids(reset, "Details")).toEqual([
			["app:0", "app"],
			["app:1", "app"],
		]);
		expect(reset.layouts.Details!.touched).toBe(false);
	});

	it("a reset after a canvas edit on an unforked type gives back the app's own tree", () => {
		const unforked = editorBase(leadNote({ mode: "Customize", layouts: { ...leadNote().layouts, Details: leadNote().layouts.Details!.slice(1) } }));
		const reset = workingState(unforked, [
			{ act: "canvas.unplace_field", layout: DETAILS, fieldname: "status" },
			{ act: "layouts.reset_to_app", type: "Details" },
		]);
		expect(tabsOf(reset, DETAILS)).toEqual(tabs("subject", "status"));
	});

	it("reset to the app layout only in Customize", () => {
		expect(() => workingState(design, [{ act: "layouts.reset_to_app", type: "Details" }])).toThrow(
			"layouts.reset_to_app is not a Design edit.",
		);
	});
});
