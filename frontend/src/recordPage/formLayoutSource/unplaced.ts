import { DROPPED_FIELDTYPES } from "@framework/ui/FormLayout";
import { __ } from "@/i18n";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { FieldAccess } from "@framework/ui/useDocPermissions";
import { withAnchors } from "./anchors";
import type { LayoutTree, LayoutTreeSection } from "./types";

/** What a row in use does with the fields it neither places nor omits. */
export interface UnplacedRule {
	/** `section`: Details and New Record draw them at their anchor, else in "More fields" at the end of the first tab.
	 *  `mandatory`: Quick Entry adds only the mandatory ones at the end of the dialog. */
	mode: "section" | "mandatory";
	/** Fieldnames the row keeps off on purpose; a stale one matches nothing. */
	omitted?: string[];
	/** Fieldnames another layout on the same page places, such as the Side Panel row in use. */
	placedElsewhere?: Iterable<string>;
}

const SECTION_NAME = "more_fields";

export function withUnplaced(
	tree: LayoutTree,
	fields: RawMetaField[],
	rule: UnplacedRule,
	fieldAccess?: (field: RawMetaField) => FieldAccess
): LayoutTree {
	const unplaced = unplacedFields(tree, fields, rule, fieldAccess);
	if (rule.mode === "section") {
		const anchored = withAnchors(tree, unplaced);
		return withMoreFieldsSection(anchored.tree, anchored.rest, fields);
	}
	return withMandatorySections(tree, unplaced.filter(isMandatory), fields);
}

/** Meta fields, in meta (`idx`) order, that the row neither places nor omits and the person can see. */
export function unplacedFields(
	tree: LayoutTree,
	fields: RawMetaField[],
	rule: UnplacedRule,
	fieldAccess?: (field: RawMetaField) => FieldAccess
): RawMetaField[] {
	const placed = new Set([...placedFieldnames(tree), ...(rule.placedElsewhere ?? [])]);
	if (rule.mode === "section")
		for (const fieldname of omittable(rule.omitted, fields)) placed.add(fieldname);
	return fields.filter(
		(field) =>
			!placed.has(field.fieldname) &&
			!DROPPED_FIELDTYPES.has(field.fieldtype) &&
			!field.hidden &&
			fieldAccess?.(field) !== "none"
	);
}

/** Every fieldname a tree lists, by name or as an inline field. */
export function placedFieldnames(tree: LayoutTree | null): string[] {
	return (tree ?? []).flatMap((tab) =>
		(tab.sections ?? []).flatMap((section) =>
			(section.columns ?? []).flatMap((column) =>
				(column.fields ?? []).map((entry) =>
					typeof entry === "string" ? entry : entry.fieldname
				)
			)
		)
	);
}

function withMoreFieldsSection(
	tree: LayoutTree,
	unplaced: RawMetaField[],
	fields: RawMetaField[]
): LayoutTree {
	if (!unplaced.length) return tree;
	const section: LayoutTreeSection = {
		name: freeSectionName(takenNames(tree, fields)),
		label: __("More fields"),
		columns: [{ name: "column_1", fields: unplaced.map((field) => field.fieldname) }],
	};
	const [first, ...rest] = withTab(tree);
	return [{ ...first, sections: [...(first.sections ?? []), section] }, ...rest];
}

/** Sectioned as the server's Quick Entry fallback is: a conditional field gets a section of its own. */
function withMandatorySections(
	tree: LayoutTree,
	mandatory: RawMetaField[],
	fields: RawMetaField[]
): LayoutTree {
	if (!mandatory.length) return tree;
	const taken = takenNames(tree, fields);
	const sections: LayoutTreeSection[] = [];
	for (const field of mandatory) {
		const condition = mandatoryCondition(field);
		const last = sections.at(-1);
		if (condition || !last || last.dependsOn) {
			sections.push({
				name: freeSectionName(taken),
				hideBorder: true,
				dependsOn: condition,
				columns: [{ name: "column_1", fields: [] }],
			});
		}
		sections.at(-1)!.columns[0].fields.push(field.fieldname);
	}
	const tabs = withTab(tree);
	const last = tabs.at(-1)!;
	return [...tabs.slice(0, -1), { ...last, sections: [...(last.sections ?? []), ...sections] }];
}

/** `reqd` with no `default`, or required under a condition. */
function isMandatory(field: RawMetaField): boolean {
	return Boolean(alwaysMandatory(field) || field.mandatory_depends_on);
}

function alwaysMandatory(field: RawMetaField): boolean {
	return Boolean(field.reqd && !field.default);
}

function mandatoryCondition(field: RawMetaField): string | undefined {
	return alwaysMandatory(field) ? undefined : field.mandatory_depends_on;
}

/** A field that became mandatory after the row omitted it renders anyway: no row may omit one. */
function omittable(omitted: string[] = [], fields: RawMetaField[]): string[] {
	const mandatory = new Set(fields.filter(alwaysMandatory).map((field) => field.fieldname));
	return omitted.filter((fieldname) => !mandatory.has(fieldname));
}

function withTab(tree: LayoutTree): LayoutTree {
	return tree.length ? tree : [{ name: "first_tab", sections: [] }];
}

/** A script addresses sections and fields by one name across the form, so an added section dodges both. */
function takenNames(tree: LayoutTree, fields: RawMetaField[]): Set<string | undefined> {
	return new Set([
		...fields.map((field) => field.fieldname),
		...tree.flatMap((tab) => (tab.sections ?? []).map((section) => section.name)),
	]);
}

function freeSectionName(taken: Set<string | undefined>): string {
	let name = SECTION_NAME;
	for (let suffix = 2; taken.has(name); suffix++) name = `${SECTION_NAME}_${suffix}`;
	taken.add(name);
	return name;
}
