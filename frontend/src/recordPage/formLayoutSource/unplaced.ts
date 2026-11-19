import { DROPPED_FIELDTYPES } from "@framework/ui/FormLayout";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { FieldAccess } from "@framework/ui/useDocPermissions";
import { withAnchors } from "./anchors";
import type { LayoutTree, LayoutTreeSection } from "./types";

/** What a row in use does with the fields it does not place. */
export interface UnplacedRule {
	/** Fieldnames the row did not place at its save; any other field it does not place is new since then. */
	omitted?: string[];
	/** Draw each new field at its anchor, else nowhere: Details, New Record and the row dialog. */
	anchors?: boolean;
	/** Add each mandatory field still not drawn at the end: Quick Entry and the row dialog. */
	mandatoryAtEnd?: boolean;
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
	const anchored = rule.anchors ? withNewFields(tree, fields, rule, fieldAccess) : tree;
	if (!rule.mandatoryAtEnd) return anchored;
	const mandatory = notShown(anchored, fields, rule).filter(
		(field) => isDrawn(field, fieldAccess) && isMandatory(field)
	);
	return withMandatorySections(anchored, mandatory, fields);
}

/** The mandatory fields, in meta (`idx`) order, that the page does not show and the person can write. */
export function requiredOffLayout(
	shown: Iterable<string>,
	fields: RawMetaField[],
	fieldAccess?: (field: RawMetaField) => FieldAccess
): RawMetaField[] {
	const drawn = new Set(shown);
	return fields.filter(
		(field) =>
			!drawn.has(field.fieldname) &&
			isDrawn(field, fieldAccess) &&
			Boolean(field.reqd || field.mandatory_depends_on) &&
			!field.read_only &&
			(fieldAccess?.(field) ?? "write") === "write"
	);
}

/** A field new since the row's save renders at its anchor; with none it is not drawn. */
function withNewFields(
	tree: LayoutTree,
	fields: RawMetaField[],
	rule: UnplacedRule,
	fieldAccess?: (field: RawMetaField) => FieldAccess
): LayoutTree {
	const omitted = new Set(rule.omitted ?? []);
	const fresh = notShown(tree, fields, rule).filter((field) => !omitted.has(field.fieldname));
	return withAnchors(tree, fresh.filter((field) => isDrawn(field, fieldAccess)), fresh);
}

function notShown(tree: LayoutTree, fields: RawMetaField[], rule: Pick<UnplacedRule, "placedElsewhere">) {
	const placed = new Set([...placedFieldnames(tree), ...(rule.placedElsewhere ?? [])]);
	return fields.filter((field) => !placed.has(field.fieldname));
}

function isDrawn(field: RawMetaField, fieldAccess?: (field: RawMetaField) => FieldAccess): boolean {
	return !DROPPED_FIELDTYPES.has(field.fieldtype) && !field.hidden && fieldAccess?.(field) !== "none";
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
