import { mapField } from "../../components/FormLayout/buildLayoutFromMeta";
import type {
	Column,
	FieldNode,
	FormLayoutSchema,
	RawMetaField,
	Section,
	Tab,
} from "../../components/FormLayout/types";
import type { FieldAccess } from "../../composables/useDocPermissions";
import type { LayoutTree, LayoutTreeColumn, LayoutTreeSection } from "./types";

export interface JoinLayoutOptions {
	/** Child doctype name → its flat meta `fields`, for `Table` columns. */
	childMetas?: Record<string, RawMetaField[]>;
	/** Permlevel gate per field; `read` demotes to read-only, `none` hides. */
	fieldAccess?: (field: RawMetaField) => FieldAccess;
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
	return {
		name: section.name,
		label: section.label,
		hideLabel: Boolean(section.hideLabel),
		hideBorder: Boolean(section.hideBorder),
		collapsible: Boolean(section.collapsible),
		opened: section.opened !== false,
		dependsOn: section.dependsOn,
		columns: (section.columns ?? []).map((column) =>
			joinColumn(column, byName, options)
		),
	};
}

function joinColumn(
	column: LayoutTreeColumn,
	byName: Map<string, RawMetaField>,
	options: JoinLayoutOptions
): Column {
	return {
		name: column.name,
		label: column.label,
		fields: (column.fields ?? []).flatMap((fieldname) =>
			joinField(fieldname, byName, options)
		),
	};
}

function joinField(
	fieldname: string,
	byName: Map<string, RawMetaField>,
	options: JoinLayoutOptions
): FieldNode[] {
	const raw = byName.get(fieldname);
	if (!raw || LAYOUT_BREAKS.has(raw.fieldtype)) return [];
	return [mapField(withAccess(raw, options.fieldAccess), options.childMetas ?? {})];
}

function withAccess(
	field: RawMetaField,
	fieldAccess?: (field: RawMetaField) => FieldAccess
): RawMetaField {
	const access = fieldAccess?.(field);
	if (!access || access === "write") return field;
	return access === "read"
		? { ...field, read_only: 1 }
		: { ...field, hidden: 1 };
}
