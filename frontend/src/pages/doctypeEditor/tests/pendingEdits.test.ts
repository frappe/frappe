import { describe, expect, it } from "vitest";
import { PendingEdits, type EditorTab } from "../pendingEdits";

const VERSION = { doctype: "2026-11-13 10:00:00", layouts: {}, app_layouts: {} };

function pending() {
	const opened: EditorTab[] = [];
	const edits = new PendingEdits(
		{ doctype: "Note", mode: "Design", base_version: VERSION },
		(tab) => opened.push(tab),
	);
	return { edits, opened };
}

describe("PendingEdits", () => {
	it("keeps one stack across the Editor and Settings tabs", () => {
		const { edits } = pending();
		edits.stage({ act: "canvas.add_tab", value: {}, tab: "editor" });
		edits.stage({ act: "settings.set_property", value: { property: "track_changes" }, tab: "settings" });
		expect(edits.payload()).toEqual({
			doctype: "Note",
			mode: "Design",
			base_version: VERSION,
			edits: [{ act: "canvas.add_tab" }, { act: "settings.set_property", property: "track_changes" }],
		});
	});

	it("undoes the last edit from either tab and opens the tab of the change", () => {
		const { edits, opened } = pending();
		edits.stage({ act: "canvas.add_tab", value: {}, tab: "editor" });
		edits.stage({ act: "settings.set_property", value: {}, tab: "settings" });
		edits.undo();
		edits.undo();
		expect(opened).toEqual(["settings", "editor"]);
		expect(edits.payload().edits).toEqual([]);
		expect(edits.canUndo.value).toBe(false);
	});

	it("redoes in order and a new edit clears the redo stack", () => {
		const { edits, opened } = pending();
		edits.stage({ act: "canvas.add_tab", value: { label: "One" }, tab: "editor" });
		edits.undo();
		edits.redo();
		expect(opened).toEqual(["editor", "editor"]);
		expect(edits.payload().edits.map((edit) => edit.label)).toEqual(["One"]);
		edits.undo();
		edits.stage({ act: "settings.set_property", value: {}, tab: "settings" });
		expect(edits.canRedo.value).toBe(false);
		expect(edits.dirty.value).toBe(true);
	});

	it("stages several edits as one undo step", () => {
		const { edits } = pending();
		edits.stage({ act: "canvas.add_tab", value: { label: "One" }, tab: "editor" });
		edits.stage(
			{ act: "fields.set_field_property", value: { fieldname: "ref", property: "label", value: "Code" }, tab: "editor" },
			{ act: "fields.rename_field", value: { fieldname: "ref", new_fieldname: "code" }, tab: "editor" },
		);
		expect(edits.staged.value.map((edit) => edit.act)).toEqual([
			"canvas.add_tab",
			"fields.set_field_property",
			"fields.rename_field",
		]);
		edits.undo();
		expect(edits.payload().edits).toEqual([{ act: "canvas.add_tab", label: "One" }]);
		edits.redo();
		expect(edits.payload().edits).toHaveLength(3);
	});
});
