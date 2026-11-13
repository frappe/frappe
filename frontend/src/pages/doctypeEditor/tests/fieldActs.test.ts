import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("frappe-ui", () => ({ toast }));

import { acts } from "@/acts/dispatcher";
import type { DesignCanvas } from "../designCanvas";
import { mountEditor, taskNote } from "./editorFixture";

let stop: () => void;
beforeEach(() => toast.error.mockReset());
afterEach(() => stop());

function mount(...args: Parameters<typeof taskNote>) {
	const mounted = mountEditor(taskNote(...args));
	stop = mounted.stop;
	return mounted;
}

const fieldnames = (canvas: DesignCanvas) => canvas.working.value.fields.map((field) => field.fieldname);

describe("the field and settings acts", () => {
	const cases: [act: string, value: Record<string, unknown>, check: (canvas: DesignCanvas) => unknown, expected: unknown][] = [
		["fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 }, (c) => (c.field("subject") as { bold?: number } | undefined)?.bold, 1],
		[
			"fields.set_field_property",
			{ fieldname: "spare", properties: { fieldtype: "Link", options: "User" } },
			(c) => [c.field("spare")?.fieldtype, c.field("spare")?.options],
			["Link", "User"],
		],
		["fields.rename_field", { fieldname: "subject", new_fieldname: "title" }, (c) => [fieldnames(c), c.place("title")?.index], [["title", "status", "notes", "spare"], 0]],
		["fields.delete_field", { fieldname: "status" }, (c) => [fieldnames(c), c.place("status")], [["subject", "notes", "spare"], null]],
		["settings.set_doctype_property", { property: "description", value: "One note on a task" }, (c) => c.working.value.description, "One note on a task"],
	];

	it.each(cases)("%s stages one undo step, and undo restores the state", async (act, value, check, expected) => {
		const { canvas, edits } = mount();
		const before = check(canvas);
		await acts.run(act, value);
		expect(check(canvas)).toEqual(expected);
		expect(edits.steps).toHaveLength(1);
		edits.undo();
		expect(check(canvas)).toEqual(before);
	});

	it("keep the selection on a renamed field, and drop it from a removed one", async () => {
		const { canvas } = mount();
		canvas.select({ kind: "field", fieldname: "subject" });
		await acts.run("fields.rename_field", { fieldname: "subject", new_fieldname: "title" });
		expect(canvas.selection.value).toEqual({ kind: "field", fieldname: "title" });
		await acts.run("fields.delete_field", { fieldname: "title" });
		expect(canvas.selection.value).toBeNull();
	});

	it("refuse to rename a saved field of a standard DocType, as a toast", async () => {
		const { canvas, edits } = mount({ custom: 0 });
		await acts.perform("fields.rename_field", { fieldname: "subject", new_fieldname: "title" });
		expect(toast.error).toHaveBeenCalledWith("Renaming a saved field of a standard DocType needs a patch.");
		expect([fieldnames(canvas)[0], edits.steps.length]).toEqual(["subject", 0]);
	});
});

describe("a field's fieldname follows its label until the save", () => {
	it("renames a field added since the save with its label, in one undo step", async () => {
		const { canvas, edits } = mount();
		await acts.run("fields.add_field", { label: "Owner", fieldtype: "Data", section: "main", column: "column_1" });
		await acts.run("fields.set_field_property", { fieldname: "owner", property: "label", value: "Task owner" });
		expect(canvas.field("task_owner")?.label).toBe("Task owner");
		expect(canvas.selection.value).toEqual({ kind: "field", fieldname: "task_owner" });
		expect(edits.staged.value.slice(-2).map((edit) => edit.act)).toEqual([
			"fields.set_field_property",
			"fields.rename_field",
		]);
		edits.undo();
		expect([canvas.field("owner")?.label, canvas.field("task_owner")]).toEqual(["Owner", undefined]);
	});

	it("keeps a saved field's fieldname, and one whose label spells another field's", async () => {
		const { canvas, edits } = mount();
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "label", value: "Headline" });
		expect(canvas.field("subject")?.label).toBe("Headline");
		await acts.run("fields.add_field", { label: "Owner", fieldtype: "Data" });
		await acts.run("fields.set_field_property", { fieldname: "owner", property: "label", value: "Spare" });
		expect(canvas.field("owner")?.label).toBe("Spare");
		expect(edits.staged.value.filter((edit) => edit.act === "fields.rename_field")).toEqual([]);
	});
});
