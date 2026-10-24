// The values a new record starts with and sends: the prompt-name field, the defaults, the
// query the full page reads, the values Edit full form carries, and the insert body.
import { describe, expect, it } from "vitest";
import type { FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
import type { DoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { NEW_NAME } from "@framework/ui/utils/naming";
import { layoutFromFields } from "@/recordPage/formDialogLayout";
import {
	fieldDefaults,
	fillEmpty,
	insertBody,
	queryValues,
	typedValues,
	withNameField,
} from "@/newRecordValues";

const LAYOUT = layoutFromFields([
	{ fieldname: "title", fieldtype: "Data", label: "Title" },
	{ fieldname: "status", fieldtype: "Select", label: "Status", options: "Open\nClosed" },
]);

function fieldnames(layout: FormLayoutSchema): string[] {
	return layout.flatMap((tab) =>
		tab.sections.flatMap((section) => section.columns.flatMap((column) => column.fields.map((field) => field.fieldname)))
	);
}

function firstField(layout: FormLayoutSchema) {
	return layout[0].sections[0].columns[0].fields[0];
}

describe("withNameField", () => {
	it("puts a mandatory name field above the layout of a doctype named by prompt", () => {
		const layout = withNameField(LAYOUT, { name: "Territory", autoname: "Prompt" });

		expect(fieldnames(layout)).toEqual([NEW_NAME, "title", "status"]);
		expect(firstField(layout)).toMatchObject({ fieldname: "__newname", fieldtype: "Data", reqd: true, label: "Territory Name" });
	});

	it("gives the name field alone when the layout is empty", () => {
		const layout = withNameField([], { name: "Territory", autoname: "prompt" });

		expect(fieldnames(layout)).toEqual([NEW_NAME]);
		expect(firstField(layout).reqd).toBe(true);
	});

	it("leaves the layout alone for any other naming rule, or before the meta loads", () => {
		for (const meta of [{ name: "Lead", autoname: "naming_series:" }, { name: "Lead" }, null] as (DoctypeMeta | null)[]) {
			expect(withNameField(LAYOUT, meta)).toBe(LAYOUT);
		}
	});
});

describe("fieldDefaults", () => {
	it("keeps the server's values for the doctype's own fields only", () => {
		const meta: DoctypeMeta = {
			name: "Lead",
			fields: [
				{ fieldname: "status", fieldtype: "Select", label: "Status" },
				{ fieldname: "title", fieldtype: "Data", label: "Title" },
				{ fieldname: "source", fieldtype: "Data", label: "Source" },
			],
		};
		const newDoc = { doctype: "Lead", name: "new-lead-1", __islocal: 1, owner: "test@example.com", status: "Open", title: null };

		expect(fieldDefaults(newDoc, meta)).toEqual({ status: "Open" });
	});

	it("is empty without a meta", () => {
		expect(fieldDefaults({ status: "Open" }, null)).toEqual({});
	});
});

describe("fillEmpty", () => {
	it("fills only the fields still empty", () => {
		const doc = { title: "Typed", status: null, source: undefined };
		const filled = fillEmpty(doc, { title: "Default", status: "Open", source: "Web" });

		expect(filled).toEqual({ title: "Typed", status: "Open", source: "Web" });
		expect(doc.status).toBeNull();
	});
});

describe("insertBody", () => {
	it("lays the form data over the caller's values", () => {
		expect(insertBody({ company: "Acme", status: "Open" }, { status: "Closed", title: "Big deal" })).toEqual({
			company: "Acme",
			status: "Closed",
			title: "Big deal",
		});
	});

	it("never sends name, whether the caller or the form carries it", () => {
		expect(insertBody({ name: "LEAD-9", company: "Acme" }, { name: "LEAD-10", title: "x" })).toEqual({
			company: "Acme",
			title: "x",
		});
	});

	it("sends a prompt doctype's typed name as __newname", () => {
		expect(insertBody({}, { [NEW_NAME]: "North", parent_territory: "All" })).toEqual({
			__newname: "North",
			parent_territory: "All",
		});
	});
});

describe("typedValues", () => {
	it("carries the caller's values and what the person typed, not what repeats a default", () => {
		const typed = typedValues(
			{ company: "Acme" },
			{ title: "Big deal", status: "Open", source: "", tags: [], notes: null },
			{ status: "Open" }
		);

		expect(typed).toEqual({ company: "Acme", title: "Big deal" });
	});

	it("keeps a value the person changed away from its default", () => {
		expect(typedValues({}, { status: "Closed" }, { status: "Open" })).toEqual({ status: "Closed" });
	});

	it("carries the form's value, not the caller's, for a field the form shows", () => {
		const values = { customer_type: "Individual", company: "Acme" };
		const defaults = { customer_type: "Company" };

		expect(typedValues(values, { customer_type: "Company" }, defaults)).toEqual({ company: "Acme" });
		expect(typedValues(values, { customer_type: "" }, defaults)).toEqual({ company: "Acme" });
	});

	it("drops name from what it carries", () => {
		expect(typedValues({ name: "LEAD-9" }, { name: "LEAD-10", title: "x" }, {})).toEqual({ title: "x" });
	});
});

describe("queryValues", () => {
	const meta = {
		name: "Sales Invoice",
		autoname: "naming_series:",
		fields: [
			{ fieldname: "customer", fieldtype: "Link" },
			{ fieldname: "is_return", fieldtype: "Check" },
			{ fieldname: "qty", fieldtype: "Int" },
			{ fieldname: "grand_total", fieldtype: "Currency" },
			{ fieldname: "items", fieldtype: "Table" },
		],
	} as unknown as DoctypeMeta;

	it("keeps the doctype's own fields, typed, and a table's rows from JSON", () => {
		const rows = [{ item_code: "PEN", qty: 2 }];
		const query = {
			customer: "Acme",
			is_return: "1",
			qty: "3",
			grand_total: "12.5",
			items: JSON.stringify(rows),
			owner: "intruder",
		};

		expect(queryValues(query, meta)).toEqual({ customer: "Acme", is_return: 1, qty: 3, grand_total: 12.5, items: rows });
	});

	it("reads a checkbox that Edit full form carried as true or false", () => {
		const query = (routeValues: Record<string, unknown>) =>
			Object.fromEntries(Object.entries(routeValues).map(([key, value]) => [key, String(value)]));

		expect(queryValues(query({ is_return: true }), meta)).toEqual({ is_return: 1 });
		expect(queryValues(query({ is_return: false }), meta)).toEqual({ is_return: 0 });
	});

	it("drops a number that is empty or not a number, and a field that holds no value", () => {
		const withBreak = { ...meta, fields: [...meta.fields, { fieldname: "details", fieldtype: "Section Break" }] } as DoctypeMeta;

		expect(queryValues({ qty: "", grand_total: "abc", details: "x" }, withBreak)).toEqual({});
	});

	it("drops a table whose value is not a JSON list, and takes the first of a repeated key", () => {
		expect(queryValues({ items: "not json", customer: ["Acme", "Other"] }, meta)).toEqual({ customer: "Acme" });
		expect(queryValues({ items: '{"item_code":"PEN"}' }, meta)).toEqual({});
	});

	it("keeps a prompt name only for a doctype named by prompt", () => {
		expect(queryValues({ [NEW_NAME]: "SI-X" }, meta)).toEqual({});
		expect(queryValues({ [NEW_NAME]: "SI-X" }, { ...meta, autoname: "Prompt" })).toEqual({ [NEW_NAME]: "SI-X" });
	});
});

describe("queryValues with the layout", () => {
	const meta = {
		name: "Customer",
		fields: [
			{ fieldname: "customer_name", fieldtype: "Data" },
			{ fieldname: "credit_days", fieldtype: "Data", read_only: 1 },
		],
	} as unknown as DoctypeMeta;
	const layout = layoutFromFields([
		{ fieldname: "customer_name", fieldtype: "Data" },
		{ fieldname: "address_line1", fieldtype: "Data" },
		{ fieldname: "credit_days", fieldtype: "Int" },
	]);

	it("keeps the layout's inline fields, typed by the layout over the meta", () => {
		const query = { customer_name: "Acme", address_line1: "1 Main St", credit_days: "30", owner: "intruder" };

		expect(queryValues(query, meta, layout)).toEqual({ customer_name: "Acme", address_line1: "1 Main St", credit_days: 30 });
		expect(queryValues(query, meta)).toEqual({ customer_name: "Acme", credit_days: "30" });
	});
});
