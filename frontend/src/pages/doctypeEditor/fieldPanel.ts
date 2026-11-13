// What the field panel shows for one field: its type choices, the notes under Type and
// Fieldname, the remove question and the property groups. The panel's .vue draws these.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { __, __n } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { reqdInConditional } from "./editorModel";
import { allowedFieldtypes } from "./fieldRules";
import { COMMON_TYPES, FIELDTYPE_GROUPS, typeName } from "./fieldtypes";

export interface TypeGroup {
	label: string;
	types: { name: string; disabled: boolean }[];
}

/** A saved field whose column holds values keeps to the types that keep them; the rest show disabled. */
export function typeGroups(canvas: DesignCanvas, fieldname: string): { groups: TypeGroup[]; more: TypeGroup[] } {
	const saved = canvas.savedField(fieldname);
	const count = canvas.valueCount(fieldname);
	const allowed = saved ? allowedFieldtypes(saved, true, count) : "any";
	if (allowed === "any") {
		const more = FIELDTYPE_GROUPS.map((group) => ({
			label: group.label,
			types: group.types.filter((name) => !COMMON_TYPES.includes(name)).map(enabled),
		}));
		return { groups: [{ label: "", types: COMMON_TYPES.map(enabled) }], more };
	}
	const keeps = [saved!.fieldtype, ...allowed];
	if (keeps.includes("Data")) keeps.splice(keeps.indexOf("Data") + 1, 0, "Email");
	const others = COMMON_TYPES.filter((name) => !keeps.includes(name));
	return {
		groups: [
			{ label: __n("Keeps its {0} value", "Keeps its {0} values", count, [count]), types: keeps.map(enabled) },
			{
				label: __n("Not while {0} record holds a value", "Not while {0} records hold a value", count, [count]),
				types: others.map((name) => ({ name, disabled: true })),
			},
		],
		more: [],
	};
}

/** Under Type, once a saved field's type changed. */
export function typeNote(canvas: DesignCanvas, field: RawMetaField): string {
	const saved = canvas.savedField(field.fieldname);
	if (!saved || saved.fieldtype === field.fieldtype) return "";
	const count = canvas.valueCount(field.fieldname);
	return count
		? __n(
				"The column changes type on save. Its {0} value is kept.",
				"The column changes type on save. Its {0} values are kept.",
				count,
				[count],
			)
		: __("The column changes type on save. No record holds a value in it.");
}

/** A saved field trades the fieldname, which has its own row, for its value count. */
export function subtitle(canvas: DesignCanvas, field: RawMetaField): string {
	const type = __(typeName(field.fieldtype, field.options));
	if (!canvas.savedName(field.fieldname)) return `${type} · ${field.fieldname}`;
	const count = canvas.valueCount(field.fieldname);
	return `${type} · ${__n("{0} value", "{0} values", count, [count])}`;
}

/** A new field's fieldname follows its label; a saved one renames on a custom DocType only. */
export function fieldnameMode(canvas: DesignCanvas, fieldname: string): "follows" | "renamable" | "locked" {
	if (!canvas.savedName(fieldname)) return "follows";
	return canvas.base.standard ? "locked" : "renamable";
}

/** The confirm a remove asks; none for a field added since the save, which has no column. */
export function removeQuestion(canvas: DesignCanvas, field: RawMetaField): string | null {
	if (!canvas.savedName(field.fieldname)) return null;
	const count = canvas.valueCount(field.fieldname);
	const label = field.label || field.fieldname;
	const leaves = __("{0} also leaves every layout of {1}.", [label, canvas.state.doctype]);
	const stays = count
		? __n(
				"Its column and the {0} value in it stay in the database, but no form, list or report shows them.",
				"Its column and the {0} values in it stay in the database, but no form, list or report shows them.",
				count,
				[count],
			)
		: __("Its column stays in the database, but no form, list or report shows it.");
	return `${stays} ${leaves}`;
}

/** The amber note for a mandatory field a condition can hide, naming the container that hides it. */
export function reqdWarning(canvas: DesignCanvas, fieldname: string): string {
	const found = reqdInConditional(canvas.working.value).find((one) => one.fieldname === fieldname);
	if (!found) return "";
	const containers = canvas.tabs.value.flatMap((tab) => [
		tab,
		...tab.sections.flatMap((section) => [section, ...section.columns]),
	]);
	const container = containers.find((one) => one.name === found.container);
	return __(
		"Mandatory, but it sits in “{0}”, which has a condition. When the condition hides it, the save still asks for it.",
		[container?.label || found.container],
	);
}

export interface PanelProperty {
	key: string;
	label: string;
	type: "check" | "int";
	placeholder?: string;
	only?: (field: RawMetaField, canvas: DesignCanvas) => boolean;
}

const NUMERIC = ["Int", "Float", "Currency", "Percent"];

/** The plain properties, grouped; the rules, Fetch from and link filters come with #47279. */
export const PROPERTY_GROUPS: { label: string; properties: PanelProperty[] }[] = [
	{
		label: "Display",
		properties: [
			{ key: "hidden", label: "Hidden", type: "check" },
			{ key: "read_only", label: "Read only", type: "check" },
			{ key: "bold", label: "Bold", type: "check" },
			{ key: "print_hide", label: "Hide in print", type: "check" },
			{ key: "report_hide", label: "Hide in reports", type: "check" },
			{
				key: "allow_on_submit",
				label: "Edit after submit",
				type: "check",
				only: (_field, canvas) => Boolean(canvas.state.definition.is_submittable),
			},
			{ key: "translatable", label: "Translatable", type: "check" },
		],
	},
	{
		label: "List and search",
		properties: [
			{ key: "in_list_view", label: "In list view", type: "check" },
			{ key: "in_standard_filter", label: "List filter", type: "check" },
			{ key: "in_global_search", label: "Global search", type: "check" },
			{ key: "in_preview", label: "Link preview", type: "check" },
			{ key: "search_index", label: "Search index", type: "check" },
		],
	},
	{
		label: "Data and permissions",
		properties: [
			{ key: "unique", label: "Unique", type: "check" },
			{ key: "no_copy", label: "No copy", type: "check" },
			{ key: "set_only_once", label: "Set only once", type: "check" },
			{ key: "non_negative", label: "No negatives", type: "check", only: (field) => NUMERIC.includes(field.fieldtype) },
			{
				key: "precision",
				label: "Decimal places",
				type: "int",
				only: (field) => NUMERIC.includes(field.fieldtype) && field.fieldtype !== "Int",
			},
			{ key: "length", label: "Max length", type: "int", only: (field) => field.fieldtype === "Data" },
			{ key: "permlevel", label: "Perm level", type: "int", placeholder: "0" },
			{
				key: "ignore_user_permissions",
				label: "Ignore user perms",
				type: "check",
				only: (field) => field.fieldtype === "Link",
			},
		],
	},
];

function enabled(name: string) {
	return { name, disabled: false };
}
