import { mapField } from "../../components/FormLayout/buildLayoutFromMeta";
import type { Decorator } from "../../components/FormLayout/buildLayoutFromMeta";
import type {
	Column,
	FieldNode,
	FieldOverride,
	FormLayoutSchema,
	RawMetaField,
	Section,
	Tab,
} from "../../components/FormLayout/types";
import type { FieldAccess } from "../../composables/useDocPermissions";
import { withAccess } from "./fieldAccess";
import { buildColumn, buildSection } from "./section";
import type { LayoutTree, LayoutTreeColumn, LayoutTreeSection } from "./types";

export interface JoinLayoutOptions {
	/** Child doctype name → its flat meta `fields`, for `Table` columns. */
	childMetas?: Record<string, RawMetaField[]>;
	/** Permlevel gate per field; `read` demotes to read-only, `none` hides. */
	fieldAccess?: (field: RawMetaField) => FieldAccess;
	/**
	 * Per-field UI overlay hook, inherited by nested grid columns. This is what
	 * makes a `Button` field do anything: an undecorated Button renders with no
	 * handler (`ButtonField.vue`), so an app that wants clickable Buttons passes
	 * a decorator here.
	 */
	decorate?: Decorator;
	/**
	 * Per-render field property overrides, keyed by fieldname. Plain data on
	 * purpose — `FormLayout` reads it off the schema and knows nothing about who
	 * wrote it. Applied last by `resolveFieldConditionals`, so an override beats
	 * `depends_on` but never a permlevel denial.
	 */
	overrides?: Record<string, FieldOverride>;
}

const LAYOUT_BREAKS = new Set(["Tab Break", "Section Break", "Column Break"]);

/**
 * Join a layout tree (fieldnames as strings, as `get_form_layouts` returns it)
 * against the doctype's meta fields into a render-ready `FormLayoutSchema`.
 * A fieldname the doctype no longer has is dropped, as are layout breaks.
 */
export function joinLayout(
	tree: LayoutTree,
	fields: RawMetaField[],
	options: JoinLayoutOptions = {}
): FormLayoutSchema {
	const byName = new Map(fields.map((field) => [field.fieldname, field]));
	return (tree ?? []).map(
		(tab): Tab => ({
			name: tab.name,
			label: tab.label,
			dependsOn: tab.dependsOn,
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
	const override = options.overrides?.[fieldname];
	return [override ? { ...node, override } : node];
}
