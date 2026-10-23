// The Create dialog's pure parts: the prompt-name field, the defaults it seeds, the insert body
// and the values "Edit full form" carries.
import { mapField } from "@framework/ui/components/FormLayout/buildLayoutFromMeta";
import { fieldsToLayout } from "@framework/ui/components/FormLayout/fieldsToLayout";
import type { FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
import type { DoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { __ } from "@/i18n";

export const NEW_NAME = "__newname";

type Values = Record<string, any>;

/** A doctype named by prompt gets a mandatory name field at the top. */
export function withNameField(
	layout: FormLayoutSchema,
	meta: DoctypeMeta | null
): FormLayoutSchema {
	if (!meta || meta.autoname?.toLowerCase() !== "prompt") return layout;
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
	const [first, ...rest] = layout;
	return [{ ...first, sections: [...named[0].sections, ...first.sections] }, ...rest];
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
