import { describe, expect, it } from "vitest";
import { newChildName, pendingChild } from "../childSource";
import { taskNote } from "./editorFixture";

describe("newChildName", () => {
	it("is the parent and the table's label in the singular", () => {
		expect(newChildName("Sales Invoice", "Payment Plans")).toBe("Sales Invoice Payment Plan");
		expect(newChildName("Project", "Activities")).toBe("Project Activity");
		expect(newChildName("Course", "Classes")).toBe("Course Class");
		expect(newChildName("Order", "Status")).toBe("Order Status");
		expect(newChildName("Order", "Address")).toBe("Order Address");
	});

	it("is the parent's Item when the table has no label", () => {
		expect(newChildName("Sales Invoice", "")).toBe("Sales Invoice Item");
		expect(newChildName("Sales Invoice", "  ")).toBe("Sales Invoice Item");
	});
});

describe("pendingChild", () => {
	it("is an empty child table in the parent's module, with the DocType defaults", () => {
		const child = pendingChild("Task Note Line", taskNote());
		expect(child).toMatchObject({ doctype: "Task Note Line", module: "Desk", custom: 1, pending: true, mode: "Design" });
		expect(child.definition).toMatchObject({ istable: 1, editable_grid: 1, allow_bulk_edit: 1, fields: [] });
	});

	it("suffixes a Link fieldname that is a row column", () => {
		const child = pendingChild("Task Note Kind", taskNote(), "DocType");
		expect(child.definition.fields.map((field) => field.fieldname)).toEqual(["doctype_link"]);
	});

	it("holds one Link field when it is a child of links", () => {
		const child = pendingChild("Task Note Watcher", taskNote(), "Sales Order");
		expect(child.definition.fields).toEqual([
			{ fieldname: "sales_order", label: "Sales Order", fieldtype: "Link", options: "Sales Order", in_list_view: 1 },
		]);
	});
});
