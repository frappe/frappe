import { describe, expect, it } from "vitest";
import { editorBase, workingState, type FlatEdit } from "../editorModel";
import { addLayoutRefusal, layoutMenu } from "../layoutMenu";
import { layoutFromQuery, layoutQuery } from "../layoutQuery";
import type { LayoutRef } from "../workingLayouts";
import { taskNote } from "./editorFixture";
import { leadNote } from "./layoutsFixture";

const DETAILS = { type: "Details" } as const;
const DONE = { type: "Details", id: "app:1" } as const;

function menu(state = leadNote(), edits: FlatEdit[] = [], open: LayoutRef = DETAILS) {
	return layoutMenu(workingState(editorBase(state), edits), open);
}

const rows = (built: ReturnType<typeof layoutMenu>) =>
	built.types.map((type) => [type.label, type.badge, ...type.layouts.map((layout) => `${layout.name}: ${layout.badge}`)]);

describe("the layout menu", () => {
	it("lists each type with its source, and its conditional layouts under it", () => {
		expect(rows(menu())).toEqual([
			["Details", "App layout", "Done: App layout"],
			["Side panel", "Not set up"],
			["Quick entry", "From DocType fields"],
			["New record", "Same as Details"],
		]);
	});

	it("shows Customize the site rows, and names an untitled layout by its condition", () => {
		const customize = leadNote({ mode: "Customize" });
		customize.layouts.Details!.unshift({ name: "FL-2", source: "site", condition: "doc.x", omitted: [], layout: [] });
		expect(rows(menu(customize))[0]).toEqual(["Details", "Site layout", "doc.x: Site layout"]);
	});

	it("gives a child table Details only, with a note, and a Single Details and Side panel", () => {
		const child = menu(taskNote({ definition: { ...taskNote().definition, istable: 1 } }));
		expect(rows(child)).toEqual([["Details", "From DocType fields"]]);
		expect(child.note).toBe("A child table's rows use Details only");
		const single = menu(taskNote({ definition: { ...taskNote().definition, issingle: 1 } }));
		expect(rows(single)).toEqual([
			["Details", "From DocType fields"],
			["Side panel", "Not set up"],
		]);
		expect(single.note).toBeNull();
	});

	it("reads a staged edit: Design makes an app layout on a standard DocType, a site layout on a custom one", () => {
		const place: FlatEdit = { act: "canvas.add_tab", layout: { type: "Quick Entry" }, name: "more" };
		expect(rows(menu(leadNote(), [place]))[2]).toEqual(["Quick entry", "App layout"]);
		expect(rows(menu(taskNote(), [{ ...place, layout: DETAILS }]))[0]).toEqual(["Details", "Site layout"]);
	});

	it("reads a staged Customize edit as a site layout", () => {
		const customize = leadNote({ mode: "Customize" });
		const edit: FlatEdit = { act: "canvas.add_tab", layout: { type: "New Record" }, name: "more" };
		expect(rows(menu(customize, [edit]))[3]).toEqual(["New record", "Site layout"]);
	});

	it("marks the open layout and ends with its acts and where it shows", () => {
		const built = menu(leadNote(), [], DONE);
		expect(built.types[0].open).toBe(false);
		expect(built.types[0].layouts[0].open).toBe(true);
		expect(built.open).toEqual({
			name: "Done",
			where: "Shows in the record page's main column when doc.status == 'Done'",
			acts: ["edit_condition", "rename", "delete"],
		});
	});

	it("gives a default layout no acts, except a reset for a Customize site layout", () => {
		expect(menu().open).toBeNull();
		expect(menu().types[0].open).toBe(true);
		expect(menu(leadNote({ mode: "Customize" })).open).toEqual({
			name: "Details",
			where: "Shows in the record page's main column",
			acts: ["reset_to_app"],
		});
	});
});

describe("Add a layout", () => {
	const working = workingState(editorBase(leadNote()), []);

	it("asks for a condition or an edit of the default, which every type has, if only a stand-in", () => {
		expect(addLayoutRefusal(working, { type: "Details", title: "Wide" })).toBe(
			"Details has one default layout: edit that one, or give this one a condition.",
		);
		expect(addLayoutRefusal(working, { type: "Side Panel" })).toBe(
			"Side panel has one default layout: edit that one, or give this one a condition.",
		);
		expect(addLayoutRefusal(working, { type: "Details", title: "Wide", condition: "doc.wide" })).toBeNull();
		expect(addLayoutRefusal(working, { type: "Side Panel", condition: "doc.wide" })).toBeNull();
	});

	it("allows only the types the DocType has", () => {
		const child = editorBase(taskNote({ definition: { ...taskNote().definition, istable: 1 } }));
		expect(addLayoutRefusal(child, { type: "Quick Entry", condition: "doc.x" })).toBe(
			"Task Note is a child table, so it has only a Details layout.",
		);
	});
});

describe("the layout in the address", () => {
	it("maps ?layout= and ?row= to a layout and back", () => {
		expect(layoutFromQuery({})).toEqual(DETAILS);
		expect(layoutFromQuery({ layout: "quick-entry" })).toEqual({ type: "Quick Entry" });
		expect(layoutFromQuery({ layout: "details", row: "app:1" })).toEqual(DONE);
		expect(layoutFromQuery({ layout: "elsewhere" })).toEqual(DETAILS);
		expect(layoutQuery({ type: "Side Panel" })).toEqual({ layout: "side-panel" });
		expect(layoutQuery({ type: "New Record", id: "FL-3" })).toEqual({ layout: "new-record", row: "FL-3" });
		expect(layoutFromQuery(layoutQuery(DONE))).toEqual(DONE);
	});
});
