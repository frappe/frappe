import { afterEach, describe, expect, it, vi } from "vitest";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("frappe-ui", () => ({ toast }));

import { acts } from "@/acts/dispatcher";
import { fieldnameMode, removeQuestion, reqdWarning, subtitle, typeChange, typeGroups, typeNote } from "../fieldPanel";
import { mountEditor, taskNote } from "./editorFixture";

let stop: (() => void) | undefined;
afterEach(() => {
	stop?.();
	stop = undefined;
});

function mount(...args: Parameters<typeof taskNote>) {
	const mounted = mountEditor(taskNote(...args));
	stop = mounted.stop;
	return mounted;
}

describe("the panel's type list", () => {
	it("sets the type and its options as one change, dropping an option that was the type", () => {
		const email = { fieldname: "mail", fieldtype: "Data", options: "Email" };
		expect(typeChange(email, "Data")).toEqual({ fieldtype: "Data", options: "" });
		expect(typeChange({ fieldname: "mail", fieldtype: "Data" }, "Email")).toEqual({ fieldtype: "Data", options: "Email" });
		expect(typeChange({ fieldname: "who", fieldtype: "Link", options: "User" }, "Link")).toEqual({ fieldtype: "Link" });
		expect(typeChange({ fieldname: "who", fieldtype: "Link", options: "User" }, "Data")).toEqual({ fieldtype: "Data", options: "" });
	});


	it("keeps a saved field with values to the types that keep them, the rest disabled with the reason", () => {
		const { canvas } = mount();
		const { groups, more } = typeGroups(canvas, "subject");
		expect(groups[0]).toEqual({
			label: "Keeps its 4 values",
			types: ["Small Text", "Data", "Email", "Long Text", "Text"].map((name) => ({ name, disabled: false })),
		});
		expect(groups[1].label).toBe("Not while 4 records hold a value");
		expect(groups[1].types.every((type) => type.disabled)).toBe(true);
		expect(groups[1].types.map((type) => type.name)).toContain("Date");
		expect(more).toEqual([]);
	});

	it("offers any type to a saved field with no values, and to a field added since the save", async () => {
		const { canvas } = mount();
		expect(typeGroups(canvas, "spare").groups[0].types.every((type) => !type.disabled)).toBe(true);
		await acts.run("fields.add_field", { label: "Due on", fieldtype: "Date" });
		const { groups, more } = typeGroups(canvas, "due_on");
		expect(groups).toHaveLength(1);
		expect(more.flatMap((group) => group.types.map((type) => type.name))).toContain("Markdown Editor");
	});

	it("offers HTML Editor with the text types", async () => {
		const { canvas } = mount();
		await acts.run("fields.add_field", { label: "Body", fieldtype: "Data" });
		const text = typeGroups(canvas, "body").more.find((group) => group.label === "Text");
		expect(text?.types.map((type) => type.name)).toContain("HTML Editor");
	});

	it("limits by the saved type, so a second change cannot leave the group", async () => {
		const { canvas } = mount();
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "fieldtype", value: "Data" });
		const keeps = typeGroups(canvas, "subject").groups[0].types.map((type) => type.name);
		expect(keeps).not.toContain("Barcode");
		expect(typeNote(canvas, canvas.field("subject")!)).toBe(
			"The column changes type on save. Its 4 values are kept.",
		);
	});

	it("shows the value count in place of the fieldname for a saved field", async () => {
		const { canvas } = mount();
		expect(subtitle(canvas, canvas.field("subject")!)).toBe("Small Text · 4 values");
		await acts.run("fields.add_field", { label: "Email", fieldtype: "Data", options: "Email" });
		expect(subtitle(canvas, canvas.field("email")!)).toBe("Email · email");
	});
});

describe("the panel's fieldname, remove and reqd notes", () => {
	it("follows the label for a new field, renames on a custom DocType, and locks on a standard one", async () => {
		const custom = mount();
		await acts.run("fields.add_field", { label: "Owner", fieldtype: "Data" });
		expect(fieldnameMode(custom.canvas, "owner")).toBe("follows");
		expect(fieldnameMode(custom.canvas, "subject")).toBe("renamable");
		stop?.();
		const standard = mount({ custom: 0 });
		expect(fieldnameMode(standard.canvas, "subject")).toBe("locked");
	});

	it("asks once with the value count before removing a saved field, and not for a new one", async () => {
		const { canvas } = mount();
		expect(removeQuestion(canvas, canvas.field("subject")!)).toBe(
			"Its column and the 4 values in it stay in the database, but no form, list or report shows them. " +
				"Subject also leaves every layout of Task Note.",
		);
		await acts.run("fields.add_field", { label: "Owner", fieldtype: "Data" });
		expect(removeQuestion(canvas, canvas.field("owner")!)).toBeNull();
	});

	it("warns of a mandatory field in a conditional container, by the container's label", async () => {
		const { canvas } = mount();
		expect(reqdWarning(canvas, "notes")).toContain("“more”, which has a condition");
		await acts.run("canvas.set_container_property", { container: "more", property: "label", value: "Extra" });
		expect(reqdWarning(canvas, "notes")).toContain("“Extra”");
		expect(reqdWarning(canvas, "subject")).toBe("");
	});
});
