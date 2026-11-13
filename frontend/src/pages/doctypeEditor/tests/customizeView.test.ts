import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("frappe-ui", () => ({ toast }));

import { acts } from "@/acts/dispatcher";
import type { EditorState } from "../editorSource";
import { fieldnameMode, removeAction, rowMark, subtitle, typeGroups } from "../fieldPanel";
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

describe("the panel rows in Customize", () => {
	it("lock a property with its reason, and offer a changed one's reset to the app's value", async () => {
		const { canvas } = mount();
		await acts.run("fields.set_field_property", { fieldname: "status", property: "bold", value: 0 });
		expect(rowMark(canvas, "notes", "reqd")).toEqual({ lock: "The app makes this field mandatory." });
		expect(rowMark(canvas, "subject", "label")).toEqual({ changed: true, resetText: "Reset to ERPNext's value (Subject)" });
		expect(rowMark(canvas, "status", "bold")).toEqual({ changed: true, resetText: "Reset to ERPNext's value (off)" });
		expect(rowMark(canvas, "subject", "bold")).toEqual({});
		expect(rowMark(canvas, "custom_rating", "label")).toEqual({});
	});

	it("draw no row marks in Design", () => {
		const { canvas } = mountEditor(taskNote());
		expect(rowMark(canvas, "notes", "reqd")).toEqual({});
	});

	it("offer only a standard field's allowed types, the rest disabled", () => {
		const { canvas } = mount();
		const { groups, more } = typeGroups(canvas, "subject");
		expect(groups[0]).toEqual({
			label: "A standard Small Text field can become",
			types: [
				{ name: "Small Text", disabled: false },
				{ name: "Text", disabled: false },
			],
		});
		expect(groups[1].label).toBe("Not on a standard field");
		expect(groups[1].types.every((type) => type.disabled)).toBe(true);
		expect(groups[1].types.map((type) => type.name)).toContain("Data");
		expect(more).toEqual([]);
	});

	it("name where a field comes from", () => {
		const { canvas } = mount();
		const of = (fieldname: string) => subtitle(canvas, canvas.field(fieldname)!);
		expect(of("region")).toBe("Data · From ERPNext · 0 values");
		expect(of("custom_rating")).toBe("Int · Custom · 0 values");
		expect(of("subject")).toBe("Small Text · Standard · 4 values");
	});

	it("rename only a site's custom field", () => {
		const { canvas } = mount();
		expect(fieldnameMode(canvas, "subject")).toBe("locked");
		expect(fieldnameMode(canvas, "region")).toBe("locked");
		expect(fieldnameMode(canvas, "custom_rating")).toBe("renamable");
	});

	it("hide or show a standard field in place of remove", async () => {
		const { canvas } = mount();
		expect(removeAction(canvas, canvas.field("status")!)).toEqual({ label: "Hide field", icon: "lucide-eye-off" });
		expect(removeAction(canvas, canvas.field("custom_rating")!)).toEqual({ label: "Remove field", icon: "lucide-trash-2" });
		await acts.run("fields.set_field_property", { fieldname: "status", property: "hidden", value: 1 });
		expect(removeAction(canvas, canvas.field("status")!)).toEqual({ label: "Show field", icon: "lucide-eye" });
	});

	it("name the field a custom field is placed after", async () => {
		const { canvas } = mount();
		await acts.run("fields.add_field", { label: "Due On", fieldtype: "Date", section: "more", column: "column_1", index: 0 });
		expect(canvas.customize!.anchor("custom_due_on")?.fieldname).toBe("status");
		await acts.run("fields.add_field", { label: "First", fieldtype: "Data", section: "main", column: "column_1", index: 0 });
		expect(canvas.customize!.anchor("custom_first")).toBeNull();
		expect(canvas.customize!.anchor("subject")).toBeUndefined();
	});
});
