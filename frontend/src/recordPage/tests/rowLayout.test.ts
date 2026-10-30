// The row dialog's layout: a `Table` field whose child doctype has Details rows picks one per
// row, as the record page picks its own; with no row it draws the child's full form.
import { describe, expect, it } from "vitest";
import { layoutFields } from "@framework/ui/FormLayout";
import type { FieldNode, FormLayoutSchema, RawMetaField } from "@framework/ui/FormLayout/types";
import { joinLayout } from "../formLayoutSource/joinLayout";
import { missingRequired } from "../requiredFields";
import type { FormLayoutRow, LayoutTree } from "../formLayoutSource/types";

const CHILD = "Deal Item";

const parentFields: RawMetaField[] = [
	{ fieldname: "title", fieldtype: "Data", label: "Title" },
	{ fieldname: "items", fieldtype: "Table", label: "Items", options: CHILD },
];

const childFields: RawMetaField[] = [
	{ fieldname: "item", fieldtype: "Data", label: "Item", reqd: 1 },
	{ fieldname: "kind", fieldtype: "Select", label: "Kind", options: "Goods\nService" },
	{ fieldname: "hours", fieldtype: "Float", label: "Hours", reqd: 1 },
	{ fieldname: "qty", fieldtype: "Float", label: "Qty", default: "1" },
];

function tree(...sections: { name: string; label?: string; dependsOn?: string; fields: string[] }[]): LayoutTree {
	return [
		{
			name: "first_tab",
			sections: sections.map(({ fields, ...section }) => ({ ...section, columns: [{ fields }] })),
		},
	];
}

const defaultRow: FormLayoutRow = {
	name: "goods",
	condition: null,
	layout: tree({ name: "goods", label: "Goods", fields: ["item", "kind", "hours"] }),
	omitted: ["qty"],
};

const serviceRow: FormLayoutRow = {
	name: "service",
	condition: "eval:doc.kind == 'Service'",
	layout: tree(
		{ name: "service", label: "Service", fields: ["item", "kind"] },
		{ name: "time", dependsOn: "eval:doc.item", fields: ["hours"] }
	),
};

function itemsField(rows: FormLayoutRow[] = [defaultRow, serviceRow]): FieldNode {
	const schema = joinLayout(tree({ name: "main", fields: ["title", "items"] }), parentFields, {
		childMetas: { [CHILD]: childFields },
		childLayouts: { [CHILD]: rows },
	});
	return layoutFields(schema).find((field) => field.fieldname === "items")!;
}

function sectionsOf(layout: FormLayoutSchema) {
	return layout[0].sections.map((section) => [
		section.label ?? section.name,
		section.columns.flatMap((column) => column.fields.map((field) => field.fieldname)),
	]);
}

describe("the row dialog's layout", () => {
	it("draws the child's default Details row, with its unplaced fields in More fields", () => {
		const items = itemsField([{ ...defaultRow, omitted: [] }]);
		expect(sectionsOf(items.rowLayout!({ item: "Pen" }))).toEqual([
			["Goods", ["item", "kind", "hours"]],
			["More fields", ["qty"]],
		]);
	});

	it("keeps a field the row omits off the dialog", () => {
		expect(sectionsOf(itemsField().rowLayout!({ kind: "Goods" }))).toEqual([
			["Goods", ["item", "kind", "hours"]],
		]);
	});

	it("chooses a conditional row against the row, so two rows of one table get two dialogs", () => {
		const items = itemsField();
		expect(sectionsOf(items.rowLayout!({ kind: "Service" }))[0][0]).toBe("Service");
		expect(sectionsOf(items.rowLayout!({ kind: "Goods" }))[0][0]).toBe("Goods");
	});

	it("hands back the same layout while the row stays on one Details row", () => {
		const items = itemsField();
		expect(items.rowLayout!({ kind: "Service", item: "a" })).toBe(
			items.rowLayout!({ kind: "Service", item: "b" })
		);
	});

	it("draws the child's full form when no row matches", () => {
		const items = itemsField([serviceRow]);
		expect(items.rowLayout!({ kind: "Goods" })).toBe(items.childLayout);
	});

	it("is absent when the child has no Details row, so the dialog draws the full form", () => {
		const items = itemsField([]);
		expect(items.rowLayout).toBeUndefined();
		expect(layoutFields(items.childLayout!).map((field) => field.fieldname)).toEqual([
			"item",
			"kind",
			"hours",
			"qty",
		]);
	});

	it("keeps every child meta field in childLayout, so a new row takes the default of one a row omits", () => {
		const qty = layoutFields(itemsField().childLayout!).find((field) => field.fieldname === "qty");
		expect(qty?.default).toBe("1");
	});
});

describe("the required-cell check on a row", () => {
	function missing(row: Record<string, any>) {
		const schema = joinLayout(tree({ name: "main", fields: ["items"] }), parentFields, {
			childMetas: { [CHILD]: childFields },
			childLayouts: { [CHILD]: [defaultRow, serviceRow] },
		});
		return missingRequired(schema, { items: [{ name: "r1", ...row }] }).map(
			(one) => (one.address as { fieldname: string }).fieldname
		);
	}

	it("reads the row's chosen layout: a cell its hidden section holds is not demanded", () => {
		expect(missing({ kind: "Service" })).toEqual(["item"]);
		expect(missing({ kind: "Goods" })).toEqual(["item", "hours"]);
	});
});
