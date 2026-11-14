import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toast, runMethod } = vi.hoisted(() => ({
	toast: { error: vi.fn(), success: vi.fn() },
	runMethod: vi.fn(),
}));
vi.mock("frappe-ui", () => ({ toast }));
vi.mock("@framework/ui/api", () => ({ runMethod }));

import { acts } from "@/acts/dispatcher";
import { CREATE_METHOD, SAVE_METHOD, WRITE_FILES_METHOD } from "../editorSave";
import type { EditorState } from "../editorSource";
import { settingRows } from "../settingsRows";
import { mountEditor, taskNote, VERSION } from "./editorFixture";

const LINE_VERSION = { doctype: "2026-11-12 09:00:00", layouts: {}, app_layouts: {} };
const LOAD = "frappe.desk.doctype_editor.load.get_doctype_editor";

function parent(overrides: Partial<EditorState> = {}): EditorState {
	const state = taskNote(overrides);
	state.definition.fields.push({ fieldname: "lines", label: "Lines", fieldtype: "Table", options: "Task Note Line" });
	return state;
}

function line(doctype = "Task Note Line", base_version = LINE_VERSION): EditorState {
	return taskNote({
		doctype,
		base_version,
		layouts: {},
		definition: { name: doctype, istable: 1, fields: [{ fieldname: "qty", label: "Qty", fieldtype: "Float" }] },
	});
}

let stop: () => void;
beforeEach(() => {
	runMethod.mockReset();
	toast.success.mockReset();
});

/** Edits the saved child "Task Note Line", then the parent, back on the parent's editor. */
async function editChildAndParent(children: ReturnType<typeof mount>["children"]) {
	answers(line());
	await children.show("lines");
	await acts.run("fields.set_field_property", bold("qty"));
	await children.show(null);
	await acts.run("fields.set_field_property", bold("subject"));
}
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

	it("saves a child's grid setting from its Settings tab in the child's own call", async () => {
		const { children } = mount();
		answers(line());
		await children.show("lines");
		await acts.run("settings.set_doctype_property", { property: "editable_grid", value: 0 });
		expect(children.open.value?.canvas.working.value.settings.properties.editable_grid).toBe(0);
		await children.show(null);
		answers(saved);
		await acts.run("editor.save");
		expect(runMethod.mock.calls.at(-1)).toEqual([
			SAVE_METHOD,
			{
				doctype: "Task Note Line",
				mode: "Design",
				base_version: LINE_VERSION,
				edits: [{ act: "settings.set_doctype_property", property: "editable_grid", value: 0 }],
			},
		]);
	});

	it("undoes a child's grid setting on the shared stack, and reopens the child to do it", async () => {
		const { children, edits } = mount();
		const grid = line();
		grid.definition.editable_grid = 1;
		answers(grid);
		await children.show("lines");
		await acts.run("settings.set_doctype_property", { property: "editable_grid", value: 0 });
		const child = children.open.value!;
		await children.show(null);
		edits.undo();
		await Promise.resolve();
		expect(children.open.value?.state.doctype).toBe("Task Note Line");
		expect(child.canvas.working.value.settings.properties.editable_grid).toBe(1);
		expect([edits.childDoctypes(), edits.staged.value]).toEqual([[], []]);
	});

	it("sends the parent's call with the modified a child's Settings save moved it to", async () => {
		const { children } = mount();
		answers(line());
		await children.show("lines");
		await acts.run("settings.set_doctype_property", { property: "editable_grid", value: 0 });
		await children.show(null);
		await acts.run("fields.set_field_property", bold("subject"));
		answers({ ...saved, parents: { "Task Note": { was: VERSION.doctype, now: "2026-11-13 10:05:00" } } }, saved);
		await acts.run("editor.save");
		expect(runMethod.mock.calls.slice(-2).map(([, args]) => [args.doctype, args.base_version.doctype])).toEqual([
			["Task Note Line", LINE_VERSION.doctype],
			["Task Note", "2026-11-13 10:05:00"],
		]);
	});

	it("opens a new child of links for a Table MultiSelect, holding its one Link field", async () => {
		const { children } = mount();
		await acts.run("fields.add_field", { label: "Watchers", fieldtype: "Table MultiSelect" });
		await acts.run("fields.add_child_table", { name: "Task Note Watcher", table_field: "watchers", link: "User" });
		await children.show("watchers");
		const fields = children.open.value!.canvas.working.value.fields;
		expect(fields).toMatchObject([{ fieldname: "user", fieldtype: "Link", options: "User", in_list_view: 1 }]);
		expect(children.open.value?.canvas.place("user")).toMatchObject({ section: "main", index: 0 });
	});

	it("opens a new child undone and made again with another link on that link's field", async () => {
		const { children, edits } = mount();
		await acts.run("fields.add_field", { label: "Watchers", fieldtype: "Table MultiSelect" });
		await acts.run("fields.add_child_table", { name: "Task Note Watcher", table_field: "watchers", link: "User" });
		await children.show("watchers");
		edits.undo();
		await acts.run("fields.add_child_table", { name: "Task Note Watcher", table_field: "watchers", link: "Role" });
		await children.show("watchers");
		expect(children.open.value!.canvas.working.value.fields).toMatchObject([{ fieldname: "role", options: "Role" }]);
	});

	it("adds a Table MultiSelect field for a new child of links that no field names yet", async () => {
		const { canvas } = mount();
		await acts.run("fields.add_child_table", { name: "Task Note Watcher", table_field: "watchers", link: "User" });
		expect(canvas.field("watchers")).toMatchObject({ fieldtype: "Table MultiSelect", options: "Task Note Watcher" });
	});

	it("keeps a new child a child table: its Settings tab has no kind row", async () => {
		const { children } = mount();
		await acts.run("fields.add_field", { label: "Steps", fieldtype: "Table" });
		await acts.run("fields.add_child_table", { name: "Task Note Step", table_field: "steps" });
		await children.show("steps");
		const keys = settingRows(children.open.value!.canvas.working.value.settings).map((row) => row.key);
		expect(keys).toContain("editable_grid");
		expect(keys).not.toContain("kind");
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

	it("drops a saved child's steps once its call is in, so the next save sends the parent only", async () => {
		const { children, edits } = mount();
		answers(line());
		await children.show("lines");
		await acts.run("fields.set_field_property", bold("qty"));
		await children.show(null);
		await acts.run("fields.set_field_property", bold("subject"));
		answers(saved, { saved: false, errors: [{ target: { kind: "field", fieldname: "subject" }, message: "No." }] });
		await acts.run("editor.save");
		expect(edits.childDoctypes()).toEqual([]);
		answers(saved);
		await acts.run("editor.save");
		expect(runMethod).toHaveBeenCalledTimes(4);
		expect(runMethod.mock.calls[3][1]).toMatchObject({ doctype: "Task Note", edits: [{ act: "fields.set_field_property", ...bold("subject") }] });
	});

	it("reloads every edited child on reload and reapply, and lists a child edit it refuses", async () => {
		const tasks = { fieldname: "tasks", label: "Tasks", fieldtype: "Table", options: "Task Note Task" };
		const { children, save } = mount(parent({ definition: { ...parent().definition, fields: [...parent().definition.fields, tasks] } }));
		answers(line());
		await children.show("lines");
		await acts.run("fields.set_field_property", bold("qty"));
		answers(line("Task Note Task"));
		await children.show("tasks");
		await acts.run("fields.set_field_property", bold("qty"));
		await children.show(null);
		answers({ saved: false, errors: [{ target: { kind: "banner" }, code: "stale", message: "Changed." }] });
		await acts.run("editor.save");
		const fresh = { ...LINE_VERSION, doctype: "2026-11-13 11:00:00" };
		const renamed = line("Task Note Task");
		renamed.definition.fields = [{ fieldname: "amount", label: "Amount", fieldtype: "Float" }];
		answers(line("Task Note Line", fresh), renamed);
		await acts.run("editor.reload_and_reapply");
		expect(save.banner.value?.messages).toEqual(["qty is not a field of Task Note Task."]);
		expect(children.saves()).toEqual([{ doctype: "Task Note Line", edits: [{ act: "fields.set_field_property", ...bold("qty") }], base_version: fresh }]);
	});

	it("does not send the edits of a new child no Table field names any more", async () => {
		const { children } = mount();
		await acts.run("fields.add_field", { label: "Steps", fieldtype: "Table" });
		await acts.run("fields.add_child_table", { name: "Task Note Step", table_field: "steps" });
		await children.show("steps");
		await acts.run("fields.add_field", { label: "Done", fieldtype: "Check" });
		await children.show(null);
		await acts.run("fields.set_field_property", { fieldname: "steps", property: "options", value: "Task Note Line" });
		answers(saved);
		await acts.run("editor.save");
		expect(runMethod).toHaveBeenCalledOnce();
		expect(Array.isArray(runMethod.mock.calls[0][1].edits)).toBe(true);
	});

	it("marks each refused DocType's errors on its own canvas", async () => {
		const mounted = mount();
		const { children } = mounted;
		await acts.run("fields.add_child_table", { name: "Task Note Step", table_field: "steps" });
		await children.show("steps");
		await acts.run("fields.add_field", { label: "Qty", fieldtype: "Int" });
		await children.show(null);
		const errors = [
			{ target: { kind: "field", fieldname: "qty" }, message: "No qty.", doctype: "Task Note Step" },
			{ target: { kind: "field", fieldname: "subject" }, message: "No subject." },
		];
		answers({ saved: false, errors });
		await acts.run("editor.save");
		const step = children.open.value!.canvas;
		expect(step.state.doctype).toBe("Task Note Step");
		expect([step.errorsAt("field", "qty"), step.errorsAt("field", "subject")]).toEqual([["No qty."], []]);
		expect(mounted.canvas.errorsAt("field", "subject")).toEqual(["No subject."]);
		answers(saved);
		await acts.run("editor.save");
		expect(step.errors.value).toEqual([]);
	});

	it("sends the parent's call with the modified a saved child moved it to, unless someone else moved it first", async () => {
		for (const [was, sent] of [
			[VERSION.doctype, "2026-11-13 10:05:00"],
			["2026-11-13 09:59:00", VERSION.doctype],
		]) {
			runMethod.mockReset();
			const { children } = mount();
			await editChildAndParent(children);
			answers({ ...saved, parents: { "Task Note": { was, now: "2026-11-13 10:05:00" } } }, saved);
			await acts.run("editor.save");
			expect(runMethod.mock.calls[2][1].base_version).toEqual({ ...VERSION, doctype: sent });
			stop();
		}
		stop = () => undefined;
	});

	it("drops a saved child's steps when a later call fails, so a retry sends the parent only", async () => {
		const { children, edits } = mount();
		await editChildAndParent(children);
		answers({ ...saved, parents: { "Task Note": { was: VERSION.doctype, now: "2026-11-13 10:05:00" } } });
		runMethod.mockRejectedValueOnce(new Error("offline"));
		await expect(acts.run("editor.save")).rejects.toThrow("offline");
		expect([edits.childDoctypes(), edits.staged.value.length]).toEqual([[], 1]);
		answers(saved);
		await acts.run("editor.save");
		expect(runMethod.mock.calls[3][1]).toMatchObject({ doctype: "Task Note", base_version: { doctype: "2026-11-13 10:05:00" } });
	});

	it("keeps a new child's column order, which its field order is", async () => {
		const { children } = mount();
		await acts.run("fields.add_child_table", { name: "Task Note Step", table_field: "steps" });
		await children.show("steps");
		await acts.run("fields.add_field", { label: "Done", fieldtype: "Check" });
		await acts.run("fields.add_field", { label: "Note", fieldtype: "Data" });
		children.open.value!.canvas.stage({ act: "fields.reorder_field", fieldname: "note", index: 0 });
		expect(children.open.value!.canvas.working.value.fields.map((field) => field.fieldname)).toEqual(["note", "done"]);
		expect(children.saves()[0].edits.at(-1)).toEqual({ act: "fields.reorder_field", fieldname: "note", index: 0 });
	});

	it("shows a saved child's failed export on the parent's editor, and writes that child's files again", async () => {
		const { children, save, edits } = mount();
		await editChildAndParent(children);
		answers(saved, saved);
		await acts.run("editor.save");
		await save.exported({ doctype: "Task Note Line", ok: false, error: "Disk full" });
		expect(save.banner.value).toMatchObject({ doctype: "Task Note", files: "Task Note Line", messages: ["Disk full"] });
		answers({ Details: "def" });
		await acts.run("editor.write_files_again");
		expect(runMethod).toHaveBeenLastCalledWith(WRITE_FILES_METHOD, { doctype: "Task Note Line" }, { nullable: true });
		expect([save.banner.value, edits.payload().base_version]).toEqual([null, VERSION]);
	});

	it("drops a child load that a switch to another parent outran", async () => {
		const { children } = mount();
		let first!: (value: unknown) => void;
		runMethod.mockReturnValueOnce(new Promise((resolve) => (first = resolve)));
		const stale = children.show("lines");
		children.reset();
		const fresh = { ...LINE_VERSION, doctype: "2026-11-13 11:00:00" };
		answers(line("Task Note Line", fresh));
		await children.show("lines");
		first({ data: line() });
		await stale;
		expect(children.open.value?.state.base_version).toEqual(fresh);
		expect(children.canvasOf("Task Note Line")?.state.base_version).toEqual(fresh);
	});
});
