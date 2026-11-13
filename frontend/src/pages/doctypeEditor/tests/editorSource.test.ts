import { describe, expect, it } from "vitest";
import {
	carriedAnswers,
	copiedAnswers,
	pendingDoctype,
	type EditorState,
} from "../editorSource";

const LAYOUT = [
	{
		name: "details",
		sections: [{ name: "main", columns: [{ name: "column", fields: ["subject", "status"] }] }],
	},
];

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
