import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("frappe-ui", () => ({ toast }));

import { acts } from "@/acts/dispatcher";
import type { EditorState } from "../editorSource";
import { mountEditor, taskNote } from "./editorFixture";

let stop: () => void;
beforeEach(() => toast.error.mockReset());
afterEach(() => stop());

/** Task Note as an app ships it, with this site's changes: a label, a custom field, and an app's custom field. */
function customized(): EditorState {
	const base = taskNote();
	return {
		...base,
		mode: "Customize",
		modes: ["Customize"],
		custom: 0,
		app_title: "ERPNext",
		definition: {
			...base.definition,
			fields: [
				{ fieldname: "subject", label: "Title", fieldtype: "Small Text" },
				...base.definition.fields.slice(1),
				{ fieldname: "custom_rating", label: "Rating", fieldtype: "Int", is_custom_field: 1 },
				{ fieldname: "region", label: "Region", fieldtype: "Data", is_custom_field: 1, is_system_generated: 1 },
			],
		},
		custom_fields: [
			{ name: "Task Note-custom_rating", fieldname: "custom_rating", is_system_generated: 0 },
			{ name: "Task Note-region", fieldname: "region", is_system_generated: 1 },
		],
		property_setters: [
			{ field_name: "subject", doctype_or_field: "DocField", property: "label", value: "Title", app_value: "Subject", is_system_generated: 0 },
			{ field_name: "status", doctype_or_field: "DocField", property: "bold", value: "1", app_value: 0, is_system_generated: 1 },
		],
		locks: { notes: { reqd: "The app makes this field mandatory." } },
		fieldtype_changes: { subject: ["Small Text", "Text"], status: ["Select"] },
	} as EditorState;
}

function mount() {
	const mounted = mountEditor(customized());
	stop = mounted.stop;
	return mounted;
}

describe("the canvas marks in Customize", () => {
	it("mark only what the site changed", async () => {
		const { canvas } = mount();
		await acts.run("fields.set_field_property", { fieldname: "status", property: "hidden", value: 1 });
		const view = canvas.customize!;
		expect(view.marks("custom_rating")).toEqual({ custom: true, changed: [], hidden: false });
		expect(view.marks("region")).toEqual({ custom: false, changed: [], hidden: false });
		expect(view.marks("subject")).toEqual({ custom: false, changed: ["label"], hidden: false });
		expect(view.marks("status")).toEqual({ custom: false, changed: ["hidden"], hidden: true });
		expect(view.marks("notes")).toEqual({ custom: false, changed: [], hidden: false });
	});

	it("a new field is a custom field named custom_ and its label", async () => {
		const { canvas } = mount();
		await acts.run("fields.add_field", { label: "Due On", fieldtype: "Date", section: "main", column: "column_1" });
		expect(canvas.field("custom_due_on")?.label).toBe("Due On");
		expect(canvas.customize!.marks("custom_due_on").custom).toBe(true);
		await acts.run("fields.set_field_property", { fieldname: "custom_due_on", property: "label", value: "Due" });
		expect(canvas.field("custom_due")?.label).toBe("Due");
	});

	it("draws no marks in Design", () => {
		const mounted = mountEditor(taskNote());
		stop = mounted.stop;
		expect(mounted.canvas.customize).toBeNull();
	});
});

describe("the panel in Customize", () => {
	it("gives a locked property's reason, and refuses to change it", async () => {
		const { canvas, edits } = mount();
		expect(canvas.customize!.lock("notes", "reqd")).toBe("The app makes this field mandatory.");
		expect(canvas.customize!.lock("notes", "label")).toBeUndefined();
		await acts.perform("fields.set_field_property", { fieldname: "notes", property: "reqd", value: 0 });
		expect(edits.staged.value).toEqual([]);
		expect(toast.error).toHaveBeenCalledWith("The app makes this field mandatory.");
	});

	it("resets one changed property to the app's value and keeps the others", async () => {
		const { canvas, edits } = mount();
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		await acts.run("fields.reset_field_property", { fieldname: "subject", property: "label" });
		expect(canvas.field("subject")).toMatchObject({ label: "Subject", bold: 1 });
		expect(canvas.customize!.marks("subject").changed).toEqual(["bold"]);
		expect(edits.staged.value.at(-1)).toEqual({ act: "fields.reset_field_property", fieldname: "subject", property: "label" });
		edits.undo();
		expect(canvas.field("subject")?.label).toBe("Title");
	});

	it("lists a standard field's allowed types; a custom field takes any", () => {
		const { canvas } = mount();
		expect(canvas.customize!.fieldtypes("subject")).toEqual(["Small Text", "Text"]);
		expect(canvas.customize!.fieldtypes("custom_rating")).toBeNull();
	});

	it("hides a standard field instead of removing it", async () => {
		const { canvas } = mount();
		expect(canvas.customize!.hidesOnRemove("status")).toBe(true);
		expect(canvas.customize!.hidesOnRemove("custom_rating")).toBe(false);
		await acts.perform("fields.delete_field", { fieldname: "status" });
		expect(toast.error).toHaveBeenCalledWith("status is a standard field. Hide it instead.");
	});
});
