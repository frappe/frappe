import { describe, expect, it } from "vitest";
import {
	carriedAnswers,
	copiedAnswers,
	holdsRoute,
	pendingDoctype,
	type EditorState,
} from "../editorSource";

const LAYOUT = [
	{
		name: "details",
		sections: [{ name: "main", columns: [{ name: "column", fields: ["subject", "status"] }] }],
	},
];

const SERIES_ANSWERS = { name: "Route Note", module: "Desk", custom: true, naming_rule: 'By "Naming Series" field' };

function source(): EditorState {
	return {
		doctype: "Task Note",
		mode: "Design",
		modes: ["Design"],
		base_version: { doctype: "", layouts: {}, app_layouts: {} },
		custom: 0,
		module: "Desk",
		app_title: "Frappe Framework",
		record_count: 3,
		value_counts: {},
		layouts: { Details: [{ name: null, layout: LAYOUT, omitted: [], source: "app" }] },
		definition: {
			name: "Task Note",
			module: "Desk",
			naming_rule: "By fieldname",
			autoname: "field:subject",
			owner: "Administrator",
			fields: [
				{ name: "row1", parent: "Task Note", fieldname: "subject", fieldtype: "Data" },
				{ name: "row2", parent: "Task Note", fieldname: "status", fieldtype: "Select" },
			],
		} as unknown as EditorState["definition"],
	};
}

describe("a new DocType's first answers", () => {
	it("come from the values routeForNew carried", () => {
		expect(
			carriedAnswers({ __newname: "Route", module: "Desk", custom: "0", naming_rule: "Random" })
		).toEqual({
			answers: { name: "Route", module: "Desk", custom: false, naming_rule: "Random" },
			copyOf: null,
		});
		expect(carriedAnswers({ __copy_of: "Task Note" })).toEqual({ answers: {}, copyOf: "Task Note" });
	});

	it("take a duplicate's module, kind and naming rule, but not its name", () => {
		expect(copiedAnswers(source())).toEqual({
			module: "Desk",
			custom: false,
			naming_rule: "By fieldname",
		});
	});
});

describe("a pending DocType", () => {
	it("starts with one Title field when it copies nothing", () => {
		const state = pendingDoctype({ name: "Route", module: "Desk", custom: true, naming_rule: "Random" });
		expect(state.definition.fields.map((field) => field.fieldname)).toEqual(["title"]);
		expect([state.pending, state.definition.custom]).toEqual([true, 1]);
	});

	it("starts with the System Manager rule its insert would add, so the table shows what the save makes", () => {
		const state = pendingDoctype({ name: "Route", module: "Desk", custom: true, naming_rule: "Random" });
		expect(state.definition.permissions).toEqual([
			{
				role: "System Manager",
				permlevel: 0,
				read: 1,
				write: 1,
				create: 1,
				delete: 1,
				report: 1,
				export: 1,
				share: 1,
				print: 1,
				email: 1,
			},
		]);
	});

	it("names its records by the dialog's naming rule", () => {
		const autoname = (naming_rule: string) =>
			pendingDoctype({ name: "Route", module: "Desk", custom: true, naming_rule }).definition.autoname;
		expect(["By fieldname", "Set by user", "Autoincrement", 'By "Naming Series" field', "Random", "UUID"].map(autoname)).toEqual([
			"field:title",
			"Prompt",
			"autoincrement",
			"naming_series:",
			"hash",
			"UUID",
		]);
	});

	it("starts with a placed naming_series field when a series names its records", () => {
		const state = pendingDoctype({ name: "Route", module: "Desk", custom: true, naming_rule: 'By "Naming Series" field' });
		expect(state.definition.fields[0]).toMatchObject({
			fieldname: "naming_series",
			fieldtype: "Select",
			reqd: 1,
			options: "ROUT-.#####",
			default: "ROUT-.#####",
		});
		expect(state.layouts.Details?.[0].layout[0].sections[0].columns[0].fields).toEqual(["naming_series", "title"]);
	});

	it("gives a duplicate the naming_series field its new rule needs, leaving the source's layout as is", () => {
		const state = pendingDoctype(SERIES_ANSWERS, source());
		expect(state.definition.fields.map((field) => field.fieldname)).toEqual(["naming_series", "subject", "status"]);
		expect(state.definition.fields[0].options).toBe("RN-.#####");
		expect(state.layouts.Details?.[0].layout[0].sections[0].columns[0].fields).toEqual(["naming_series", "subject", "status"]);
		expect(LAYOUT[0].sections[0].columns[0].fields).toEqual(["subject", "status"]);
	});

	it("makes a column for the naming_series field when the duplicate's first tab has no section", () => {
		const bare = source();
		bare.layouts.Details![0].layout = [
			{ name: "empty", sections: [] },
			{ name: "more", sections: [{ name: "section_1", columns: [{ name: "column", fields: ["subject"] }] }] },
		];
		const state = pendingDoctype(SERIES_ANSWERS, bare);
		expect(state.layouts.Details?.[0].layout[0]).toEqual({
			name: "empty",
			sections: [{ name: "section_2", columns: [{ name: "column_1", fields: ["naming_series"] }] }],
		});
		expect(bare.layouts.Details![0].layout[0].sections).toEqual([]);
	});

	it("makes a column for the naming_series field when the duplicate's first section has none", () => {
		const bare = source();
		bare.layouts.Details![0].layout = [{ name: "details", sections: [{ name: "main", columns: [] }] }];
		const state = pendingDoctype(SERIES_ANSWERS, bare);
		expect(state.layouts.Details?.[0].layout[0].sections[0]).toEqual({
			name: "main",
			columns: [{ name: "column_1", fields: ["naming_series"] }],
		});
	});

	it("names a duplicate at random when no field can give its name", () => {
		const bare = source();
		bare.definition.naming_rule = "Random";
		bare.definition.fields = [{ fieldname: "notes", fieldtype: "Text" } as EditorState["definition"]["fields"][number]];
		const state = pendingDoctype({ name: "Route Note", module: "Desk", custom: true, naming_rule: "By fieldname" }, bare);
		expect(state.definition).toMatchObject({ naming_rule: "Random", autoname: "hash" });
	});

	it("copies a duplicate's fields and layout, without the source's record identity", () => {
		const answers = { name: "Route Note", module: "Desk", custom: true, naming_rule: "By fieldname" };
		const state = pendingDoctype(answers, source());
		expect(state.doctype).toBe("Route Note");
		expect(state.layouts.Details?.[0].layout).toEqual(LAYOUT);
		expect(state.definition).toMatchObject({ name: "Route Note", custom: 1, autoname: "field:subject" });
		expect(state.definition).not.toHaveProperty("owner");
		expect(state.definition.fields).toEqual([
			{ fieldname: "subject", fieldtype: "Data" },
			{ fieldname: "status", fieldtype: "Select" },
		]);
		const renamed = pendingDoctype({ ...answers, naming_rule: "Random" }, source());
		expect(renamed.definition.autoname).toBe("hash");
	});
});

describe("a route that names the open DocType", () => {
	const open = { doctype: "Task Note", mode: "Design" } as EditorState;

	it("loads nothing when the DocType and mode are the ones held", () => {
		expect(holdsRoute(open, "Task Note", undefined)).toBe(true);
		expect(holdsRoute(open, "Task Note", "Design")).toBe(true);
	});

	it("loads when the DocType, the mode or the page's state differs", () => {
		expect(holdsRoute(open, "Other", undefined)).toBe(false);
		expect(holdsRoute(open, "Task Note", "Customize")).toBe(false);
		expect(holdsRoute(null, "Task Note", undefined)).toBe(false);
	});
});
