import {
	DROPPED_FIELDTYPES,
	mapField,
	type Decorator,
	identifyTabs,
} from "@framework/ui/FormLayout";
import type {
	Column,
	FieldNode,
	FormLayoutSchema,
	RawMetaField,
	Section,
	Tab,
	TabOverride,
} from "@framework/ui/FormLayout/types";
import type { FieldAccess } from "@framework/ui/useDocPermissions";
import { withAccess } from "./fieldAccess";
import { applyFieldPatch, type FieldPatch } from "./fieldPatch";
import { chooseRow } from "./chooseLayout";
import { buildColumn, buildSection } from "./section";
import type {
	FormLayoutRow,
	InlineField,
	LayoutTree,
	LayoutTreeColumn,
	LayoutTreeSection,
} from "./types";
import { withUnplaced, type UnplacedRule } from "./unplaced";

export interface JoinLayoutOptions {
	/** Child doctype name → its flat meta `fields`, for `Table` columns. */
	childMetas?: Record<string, RawMetaField[]>;
	/** Child doctype name → its Details rows; a `Table` field whose child has one gets a `rowLayout`. */
	childLayouts?: Record<string, FormLayoutRow[]>;
	/** Permlevel gate per field; `read` demotes to read-only, `none` hides. */
	fieldAccess?: (field: RawMetaField) => FieldAccess;
	/** Per-field UI overlay hook, inherited by nested grid columns; an undecorated `Button` field has no handler. */
	decorate?: Decorator;
	/** Per-render field overrides by fieldname; the `override` half beats `depends_on`, never a permlevel denial. */
	overrides?: Record<string, FieldPatch>;
	/** Per-render tab overrides by identity; carried, not applied, since `FormLayout` draws the strip. */
	tabOverrides?: Record<string, TabOverride>;
	/** How the row in use draws the meta fields it neither places nor omits; unset draws none. */
	unplaced?: UnplacedRule;
}

/** Joins a tree of fieldnames against the meta into a `FormLayoutSchema`; unknown fields and `DROPPED_FIELDTYPES` drop. */
export function joinLayout(
	tree: LayoutTree,
	fields: RawMetaField[],
	options: JoinLayoutOptions = {}
): FormLayoutSchema {
	const byName = new Map(fields.map((field) => [field.fieldname, field]));
	const drawn = options.unplaced
		? withUnplaced(tree ?? [], fields, options.unplaced, options.fieldAccess)
		: tree ?? [];
	return identifyTabs(drawn).map(
		(tab): Tab => ({
			name: tab.name,
			label: tab.label,
			dependsOn: tab.dependsOn,
			override: options.tabOverrides?.[tab.identity],
			sections: (tab.sections ?? []).map((section) =>
				joinSection(section, byName, options)
			),
		})
	);
}

function joinSection(
	section: LayoutTreeSection,
	byName: Map<string, RawMetaField>,
	options: JoinLayoutOptions
): Section {
	return buildSection(
		section,
		(section.columns ?? []).map((column) =>
			joinColumn(column, byName, options)
		)
	);
}

function joinColumn(
	column: LayoutTreeColumn,
	byName: Map<string, RawMetaField>,
	options: JoinLayoutOptions
): Column {
	return buildColumn(
		column,
		(column.fields ?? []).flatMap((entry) =>
			joinField(entry, byName, options)
		)
	);
}

function joinField(
	entry: string | InlineField,
	byName: Map<string, RawMetaField>,
	options: JoinLayoutOptions
): FieldNode[] {
	const raw = typeof entry === "string" ? byName.get(entry) : inlineField(entry, byName);
	if (!raw || DROPPED_FIELDTYPES.has(raw.fieldtype)) return [];
	const node = mapField(
		withAccess(raw, options.fieldAccess),
		options.childMetas ?? {},
		options.decorate
	);
	const patch = options.overrides?.[raw.fieldname];
	return [applyFieldPatch(withRowLayout(node, raw, options), patch)];
}

function withRowLayout(node: FieldNode, raw: RawMetaField, options: JoinLayoutOptions): FieldNode {
	if (raw.fieldtype !== "Table" || !raw.options) return node;
	const rows = options.childLayouts?.[raw.options];
	const fields = options.childMetas?.[raw.options];
	if (!rows?.length || !fields) return node;
	return { ...node, rowLayout: rowLayoutOf(rows, fields, options, node.childLayout ?? []) };
}

/** Each row is joined once, so the dialog keeps its form while the row it edits stays on one layout. */
function rowLayoutOf(
	rows: FormLayoutRow[],
	fields: RawMetaField[],
	options: JoinLayoutOptions,
	fallback: FormLayoutSchema
): (row: Record<string, any>) => FormLayoutSchema {
	const joined = new Map<FormLayoutRow, FormLayoutSchema>();
	return (row) => {
		const chosen = chooseRow(rows, row);
		if (!chosen) return fallback;
		if (!joined.has(chosen))
			joined.set(
				chosen,
				joinLayout(chosen.layout, fields, {
					childMetas: options.childMetas,
					decorate: options.decorate,
					unplaced: { mode: "section", omitted: chosen.omitted },
				})
			);
		return joined.get(chosen)!;
	};
}

/** An inline field that replaces a meta field keeps its permlevel, which the insert enforces. */
function inlineField(field: InlineField, byName: Map<string, RawMetaField>): RawMetaField {
	const replaced = byName.get(field.fieldname);
	return replaced ? { ...field, permlevel: replaced.permlevel } : field;
}
