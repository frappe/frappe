import { describe, expect, it } from "vitest";
import { saveSummary } from "../saveSummary";

describe("the Customize save toast", () => {
	it("counts the custom fields, the property changes and the layout it wrote", () => {
		expect(
			saveSummary([
				{ act: "fields.add_field", label: "Due On", fieldtype: "Date", section: "main" },
				{ act: "fields.set_field_property", fieldname: "custom_due_on", property: "reqd", value: 1 },
				{ act: "fields.set_field_property", fieldname: "subject", property: "label", value: "Title" },
				{ act: "fields.set_field_property", fieldname: "subject", property: "label", value: "Topic" },
				{ act: "fields.reset_field_property", fieldname: "status", property: "bold" },
				{ act: "canvas.move_field", fieldname: "status", section: "more" },
			]),
		).toBe("Saved 1 custom field, 2 property changes and the layout.");
	});

	it("names one property change on its own", () => {
		expect(
			saveSummary([{ act: "fields.set_field_property", fieldname: "subject", properties: { fieldtype: "Text" } }]),
		).toBe("Saved 1 property change.");
	});

	it("follows a new field through its rename", () => {
		expect(
			saveSummary([
				{ act: "fields.add_field", label: "Due", fieldtype: "Date" },
				{ act: "fields.rename_field", fieldname: "custom_due", new_fieldname: "custom_due_on" },
				{ act: "fields.set_field_property", fieldname: "custom_due_on", property: "bold", value: 1 },
			]),
		).toBe("Saved 1 custom field.");
	});

	it("counts a fetched field and a new Table field as custom fields", () => {
		expect(
			saveSummary([
				{ act: "fields.fetch_field", link: "owner", source: "full_name", fieldname: "custom_full_name" },
				{ act: "fields.set_field_property", fieldname: "custom_full_name", property: "label", value: "Owner" },
				{ act: "fields.add_child_table", name: "Task Note Row", table_field: "custom_rows" },
				{ act: "fields.set_field_property", fieldname: "subject", property: "bold", value: 1 },
			]),
		).toBe("Saved 2 custom fields and 1 property change.");
	});

	it("drops a new field removed before the save", () => {
		expect(
			saveSummary([
				{ act: "fields.add_field", label: "Due", fieldtype: "Date" },
				{ act: "fields.set_field_property", fieldname: "custom_due", property: "bold", value: 1 },
				{ act: "fields.delete_field", fieldname: "custom_due" },
			]),
		).toBe("Saved");
	});

	it("leaves out what the server skipped and what was set back", () => {
		const edits = [
			{ act: "fields.set_field_property", fieldname: "subject", property: "label", value: "Topic" },
			{ act: "fields.set_field_property", fieldname: "status", property: "in_list_view", value: 1 },
			{ act: "fields.set_field_property", fieldname: "notes", property: "bold", value: 0 },
		];
		const skipped = [{ target: { kind: "field" as const, fieldname: "status", property: "in_list_view" }, message: "No." }];
		const unchanged = (fieldname: string) => fieldname === "notes";
		expect(saveSummary(edits, { skipped, unchanged })).toBe("Saved 1 property change.");
	});
});
