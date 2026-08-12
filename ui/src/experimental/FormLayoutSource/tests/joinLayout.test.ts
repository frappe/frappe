import { describe, expect, it } from "vitest";
import { joinLayout } from "../joinLayout";
import type { RawMetaField } from "../../../components/FormLayout/types";
import type { LayoutTree } from "../types";

const fields: RawMetaField[] = [
	{ fieldname: "first_name", fieldtype: "Data", label: "First Name", reqd: 1 },
	{ fieldname: "status", fieldtype: "Select", options: "Open\nClosed" },
	{ fieldname: "secret", fieldtype: "Data", permlevel: 1 },
	{ fieldname: "a_break", fieldtype: "Section Break" },
	{ fieldname: "notes", fieldtype: "Table", options: "Note Row" },
];

function treeWith(fieldnames: string[]): LayoutTree {
	return [
		{
			name: "first_tab",
			sections: [
				{ name: "main", label: "Main", columns: [{ name: "col_1", fields: fieldnames }] },
			],
		},
	];
}

describe("joinLayout", () => {
	it("joins fieldnames against meta into FieldNodes", () => {
		const [tab] = joinLayout(treeWith(["first_name", "status"]), fields);
		const joined = tab.sections[0].columns[0].fields;
		expect(joined.map((f) => f.fieldname)).toEqual(["first_name", "status"]);
		expect(joined[0]).toMatchObject({ fieldtype: "Data", reqd: true });
		expect(joined[1].options).toBe("Open\nClosed");
	});

	it("drops unknown fieldnames and layout breaks", () => {
		const [tab] = joinLayout(treeWith(["gone", "a_break", "first_name"]), fields);
		expect(tab.sections[0].columns[0].fields.map((f) => f.fieldname)).toEqual([
			"first_name",
		]);
	});

	it("carries section presentation, defaulting opened to true", () => {
		const tree: LayoutTree = [
			{
				name: "t",
				sections: [
					{ name: "s", hideLabel: true, opened: false, columns: [] },
					{ name: "s2", columns: [] },
				],
			},
		];
		const [tab] = joinLayout(tree, fields);
		expect(tab.sections[0]).toMatchObject({ hideLabel: true, opened: false });
		expect(tab.sections[1].opened).toBe(true);
	});

	it("bakes permlevel access: read demotes, none hides", () => {
		const asRead = joinLayout(treeWith(["secret"]), fields, {
			fieldAccess: () => "read",
		});
		expect(asRead[0].sections[0].columns[0].fields[0].readOnly).toBe(true);
		const asNone = joinLayout(treeWith(["secret"]), fields, {
			fieldAccess: () => "none",
		});
		expect(asNone[0].sections[0].columns[0].fields[0].hidden).toBe(true);
	});

	it("resolves Table columns through childMetas", () => {
		const childMetas = {
			"Note Row": [
				{ fieldname: "note", fieldtype: "Data", in_list_view: 1 },
			] as RawMetaField[],
		};
		const [tab] = joinLayout(treeWith(["notes"]), fields, { childMetas });
		const table = tab.sections[0].columns[0].fields[0];
		expect(table.childFields?.map((f) => f.fieldname)).toEqual(["note"]);
	});
});
