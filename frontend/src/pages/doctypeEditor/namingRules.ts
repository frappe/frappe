// The Naming section's rules: which one an autoname is, the properties picking one sets, and why
// a rule cannot be picked now.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import type { SettingsState } from "./settingsModel";

export type Rule = "hash" | "uuid" | "autoincrement" | "field" | "format" | "naming_series" | "prompt" | "script";

export const RULES: { value: Rule; label: string; help: string }[] = [
	{ value: "hash", label: "Random ID", help: "Like 8f3k2a91c0." },
	{ value: "uuid", label: "UUID", help: "Like 0190a6b2-7c1e-7d3a-9f4b-2c8e5d1a6f03." },
	{ value: "autoincrement", label: "Number in order", help: "1, 2, 3, and on." },
	{ value: "field", label: "From a field", help: "The value of one field, like a store's name." },
	{ value: "format", label: "By pattern", help: "Text, dates and a counter, like ST-2026-00042." },
	{ value: "naming_series", label: "Naming Series", help: "The person picks a series; each series counts on its own." },
	{ value: "prompt", label: "Ask for it on create", help: "The person who creates a record types its name." },
	{ value: "script", label: "Set by the app's code", help: "The DocType's Python code names each record." },
];

/** The `naming_rule` each rule writes next to its autoname. */
const NAMING_RULE: Record<Rule, string> = {
	hash: "Random",
	uuid: "UUID",
	autoincrement: "Autoincrement",
	field: "By fieldname",
	format: "Expression",
	naming_series: 'By "Naming Series" field',
	prompt: "Set by user",
	script: "By script",
};

/** Rules the list shows only while they are the rule: they are not offered as a choice. */
export const SHOWN_WHEN_CURRENT: Rule[] = ["uuid", "script"];

export function ruleOf(properties: Record<string, unknown>): Rule {
	const autoname = String(properties.autoname ?? "").trim();
	const lower = autoname.toLowerCase();
	if (properties.naming_rule === "By script") return "script";
	if (!autoname || lower === "hash") return "hash";
	if (lower === "uuid") return "uuid";
	if (lower === "autoincrement") return "autoincrement";
	if (lower === "prompt") return "prompt";
	if (lower.startsWith("field:")) return "field";
	if (lower.startsWith("naming_series:")) return "naming_series";
	if (lower.startsWith("format:") || autoname.includes(".")) return "format";
	return "script";
}

/** Field types a record's name can come from. */
export const NAMEABLE_TYPES = ["Data", "Link", "Select", "Int", "Dynamic Link", "Read Only"];

/** The autoname the New DocType dialog's naming rule starts with; "By fieldname" names by `fieldname`. */
export function autonameOf(namingRule: string, fieldname: string): string {
	const rule = (Object.keys(NAMING_RULE) as Rule[]).find((one) => NAMING_RULE[one] === namingRule);
	if (rule === "field") return `field:${fieldname}`;
	return rule ? DIALOG_AUTONAME[rule] ?? "" : "";
}

const DIALOG_AUTONAME: Partial<Record<Rule, string>> = {
	hash: "hash",
	uuid: "UUID",
	autoincrement: "autoincrement",
	naming_series: "naming_series:",
	prompt: "Prompt",
};

/** "Sales Order" → "SO", "Task" → "TASK": a series' first part. */
export function seriesAbbreviation(doctype: string): string {
	const words = doctype.split(/[\s_-]+/).filter(Boolean);
	const short = words.length > 1 ? words.map((word) => word[0]).join("") : (words[0] ?? "").slice(0, 4);
	return short.toUpperCase() || "REC";
}

/** "By pattern"'s first pattern: a dot series, v1's "Expression", counting under its own prefix. */
export function patternSeed(doctype: string): string {
	return `${seriesAbbreviation(doctype)}-.#####`;
}

/** The naming_series field a new DocType named by series starts with: one series, its default. */
export function seriesField(doctype: string): RawMetaField {
	const series = `${seriesAbbreviation(doctype)}-.#####`;
	return {
		fieldname: "naming_series",
		label: "Series",
		fieldtype: "Select",
		reqd: 1,
		options: series,
		default: series,
	} as RawMetaField;
}

/** Why a typed pattern cannot be "By pattern"'s autoname, or "": without a dot, "ST-#####" is no pattern frappe reads. */
export function patternRefusal(autoname: string): string {
	if (ruleOf({ autoname }) === "format") return "";
	return __("A pattern needs a dot between its parts, as in ST-.#####");
}

/** A `format:` pattern is v1's "Expression (old style)"; a dotted one ("ST-.#####") its "Expression". */
export function namingProperties(autoname: string): { autoname: string; naming_rule: string } {
	const rule = ruleOf({ autoname });
	const braced = rule === "format" && autoname.toLowerCase().startsWith("format:");
	return { autoname, naming_rule: braced ? "Expression (old style)" : NAMING_RULE[rule] };
}

/** Why the rule cannot be picked now; "" when it can. */
export function ruleRefusal(settings: SettingsState, fields: RawMetaField[], rule: Rule): string {
	const current = ruleOf(settings.properties);
	if (rule === current) return "";
	if (current === "script") return __("The app's code names each record. Change it there.");
	const savedAutoincrement = ruleOf({ autoname: settings.savedAutoname }) === "autoincrement";
	if ((rule === "autoincrement") !== savedAutoincrement) {
		const refusal = autoincrementRefusal(settings);
		if (refusal) return refusal;
	}
	if (rule === "naming_series" && settings.app && !fields.some((field) => field.fieldname === "naming_series")) {
		return __("Needs a Naming Series field. Add one in the Editor first.");
	}
	return "";
}

function autoincrementRefusal(settings: SettingsState): string {
	if (settings.app) return __("Customize cannot switch to or from Number in order.");
	if (settings.pending || !settings.records || Number(settings.properties.issingle)) return "";
	return __("Only while there are no records: this DocType has {0}.", [String(settings.records)]);
}
