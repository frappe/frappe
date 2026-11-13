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
			edits: [
				{ act: "canvas.add_tab", value: {}, tab: "editor" },
				{ act: "settings.set_property", value: { property: "track_changes" }, tab: "settings" },
			],
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
		edits.stage({ act: "canvas.add_tab", value: 1, tab: "editor" });
		edits.undo();
		edits.redo();
		expect(opened).toEqual(["editor", "editor"]);
		expect(edits.payload().edits.map((edit) => edit.value)).toEqual([1]);
		edits.undo();
		edits.stage({ act: "settings.set_property", value: 2, tab: "settings" });
		expect(edits.canRedo.value).toBe(false);
		expect(edits.dirty.value).toBe(true);
	});
});
