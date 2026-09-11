import { mapField } from "@framework/ui/components/FormLayout/buildLayoutFromMeta";
import type { Decorator } from "@framework/ui/components/FormLayout/buildLayoutFromMeta";
import type {
	Column,
	FieldNode,
	FormLayoutSchema,
	RawMetaField,
	Section,
	Tab,
	TabOverride,
} from "@framework/ui/components/FormLayout/types";
import { identifyTabs } from "@framework/ui/components/FormLayout/tabIdentity";
import type { FieldAccess } from "@framework/ui/composables/useDocPermissions";
import { withAccess } from "./fieldAccess";
import { applyFieldPatch, type FieldPatch } from "./fieldPatch";
import { buildColumn, buildSection } from "./section";
import type { LayoutTree, LayoutTreeColumn, LayoutTreeSection } from "./types";

export interface JoinLayoutOptions {
	/** Child doctype name → its flat meta `fields`, for `Table` columns. */
	childMetas?: Record<string, RawMetaField[]>;
	/** Permlevel gate per field; `read` demotes to read-only, `none` hides. */
	fieldAccess?: (field: RawMetaField) => FieldAccess;
	/** Per-field UI overlay hook, inherited by nested grid columns; an undecorated `Button` field has no handler. */
	decorate?: Decorator;
	/** Per-render field overrides by fieldname; the `override` half beats `depends_on`, never a permlevel denial. */
	overrides?: Record<string, FieldPatch>;
	/** Per-render tab overrides by identity; carried, not applied, since `FormLayout` draws the strip. */
	tabOverrides?: Record<string, TabOverride>;
}

const LAYOUT_BREAKS = new Set(["Tab Break", "Section Break", "Column Break"]);

/** Joins a tree of fieldnames against the meta into a `FormLayoutSchema`; unknown fields and layout breaks drop. */
export function joinLayout(
	tree: LayoutTree,
	fields: RawMetaField[],
	options: JoinLayoutOptions = {}
): FormLayoutSchema {
	const byName = new Map(fields.map((field) => [field.fieldname, field]));
	return identifyTabs(tree ?? []).map(
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
		(column.fields ?? []).flatMap((fieldname) =>
			joinField(fieldname, byName, options)
		)
	);
}

function joinField(
	fieldname: string,
	byName: Map<string, RawMetaField>,
	options: JoinLayoutOptions
): FieldNode[] {
	const raw = byName.get(fieldname);
	if (!raw || LAYOUT_BREAKS.has(raw.fieldtype)) return [];
	const node = mapField(
		withAccess(raw, options.fieldAccess),
		options.childMetas ?? {},
		options.decorate
	);
	return [applyFieldPatch(node, options.overrides?.[fieldname])];
}
