// What the list shows before anyone touches it: columns from a contributed `list.js`, else from
// meta's `in_list_view`; sort from meta's `sort_field`, else `modified desc`.
import { getColumnAlign, getDefaultColumns, isColumnFieldtype, type Column } from "@framework/ui/ColumnSettings";
import type { ListColumn } from "@framework/ui/experimental/List";
import type { RawMetaField } from "@framework/ui/FormLayout";
import { parseOrderBy, type Sort } from "@framework/ui/SortBy";
import type { LinkMarkSource } from "@framework/ui/fields";
import type { ListHandlers, RowAction } from "@/contributions/types";

/** The meta keys the list reads; the meta read sends the whole doctype record. */
export interface ListMeta {
	title_field?: string;
	image_field?: string;
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

/** The fields a page of rows needs: `name`, the columns, their marks, currencies and titles, then the row actions'. */
export function fetchFields(
	columns: Column[],
	rowActions: RowAction[] = [],
	meta: ListMeta = {},
	readable: (fieldname: string) => boolean = () => true
): string[] {
	const marks = columns.flatMap((column) => cellMark(column.fieldname, meta)?.select ?? []);
	const currencies = columns.flatMap(
		(column) => cellCurrency(column.fieldname, meta, readable)?.select ?? []
	);
	const titles = columns.flatMap((column) => cellTitle(column.fieldname, meta)?.select ?? []);
	const wanted = [
		...columns.map((column) => column.fieldname),
		...marks,
		...currencies,
		...titles,
		...rowActions.flatMap((a) => a.fields),
	];
	return [...new Set(["name", ...wanted])];
}

/** What a cell shows before its text and where the row holds it: a Link's target mark, or the title's own image. */
export interface CellMark {
	source: LinkMarkSource;
	/** The row key holding the mark value. */
	key: string;
	/** The field the page asks for; a Link's is read through the link, under an alias. */
	select: string;
}

export function cellMark(fieldname: string, meta: ListMeta): CellMark | undefined {
	const source = meta.fields?.find((field) => field.fieldname === fieldname)?.link_mark;
	if (source) {
		const key = `${fieldname}__mark`;
		return { source, key, select: `${fieldname}.${source.field} as ${key}` };
	}
	if (meta.image_field && fieldname === (meta.title_field || "name")) {
		return { source: { kind: "image", field: meta.image_field }, key: meta.image_field, select: meta.image_field };
	}
}

/** Where a cell finds a value it reads beside its own: a Currency's currency, a Link's title. */
export interface RowValue {
	/** The row key holding the value. */
	key: string;
	/** The field the page asks for; a linked record's is read through the link, under an alias. */
	select: string;
}

/** Follows `Doctype:link_field:currency_field` through the list query, so no cell reads the linked record. */
export function cellCurrency(
	fieldname: string,
	meta: ListMeta,
	readable: (fieldname: string) => boolean = () => true
): RowValue | undefined {
	const fields = meta.fields ?? [];
	const field = fields.find((one) => one.fieldname === fieldname);
	if (field?.fieldtype !== "Currency" || !field.options) return undefined;
	const [source, link, currencyField] = field.options.split(":");
	const holds = (name: string) => fields.some((one) => one.fieldname === name) && readable(name);
	if (!link) return holds(source) ? { key: source, select: source } : undefined;
	if (!currencyField || !holds(link)) return undefined;
	const key = `${fieldname}__currency`;
	return { key, select: `${link}.${currencyField} as ${key}` };
}

/** A Link cell's target title, read through the link as v1 does, so the cell shows it for the name. */
export function cellTitle(fieldname: string, meta: ListMeta): RowValue | undefined {
	const field = meta.fields?.find((one) => one.fieldname === fieldname);
	if (field?.fieldtype !== "Link" || !field.link_title) return undefined;
	const key = `${fieldname}__title`;
	return { key, select: `${fieldname}.${field.link_title} as ${key}` };
}

/** Every contributing app's row actions in run order; an act named twice is listed once, and a `list` act is refused. */
export function contributedRowActions(contributed: ListHandlers[]): RowAction[] {
	const actions = contributed
		.flatMap((handlers) => handlers.rowActions ?? [])
		.filter((action) => !action.act.startsWith("list."));
	return actions.filter((action, index) => actions.findIndex((one) => one.act === action.act) === index);
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
	if (!fields.some((field) => field.in_list_view && isColumnFieldtype(field.fieldtype))) return GENERIC_COLUMNS.map((c) => ({ ...c }));
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
