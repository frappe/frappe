// What the list shows before anyone touches it: columns from a contributed `list.js`, else from
// meta's `in_list_view`; sort from meta's `sort_field`, else `modified desc`.
import { getColumnAlign, getDefaultColumns, type Column } from "@framework/ui/ColumnSettings";
import type { ListColumn } from "@framework/ui/experimental/List";
import type { RawMetaField } from "@framework/ui/FormLayout";
import { parseOrderBy, type Sort } from "@framework/ui/SortBy";
import type { ListHandlers } from "@/contributions/types";

/** The meta keys the list reads; `getdoctype` sends the whole doctype record. */
export interface ListMeta {
	title_field?: string;
	sort_field?: string;
	sort_order?: string;
	fields?: RawMetaField[];
}

const GENERIC_COLUMNS: Column[] = [
	{ fieldname: "name", label: "Name" },
	{ fieldname: "modified", label: "Last Modified" },
];

export const DEFAULT_SORT: Sort[] = [{ fieldname: "modified", direction: "desc" }];

export function defaultColumns(meta: ListMeta, contributed: ListHandlers[]): ListColumn[] {
	const fields = meta.fields ?? [];
	const columns = contributedColumns(fields, contributed) ?? metaColumns(fields, meta.title_field);
	return columns.map((column) => withAlign(column, fields));
}

export function defaultSort(meta: ListMeta): Sort[] {
	if (!meta.sort_field) return DEFAULT_SORT;
	const orderBy = meta.sort_field.includes(" ")
		? meta.sort_field
		: `${meta.sort_field} ${meta.sort_order ?? "desc"}`;
	const sort = parseOrderBy(orderBy);
	return sort.length ? sort : DEFAULT_SORT;
}

export function sameSort(a: Sort[], b: Sort[]): boolean {
	return JSON.stringify(a) === JSON.stringify(b);
}

/** The fields a page of rows needs: `name` for the link, then one per column. */
export function fetchFields(columns: Column[]): string[] {
	return [...new Set(["name", ...columns.map((column) => column.fieldname)])];
}

/** Every contributing app's columns in run order; a fieldname named twice is shown once. */
function contributedColumns(fields: RawMetaField[], contributed: ListHandlers[]): Column[] | null {
	const columns: Column[] = [];
	const seen = new Set<string>();
	for (const handlers of contributed) {
		for (const { fieldname, width } of handlers.columns ?? []) {
			if (seen.has(fieldname)) continue;
			seen.add(fieldname);
			const column: Column = { fieldname, label: labelOf(fieldname, fields) };
			if (width) column.width = `${width}px`;
			columns.push(column);
		}
	}
	return columns.length ? columns : null;
}

function metaColumns(fields: RawMetaField[], titleField?: string): Column[] {
	if (!fields.some((field) => field.in_list_view)) return GENERIC_COLUMNS.map((c) => ({ ...c }));
	return getDefaultColumns(fields, titleField);
}

function labelOf(fieldname: string, fields: RawMetaField[]): string {
	const generic = GENERIC_COLUMNS.find((column) => column.fieldname === fieldname);
	return fields.find((field) => field.fieldname === fieldname)?.label ?? generic?.label ?? fieldname;
}

function withAlign(column: Column, fields: RawMetaField[]): ListColumn {
	const fieldtype = fields.find((field) => field.fieldname === column.fieldname)?.fieldtype;
	return { ...column, align: getColumnAlign(fieldtype ?? "Data") };
}
