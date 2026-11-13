// What Customize allows on top of the Design replay, as `customize_edits.py` and `customize_state.py`
// check it on save. Plain data, so the working state still clones.
import { NO_VALUE } from "@framework/ui/FormLayout/noValueFields";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import type { EditorState } from "./editorSource";
import { fieldnameFromLabel } from "./fieldRules";
import { EditRefused } from "./layoutTree";

export interface CustomizeRules {
	/** The fields the app ships, an app's custom fields among them. */
	standard: string[];
	locks: Record<string, Record<string, string>>;
	/** The app's value under each of this site's Property Setters, by field and property. */
	appValues: Record<string, Record<string, unknown>>;
	/** Each standard field's type as loaded, which `locks` were made for. */
	types: Record<string, string>;
	istable: boolean;
}

export function customizeRules(state: EditorState): CustomizeRules | null {
	if (state.mode !== "Customize") return null;
	const appValues: CustomizeRules["appValues"] = {};
	for (const setter of siteSetters(state)) {
		(appValues[setter.field_name!] ??= {})[setter.property] = setter.app_value;
	}
	const standard = state.definition.fields.filter((field) => !siteCustom(field));
	return {
		standard: standard.map((field) => field.fieldname),
		locks: state.locks ?? {},
		appValues,
		types: Object.fromEntries(standard.map((field) => [field.fieldname, field.fieldtype])),
		istable: Boolean(state.definition.istable),
	};
}

/** The site's own field changes; an app's setters count as the app's. */
export function siteSetters(state: EditorState) {
	return (state.property_setters ?? []).filter(
		(setter) => setter.doctype_or_field === "DocField" && setter.field_name && !setter.is_system_generated,
	);
}

/** A field this site added; a custom field an app made counts as standard, as in Customize Form. */
export function siteCustom(field: RawMetaField): boolean {
	const flags = field as { is_custom_field?: number; is_system_generated?: number };
	return Boolean(flags.is_custom_field && !flags.is_system_generated);
}

export function customFieldname(label: string): string {
	const fieldname = fieldnameFromLabel(label);
	return fieldname.startsWith("custom_") ? fieldname : `custom_${fieldname}`;
}

/** Customize Form checks options against the field's type at save, so a Select turned Data takes new ones. */
const OPTIONS_CHANGE = ["Read Only", "HTML", "Data"];

/** `supports_translation` and `get_fields_not_allowed_in_list_view`, which the save checks on the new type. */
const TRANSLATABLE = ["Data", "Select", "Text", "Small Text", "Text Editor"];
const NOT_IN_LIST = new Set([...NO_VALUE, "Table", "Table MultiSelect"]);
const TYPE_LOCKS: Record<string, (fieldtype: string, istable: boolean) => string | undefined> = {
	translatable: (type) =>
		TRANSLATABLE.includes(type) ? undefined : __("A {0} field cannot be translated.", [__(type)]),
	in_list_view: (type, istable) =>
		NOT_IN_LIST.has(type) && !(istable && ["Button", "HTML"].includes(type))
			? __("A {0} field cannot show in the list view.", [__(type)])
			: undefined,
};

export function lockOf(rules: CustomizeRules, field: RawMetaField, property: string): string | undefined {
	const loaded = rules.types[field.fieldname];
	const typeLock = TYPE_LOCKS[property];
	if (typeLock && loaded && loaded !== field.fieldtype) return typeLock(field.fieldtype, rules.istable);
	if (property !== "options") return rules.locks[field.fieldname]?.[property];
	if (!rules.standard.includes(field.fieldname) || OPTIONS_CHANGE.includes(field.fieldtype)) return undefined;
	return __("Options of a {0} field cannot be changed.", [__(field.fieldtype)]);
}

export function refuseLocked(rules: CustomizeRules, field: RawMetaField, property: string) {
	const reason = lockOf(rules, field, property);
	if (reason) throw new EditRefused(reason);
}

export function refuseStandard(rules: CustomizeRules, fieldname: string, message: string) {
	if (rules.standard.includes(fieldname)) throw new EditRefused(message, [fieldname]);
}

/** A reset deletes the site's setter, so the field takes the app's value back. */
export function appValue(rules: CustomizeRules, loaded: RawMetaField, property: string): unknown {
	const values = rules.appValues[loaded.fieldname];
	if (values && property in values) return values[property];
	return (loaded as unknown as Record<string, unknown>)[property];
}

/** Setter values are text and unset checks are absent, so a check's "0", 0 and undefined read the same. */
export function sameValue(a: unknown, b: unknown, check: boolean): boolean {
	return blankAsEmpty(a, check) === blankAsEmpty(b, check);
}

function blankAsEmpty(value: unknown, check: boolean): string {
	if (value == null || (check && (value === false || value === 0 || value === "0"))) return "";
	return String(value);
}
