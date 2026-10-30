import { describe, expect, it } from "vitest";
import { joinLayout } from "../formLayoutSource/joinLayout";
import { resolveLayout } from "@framework/ui/FormLayout";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { LayoutTree, LayoutTreeColumn } from "../formLayoutSource/types";

const fields: RawMetaField[] = [
	{ fieldname: "first_name", fieldtype: "Data", label: "First Name", reqd: 1 },
	{ fieldname: "status", fieldtype: "Select", options: "Open\nClosed" },
	{ fieldname: "secret", fieldtype: "Data", permlevel: 1 },
	{ fieldname: "a_break", fieldtype: "Section Break" },
	{ fieldname: "a_fold", fieldtype: "Fold" },
	{ fieldname: "gallery", fieldtype: "Attachment Gallery" },
	{ fieldname: "notes", fieldtype: "Table", options: "Note Row" },
	{ fieldname: "email_id", fieldtype: "Data", label: "Email Address", read_only: 1 },
];

function treeWith(fieldnames: LayoutTreeColumn["fields"]): LayoutTree {
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

	it("drops Fold and Attachment Gallery, which have no control", () => {
		const [tab] = joinLayout(treeWith(["a_fold", "gallery", "first_name"]), fields);
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

describe("joinLayout — inline fields", () => {
	it("renders an inline field beside meta fields", () => {
		const nickname = { fieldname: "nickname", fieldtype: "Data", label: "Nickname" };
		const [tab] = joinLayout(treeWith(["first_name", nickname]), fields);
		const [first, inline] = tab.sections[0].columns[0].fields;
		expect(first.fieldname).toBe("first_name");
		expect(inline).toMatchObject({ fieldname: "nickname", fieldtype: "Data", label: "Nickname" });
		expect(inline.readOnly).toBeFalsy();
	});

	it("replaces a read-only meta field of the same name", () => {
		const email = { fieldname: "email_id", fieldtype: "Data", label: "Email", options: "Email" };
		const [tab] = joinLayout(treeWith([email]), fields);
		const [field] = tab.sections[0].columns[0].fields;
		expect(field).toMatchObject({ fieldname: "email_id", label: "Email", options: "Email" });
		expect(field.readOnly).toBeFalsy();
	});

	it("gates a replacement by the permlevel of the field it replaces", () => {
		const fieldsWithLevel: RawMetaField[] = [...fields, { fieldname: "phone", fieldtype: "Data", read_only: 1, permlevel: 1 }];
		const phone = { fieldname: "phone", fieldtype: "Data", permlevel: 0 };
		const [tab] = joinLayout(treeWith([phone]), fieldsWithLevel, {
			fieldAccess: (field) => (field.permlevel === 1 ? "read" : "write"),
		});
		expect(tab.sections[0].columns[0].fields[0].readOnly).toBe(true);
	});

	it("gates an inline field by its permlevel", () => {
		const secret = { fieldname: "pin", fieldtype: "Data", permlevel: 1 };
		const [tab] = joinLayout(treeWith([secret]), fields, { fieldAccess: () => "none" });
		expect(tab.sections[0].columns[0].fields[0].hidden).toBe(true);
	});

	it("takes the overrides of its fieldname", () => {
		const nickname = { fieldname: "nickname", fieldtype: "Data" };
		const [tab] = joinLayout(treeWith([nickname]), fields, {
			overrides: { nickname: { meta: { label: "Known As" } } },
		});
		expect(tab.sections[0].columns[0].fields[0].label).toBe("Known As");
	});
});

describe("joinLayout — decorate", () => {
	it("threads the decorator onto every joined field", () => {
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
			overrides: { first_name: { override: { hidden: true } } },
		});
		const [first, second] = tab.sections[0].columns[0].fields;
		expect(first.override).toEqual({ hidden: true });
		expect(second.override).toBeUndefined();
	});

	it("does not pre-apply the override — resolveLayout has the last word", () => {
		// The carrier is inert data at join time; applying it early would put it
		// back under `depends_on`, which re-ORs on every keystroke.
		const [tab] = joinLayout(treeWith(["first_name"]), fields, {
			overrides: { first_name: { override: { hidden: true } } },
		});
		expect(tab.sections[0].columns[0].fields[0].hidden).toBe(false);
	});

	it("ignores an override naming a field the layout does not render", () => {
		const [tab] = joinLayout(treeWith(["first_name"]), fields, {
			overrides: { gone: { override: { hidden: true } } },
		});
		expect(tab.sections[0].columns[0].fields).toHaveLength(1);
	});

	it("applies the build-time half straight onto the node", () => {
		// These are computed once and never recomputed, so there is nothing for
		// `resolveLayout` to re-decide and no carrier to ride.
		const [tab] = joinLayout(treeWith(["first_name"]), fields, {
			overrides: {
				first_name: { meta: { label: "Given name", placeholder: "Ada" } },
			},
		});
		expect(tab.sections[0].columns[0].fields[0]).toMatchObject({
			label: "Given name",
			placeholder: "Ada",
		});
	});

	it("merges a `ui` patch over whatever the decorator contributed", () => {
		const [tab] = joinLayout(treeWith(["first_name"]), fields, {
			decorate: () => ({ props: { variant: "outline" }, on: { click: () => {} } }),
			overrides: { first_name: { ui: { props: { variant: "subtle" } } } },
		});
		const { ui } = tab.sections[0].columns[0].fields[0];
		expect(ui?.props).toEqual({ variant: "subtle" });
		// The decorator's listeners survive — a patch replaces only what it names.
		expect(ui?.on?.click).toBeTypeOf("function");
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
			overrides: { secret: { override: { hidden: false } } },
		});
		expect(fieldOf(joined).permDenied).toBe(true);
		expect(fieldOf(resolveLayout(joined, {})).hidden).toBe(true);
	});

	it("a `read` denial survives an override that tries to un-lock it", () => {
		const joined = joinLayout(treeFor("secret"), fields, {
			fieldAccess: () => "read",
			overrides: { secret: { override: { readOnly: false } } },
		});
		expect(fieldOf(resolveLayout(joined, {})).readOnly).toBe(true);
	});

	it("grants the override when the reader has the permlevel", () => {
		const joined = joinLayout(treeFor("secret"), fields, {
			fieldAccess: () => "write",
			overrides: { secret: { override: { hidden: true } } },
		});
		expect(fieldOf(joined).permDenied).toBe(false);
		expect(fieldOf(resolveLayout(joined, {})).hidden).toBe(true);
	});
});

describe("joinLayout unplaced fields", () => {
	const meta: RawMetaField[] = [
		{ fieldname: "title", fieldtype: "Data", reqd: 1 },
		{ fieldname: "a_break", fieldtype: "Section Break" },
		{ fieldname: "city", fieldtype: "Data", depends_on: "eval:doc.title" },
		{ fieldname: "status", fieldtype: "Select", reqd: 1, default: "Open" },
		{ fieldname: "region", fieldtype: "Data", mandatory_depends_on: "eval:doc.city" },
		{ fieldname: "gallery", fieldtype: "Attachment Gallery" },
		{ fieldname: "internal", fieldtype: "Data", hidden: 1 },
		{ fieldname: "salary", fieldtype: "Currency", permlevel: 1 },
		{ fieldname: "code", fieldtype: "Data", reqd: 1 },
		{ fieldname: "items", fieldtype: "Table", options: "Item Row" },
	];
	const access = (field: RawMetaField) => (field.permlevel ? "none" : "write");
	const sectionMode = (rest = {}) => ({ fieldAccess: access, unplaced: { mode: "section" as const, ...rest } });

	function sections(schema: ReturnType<typeof joinLayout>) {
		return schema.flatMap((tab) =>
			tab.sections.map((section) => ({
				name: section.name,
				label: section.label,
				hideBorder: section.hideBorder,
				dependsOn: section.dependsOn,
				fields: section.columns.flatMap((column) => column.fields.map((field) => field.fieldname)),
			}))
		);
	}

	it("draws the data fields a row leaves out in More fields, last on the first tab, in meta order", () => {
		const tree: LayoutTree = [
			{ name: "one", sections: [{ name: "main", columns: [{ fields: ["title"] }] }] },
			{ name: "two", sections: [{ name: "later", columns: [{ fields: ["code"] }] }] },
		];
		const [first, second] = joinLayout(tree, meta, sectionMode());
		expect(first.sections.map((section) => section.name)).toEqual(["main", "more_fields"]);
		expect(sections([first])[1]).toEqual({
			name: "more_fields",
			label: "More fields",
			hideBorder: false,
			dependsOn: undefined,
			fields: ["city", "status", "region", "items"],
		});
		expect(first.sections[1].columns).toHaveLength(1);
		expect(first.sections[1].opened).toBe(true);
		expect(second.sections.map((section) => section.name)).toEqual(["later"]);
	});

	it("keeps each unplaced field's own depends_on", () => {
		const [tab] = joinLayout(treeWith(["title"]), meta, sectionMode());
		const city = tab.sections[1].columns[0].fields.find((field) => field.fieldname === "city");
		expect(city?.dependsOn).toBe("eval:doc.title");
	});

	it("skips the fields the row omits, and ignores an omitted name the meta no longer has", () => {
		const [tab] = joinLayout(
			treeWith(["title", "code"]),
			meta,
			sectionMode({ omitted: ["city", "region", "gone"] })
		);
		expect(sections([tab])[1].fields).toEqual(["status", "items"]);
	});

	it("draws an omitted field that is now mandatory with no default", () => {
		const [tab] = joinLayout(
			treeWith(["title", "city", "region", "items"]),
			meta,
			sectionMode({ omitted: ["code", "status"] })
		);
		expect(sections([tab])[1].fields).toEqual(["code"]);
	});

	it("counts a field the Side Panel row places as placed", () => {
		const [tab] = joinLayout(
			treeWith(["title", "code"]),
			meta,
			sectionMode({ placedElsewhere: ["status", "items"] })
		);
		expect(sections([tab])[1].fields).toEqual(["city", "region"]);
	});

	it("counts an inline field with a meta fieldname as placed", () => {
		const inline = { fieldname: "city", fieldtype: "Data", label: "Town" };
		const [tab] = joinLayout(treeWith(["title", "code", inline]), meta, sectionMode());
		expect(sections([tab])[1].fields).toEqual(["status", "region", "items"]);
	});

	it("draws no section when every field is placed or omitted", () => {
		const [tab] = joinLayout(
			treeWith(["title", "code", "city"]),
			meta,
			sectionMode({ omitted: ["status", "region", "items"] })
		);
		expect(tab.sections.map((section) => section.name)).toEqual(["main"]);
	});

	it("adds nothing without a rule, as for the meta fallback", () => {
		const [tab] = joinLayout(treeWith(["title"]), meta, { fieldAccess: access });
		expect(tab.sections.map((section) => section.name)).toEqual(["main"]);
	});

	it("names the section clear of a field or a section already named more_fields", () => {
		const tree: LayoutTree = [
			{ name: "one", sections: [{ name: "more_fields", columns: [{ fields: ["title"] }] }] },
		];
		const [tab] = joinLayout(tree, meta, sectionMode());
		expect(tab.sections.map((section) => section.name)).toEqual(["more_fields", "more_fields_2"]);
	});

	it("opens a tab for a row with none", () => {
		const [tab] = joinLayout([], meta, sectionMode());
		expect(sections([tab])[0].fields).toEqual(["title", "city", "status", "region", "code", "items"]);
	});

	it("adds only the mandatory fields a Quick Entry row leaves out, a conditional one under its condition", () => {
		const schema = joinLayout(treeWith(["city"]), meta, {
			fieldAccess: access,
			unplaced: { mode: "mandatory", omitted: ["title"] },
		});
		expect(sections(schema).slice(1)).toEqual([
			{ name: "more_fields", label: undefined, hideBorder: true, dependsOn: undefined, fields: ["title"] },
			{ name: "more_fields_2", label: undefined, hideBorder: true, dependsOn: "eval:doc.city", fields: ["region"] },
			{ name: "more_fields_3", label: undefined, hideBorder: true, dependsOn: undefined, fields: ["code"] },
		]);
	});

	it("shows a Quick Entry field with a default only under its mandatory condition", () => {
		const withDefault: RawMetaField[] = [
			{ fieldname: "kind", fieldtype: "Data", reqd: 1, default: "A", mandatory_depends_on: "eval:doc.x" },
		];
		const schema = joinLayout(treeWith([]), withDefault, { unplaced: { mode: "mandatory" } });
		expect(sections(schema)[1]).toMatchObject({ dependsOn: "eval:doc.x", fields: ["kind"] });
	});

	it("adds nothing to a Quick Entry row that places every mandatory field", () => {
		const schema = joinLayout(treeWith(["title", "region", "code"]), meta, {
			fieldAccess: access,
			unplaced: { mode: "mandatory" },
		});
		expect(sections(schema).map((section) => section.name)).toEqual(["main"]);
	});
});
