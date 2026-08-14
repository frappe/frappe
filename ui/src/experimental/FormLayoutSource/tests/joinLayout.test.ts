import { describe, expect, it } from "vitest";
import { joinLayout } from "../joinLayout";
import { resolveLayout } from "../../../components/FormLayout/resolveLayout";
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

describe("joinLayout — decorate", () => {
	it("threads the decorator onto every joined field", () => {
		// The whole reason `Decorator` exists: an undecorated `Button` renders
		// inert, so an app makes one clickable by decorating it here.
		const click = () => {};
		const [tab] = joinLayout(treeWith(["first_name", "status"]), fields, {
			decorate: (f) => (f.fieldtype === "Data" ? { on: { click } } : undefined),
		});
		const [first, second] = tab.sections[0].columns[0].fields;
		expect(first.ui?.on?.click).toBe(click);
		expect(second.ui).toBeUndefined();
	});

	it("inherits the decorator into a child table's grid columns", () => {
		const seen: string[] = [];
		joinLayout(treeWith(["notes"]), fields, {
			childMetas: {
				"Note Row": [
					{ fieldname: "body", fieldtype: "Data", in_list_view: 1 },
				],
			},
			decorate: (f) => {
				seen.push(f.fieldname);
			},
		});
		expect(seen).toContain("body");
	});

	it("leaves nodes plain when no decorator is passed", () => {
		const [tab] = joinLayout(treeWith(["first_name"]), fields);
		expect(tab.sections[0].columns[0].fields[0].ui).toBeUndefined();
	});
});

describe("joinLayout — overrides", () => {
	it("attaches an override to the named field only", () => {
		const [tab] = joinLayout(treeWith(["first_name", "status"]), fields, {
			overrides: { first_name: { hidden: true } },
		});
		const [first, second] = tab.sections[0].columns[0].fields;
		expect(first.override).toEqual({ hidden: true });
		expect(second.override).toBeUndefined();
	});

	it("does not pre-apply the override — resolveLayout has the last word", () => {
		// The carrier is inert data at join time; applying it early would put it
		// back under `depends_on`, which re-ORs on every keystroke.
		const [tab] = joinLayout(treeWith(["first_name"]), fields, {
			overrides: { first_name: { hidden: true } },
		});
		expect(tab.sections[0].columns[0].fields[0].hidden).toBe(false);
	});

	it("ignores an override naming a field the layout does not render", () => {
		const [tab] = joinLayout(treeWith(["first_name"]), fields, {
			overrides: { gone: { hidden: true } },
		});
		expect(tab.sections[0].columns[0].fields).toHaveLength(1);
	});
});

describe("joinLayout — column presentation", () => {
	it("carries a column's hideLabel", () => {
		const tree: LayoutTree = [
			{
				name: "t",
				sections: [
					{
						name: "s",
						columns: [
							{ name: "c1", label: "Left", hideLabel: true, fields: [] },
							{ name: "c2", label: "Right", fields: [] },
						],
					},
				],
			},
		];
		const [tab] = joinLayout(tree, fields);
		expect(tab.sections[0].columns[0]).toMatchObject({
			label: "Left",
			hideLabel: true,
		});
		expect(tab.sections[0].columns[1].hideLabel).toBe(false);
	});
});

describe("joinLayout + resolveLayout — the permlevel floor, end to end", () => {
	// The two halves are otherwise only tested apart, so a regression in how
	// `withAccess` expresses a denial would fail nothing.
	const treeFor = (name: string) => treeWith([name]);
	const fieldOf = (schema: ReturnType<typeof joinLayout>) =>
		schema[0].sections[0].columns[0].fields[0];

	it("a `none` denial survives an override that tries to un-hide it", () => {
		const joined = joinLayout(treeFor("secret"), fields, {
			fieldAccess: () => "none",
			overrides: { secret: { hidden: false } },
		});
		expect(fieldOf(joined).permDenied).toBe(true);
		expect(fieldOf(resolveLayout(joined, {})).hidden).toBe(true);
	});

	it("a `read` denial survives an override that tries to un-lock it", () => {
		const joined = joinLayout(treeFor("secret"), fields, {
			fieldAccess: () => "read",
			overrides: { secret: { readOnly: false } },
		});
		expect(fieldOf(resolveLayout(joined, {})).readOnly).toBe(true);
	});

	it("grants the override when the reader has the permlevel", () => {
		// `withAccess` leaves a writable field untouched, so nothing is stamped
		// and the override applies — the case a `permlevel`-based floor broke.
		const joined = joinLayout(treeFor("secret"), fields, {
			fieldAccess: () => "write",
			overrides: { secret: { hidden: true } },
		});
		expect(fieldOf(joined).permDenied).toBe(false);
		expect(fieldOf(resolveLayout(joined, {})).hidden).toBe(true);
	});
});
