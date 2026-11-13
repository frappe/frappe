import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toast, runMethod } = vi.hoisted(() => ({
	toast: { error: vi.fn(), success: vi.fn() },
	runMethod: vi.fn(),
}));
vi.mock("frappe-ui", () => ({ toast }));
vi.mock("@framework/ui/api", () => ({ runMethod }));

import { acts } from "@/acts/dispatcher";
import { CREATE_METHOD, SAVE_METHOD } from "../editorSave";
import type { EditorState } from "../editorSource";
import { mountEditor, taskNote, VERSION } from "./editorFixture";

const LINE_VERSION = { doctype: "2026-11-12 09:00:00", layouts: {}, app_layouts: {} };
const LOAD = "frappe.desk.doctype_editor.load.get_doctype_editor";

function parent(overrides: Partial<EditorState> = {}): EditorState {
	const state = taskNote(overrides);
	state.definition.fields.push({ fieldname: "lines", label: "Lines", fieldtype: "Table", options: "Task Note Line" });
	return state;
}

function line(): EditorState {
	return taskNote({
		doctype: "Task Note Line",
		base_version: LINE_VERSION,
		layouts: {},
		definition: { name: "Task Note Line", istable: 1, fields: [{ fieldname: "qty", label: "Qty", fieldtype: "Float" }] },
	});
}

let stop: () => void;
beforeEach(() => {
	runMethod.mockReset();
	toast.success.mockReset();
});
afterEach(() => stop());

function mount(initial: EditorState = parent()) {
	const mounted = mountEditor(initial);
	stop = mounted.stop;
	return mounted;
}

function answers(...results: unknown[]) {
	for (const data of results) runMethod.mockResolvedValueOnce({ data });
}

const saved = { saved: true, base_version: VERSION, children: [] };
const bold = (fieldname: string) => ({ fieldname, property: "bold", value: 1 });

describe("a save with child tables", () => {
	it("saves an edited child in its own call before the parent's", async () => {
		const { children } = mount();
		answers(line());
		await children.show("lines");
		expect(runMethod).toHaveBeenLastCalledWith(LOAD, { doctype: "Task Note Line", mode: "Design" }, { http: "GET" });
		await acts.run("fields.set_field_property", bold("qty"));
		await children.show(null);
		await acts.run("fields.set_field_property", bold("subject"));
		answers(saved, saved);
		await acts.run("editor.save");
		expect(runMethod.mock.calls.slice(1)).toEqual([
			[
				SAVE_METHOD,
				{
					doctype: "Task Note Line",
					mode: "Design",
					base_version: LINE_VERSION,
					edits: [{ act: "fields.set_field_property", ...bold("qty") }],
				},
			],
			[
				SAVE_METHOD,
				{
					doctype: "Task Note",
					mode: "Design",
					base_version: VERSION,
					edits: [{ act: "fields.set_field_property", ...bold("subject") }],
				},
			],
		]);
	});

	it("sends a new child's edits inside the parent's call, keyed by DocType", async () => {
		const { children } = mount();
		await acts.run("fields.add_field", { label: "Steps", fieldtype: "Table" });
		await acts.run("fields.add_child_table", { name: "Task Note Step", table_field: "steps" });
		await children.show("steps");
		expect(children.open.value?.state).toMatchObject({ doctype: "Task Note Step", pending: true });
		await acts.run("fields.add_field", { label: "Done", fieldtype: "Check", section: "main", column: "column" });
		expect(children.open.value?.canvas.place("done")).toMatchObject({ section: "main", index: 0 });
		answers(saved);
		await acts.run("editor.save");
		expect(runMethod).toHaveBeenCalledOnce();
		expect(runMethod.mock.calls[0][1].edits).toEqual({
			"Task Note": [
				{ act: "fields.add_field", label: "Steps", fieldtype: "Table" },
				{ act: "fields.add_child_table", name: "Task Note Step", table_field: "steps" },
			],
			"Task Note Step": [{ act: "fields.add_field", label: "Done", fieldtype: "Check" }],
		});
	});

	it("nests a new child's edits in a new parent's first save too", async () => {
		const { children } = mount(parent({ pending: true }));
		await acts.run("fields.add_child_table", { name: "Task Note Step", table_field: "steps", label: "Steps" });
		await children.show("steps");
		await acts.run("fields.add_field", { label: "Done", fieldtype: "Check" });
		answers({ ...saved, doctype: "Task Note" });
		await acts.run("editor.save");
		const [method, args] = runMethod.mock.calls[0];
		expect(method).toBe(CREATE_METHOD);
		expect(Object.keys(args.edits)).toEqual(["Task Note", "Task Note Step"]);
	});

	it("stops at a refused child and marks its errors in the child's editor", async () => {
		const { children } = mount();
		answers(line());
		await children.show("lines");
		await acts.run("fields.set_field_property", bold("qty"));
		await children.show(null);
		await acts.run("fields.set_field_property", bold("subject"));
		answers({ saved: false, errors: [{ target: { kind: "field", fieldname: "qty" }, message: "No." }] });
		await acts.run("editor.save");
		expect(runMethod).toHaveBeenCalledTimes(2);
		expect(children.open.value?.state.doctype).toBe("Task Note Line");
		expect(children.open.value?.canvas.errorsAt("field", "qty")).toEqual(["No."]);
	});

	it("refuses to lay out a new child before its first save", async () => {
		const { children } = mount();
		await acts.run("fields.add_child_table", { name: "Task Note Step", table_field: "steps" });
		await children.show("steps");
		expect(() => children.open.value!.canvas.stage({ act: "canvas.add_section", layout: { type: "Details" }, tab: "details" })).toThrow(
			"before you lay it out",
		);
	});

	it("reopens the child an undo steps back into", async () => {
		const { children, edits } = mount();
		answers(line());
		await children.show("lines");
		await acts.run("fields.set_field_property", bold("qty"));
		await children.show(null);
		edits.undo();
		await Promise.resolve();
		expect(children.open.value?.state.doctype).toBe("Task Note Line");
	});
});
