// What Customize allows on top of the Design replay, as `customize_edits.py` and `customize_state.py`
// check it on save. Plain data, so the working state still clones.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { EditorState } from "./editorSource";
import { fieldnameFromLabel } from "./fieldRules";
import { EditRefused } from "./layoutTree";

export interface CustomizeRules {
	/** The fields the app ships, an app's custom fields among them. */
	standard: string[];
	locks: Record<string, Record<string, string>>;
	/** The app's value under each of this site's Property Setters, by field and property. */
	appValues: Record<string, Record<string, unknown>>;
}

export function customizeRules(state: EditorState): CustomizeRules | null {
	if (state.mode !== "Customize") return null;
	const appValues: CustomizeRules["appValues"] = {};
	for (const setter of siteSetters(state)) {
		(appValues[setter.field_name!] ??= {})[setter.property] = setter.app_value;
	}
	return {
		standard: state.definition.fields.filter((field) => !siteCustom(field)).map((field) => field.fieldname),
		locks: state.locks ?? {},
		appValues,
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

export function refuseLocked(rules: CustomizeRules, fieldname: string, property: string) {
	const reason = rules.locks[fieldname]?.[property];
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
