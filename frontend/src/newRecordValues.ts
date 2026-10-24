// The values a new record starts with and sends: the server defaults, the prompt-name field, the
// query the full page reads, the values "Edit full form" carries, and the insert body.
import { runMethod } from "@framework/ui/api";
import { mapField } from "@framework/ui/components/FormLayout/buildLayoutFromMeta";
import { layoutFields, NO_VALUE } from "@framework/ui/components/FormLayout/newRowValues";
import { fieldsToLayout } from "@framework/ui/components/FormLayout/fieldsToLayout";
import type { FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
import type { DoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { isNamedByPrompt, NEW_NAME } from "@framework/ui/utils/naming";
import type { LocationQuery } from "vue-router";
import { __ } from "@/i18n";

const GET_NEW_DOC = "frappe.desk.form.load.get_new_doc";

type Values = Record<string, any>;

const TABLES = new Set(["Table", "Table MultiSelect"]);

const INTEGERS = new Set(["Int", "Long Int", "Check"]);
const DECIMALS = new Set(["Float", "Currency", "Percent", "Rating", "Duration"]);

/** A doctype named by prompt gets a mandatory name field at the top. */
export function withNameField(
	layout: FormLayoutSchema,
	meta: DoctypeMeta | null
): FormLayoutSchema {
	if (!isNamedByPrompt(meta)) return layout;
	const named = fieldsToLayout([
		mapField(
			{
				fieldname: NEW_NAME,
				fieldtype: "Data",
				label: __("{0} Name", [__(meta.name)]),
				reqd: 1,
			},
			{}
		),
	]);
	if (!layout.length) return named;
	// Named, so a record page's form join does not fold it into an unnamed first section.
	const section = { ...named[0].sections[0], name: NEW_NAME };
	const [first, ...rest] = layout;
	return [{ ...first, sections: [section, ...first.sections] }, ...rest];
}

/** The query's values for the doctype's own fields and its prompt name, typed; a table's is JSON. */
export function queryValues(query: LocationQuery, meta: DoctypeMeta): Values {
	const values = typedQuery(query, meta.fields);
	const name = queryText(query[NEW_NAME]);
	if (name != null && isNamedByPrompt(meta)) values[NEW_NAME] = name;
	return values;
}

/** The query's values for the layout's inline fields, which the meta does not type. */
export function inlineQueryValues(
	query: LocationQuery,
	layout: FormLayoutSchema,
	meta: DoctypeMeta
): Values {
	const own = new Set(meta.fields.map((field) => field.fieldname));
	return typedQuery(
		query,
		layoutFields(layout).filter((field) => !own.has(field.fieldname))
	);
}

function typedQuery(
	query: LocationQuery,
	fields: { fieldname: string; fieldtype: string }[]
): Values {
	const values: Values = {};
	for (const { fieldname, fieldtype } of fields) {
		const text = queryText(query[fieldname]);
		const value = text == null ? undefined : typed(text, fieldtype);
		if (value !== undefined) values[fieldname] = value;
	}
	return values;
}

function queryText(given: LocationQuery[string] | undefined): string | null | undefined {
	return Array.isArray(given) ? given[0] : given;
}

/** Undefined for a value the field cannot hold, so the server default stays. */
function typed(text: string, fieldtype: string): unknown {
	if (NO_VALUE.has(fieldtype)) return undefined;
	if (fieldtype === "Check" && (text === "true" || text === "false")) return text === "true" ? 1 : 0;
	if (INTEGERS.has(fieldtype) || DECIMALS.has(fieldtype)) return number(text, fieldtype);
	if (!TABLES.has(fieldtype)) return text;
	try {
		const rows = JSON.parse(text);
		return Array.isArray(rows) ? rows : undefined;
	} catch {
		return undefined;
	}
}

function number(text: string, fieldtype: string): number | undefined {
	const value = Number(text);
	if (text.trim() === "" || !Number.isFinite(value)) return undefined;
	return INTEGERS.has(fieldtype) ? Math.trunc(value) : value;
}

/** The server's new document for this user and today. */
export async function fetchNewDocument(doctype: string): Promise<Values> {
	const { data } = await runMethod<Values>(GET_NEW_DOC, { doctype }, { http: "GET" });
	return data;
}

/** The server's new document, cut to the doctype's own fields. */
export function fieldDefaults(newDoc: Values, meta: DoctypeMeta | null): Values {
	const defaults: Values = {};
	for (const field of meta?.fields ?? [])
		if (newDoc[field.fieldname] != null) defaults[field.fieldname] = newDoc[field.fieldname];
	return defaults;
}

/** Fills the fields still empty; the caller's values and the person's edits stay. */
export function fillEmpty(doc: Values, defaults: Values): Values {
	const filled = { ...doc };
	for (const [fieldname, value] of Object.entries(defaults))
		if (filled[fieldname] == null) filled[fieldname] = value;
	return filled;
}

/** The caller's values under the form's. Never `name`: the insert would skip the naming rule. */
export function insertBody(values: Values, data: Values): Values {
	const { name: _name, ...body } = { ...values, ...data };
	return body;
}

/** The caller's values for fields the form lacks, and form values that differ from a default. */
export function typedValues(values: Values, data: Values, defaults: Values): Values {
	const typed: Values = { ...values };
	for (const [fieldname, value] of Object.entries(data)) {
		delete typed[fieldname];
		if (!isEmpty(value) && value !== defaults[fieldname]) typed[fieldname] = value;
	}
	delete typed.name;
	return typed;
}

function isEmpty(value: unknown): boolean {
	if (Array.isArray(value)) return value.length === 0;
	return value == null || value === "";
}
