// The list's stored shape, fieldnames only, and its conversion to what the controls hold. Labels
// come from meta, and a fieldname meta no longer has, or the person cannot read, is dropped.
import {
	getColumnAlign,
	getColumnOptions,
	isSortableColumn,
	type Column,
} from "@framework/ui/ColumnSettings";
import type { ListColumn } from "@framework/ui/experimental/List";
import {
	getFilterableFields,
	parseFilters,
	type FilterCondition,
	type FilterField,
	type WireFilters,
} from "@framework/ui/Filter";
import type { RawMetaField } from "@framework/ui/FormLayout";
import { getSortOptions, type Sort } from "@framework/ui/SortBy";
import type { DoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { bareLike } from "./query";

export interface StoredColumn {
	fieldname: string;
	width?: string;
}

/** One row's `settings`; every key is optional and a missing one inherits from the tier below. */
export interface ListSettings {
	columns?: StoredColumn[];
	sort?: Sort[];
	/** Wire triples, `[fieldname, operator, value]`, as an app ships them in `views/list.json`. */
	filters?: WireFilters;
	quick_filter_fields?: string[];
}

export type ListSettingsKey = keyof ListSettings;

/** Whether the person may read this fieldname; a standard field names no meta field and passes. */
export type Readable = (fieldname: string) => boolean;

/** The meta flags that decide which collaboration columns a doctype offers. */
export type OptionsMeta = Pick<DoctypeMeta, "is_submittable" | "is_virtual">;

export function columnsFrom(
	stored: unknown,
	fields: RawMetaField[],
	readable: Readable,
	meta: OptionsMeta = {}
): ListColumn[] {
	const options = new Map(
		getColumnOptions(fields, [], meta).map((option) => [option.fieldname, option])
	);
	const columns: ListColumn[] = [];
	for (const entry of asList(stored)) {
		const fieldname = fieldnameOf(entry);
		const option = fieldname && options.get(fieldname);
		if (!option || !readable(fieldname) || columns.some((c) => c.fieldname === fieldname)) continue;
		const column: ListColumn = { fieldname, label: option.label, align: alignOf(fieldname, fields) };
		const width = (entry as StoredColumn).width;
		if (typeof width === "string" && width) column.width = width;
		if (!isSortableColumn(fieldname)) column.sortable = false;
		columns.push(column);
	}
	return columns;
}

export function sortFrom(
	stored: unknown,
	fields: RawMetaField[],
	readable: Readable,
	meta: OptionsMeta = {}
): Sort[] {
	const sortable = new Set(getSortOptions(fields, meta).map((option) => option.fieldname));
	const sort: Sort[] = [];
	for (const entry of asList(stored)) {
		const fieldname = fieldnameOf(entry);
		const direction = (entry as Sort).direction;
		if (!fieldname || !sortable.has(fieldname) || !readable(fieldname)) continue;
		if (direction !== "asc" && direction !== "desc") continue;
		sort.push({ fieldname, direction });
	}
	return sort;
}

export function filtersFrom(
	stored: unknown,
	doctype: string,
	fields: RawMetaField[],
	readable: Readable
): FilterCondition[] {
	const wire = asList(stored).filter(
		(entry): entry is WireFilters[number] =>
			Array.isArray(entry) && typeof entry[0] === "string" && readable(entry[0])
	);
	// An app's file is not validated: a condition whose operator the filter UI lacks is dropped.
	return parseFilters(getFilterableFields(fields, doctype), wire)
		.filter((condition) => condition.operator)
		.map(bareLike);
}

export function quickFilterFieldsFrom(
	stored: unknown,
	doctype: string,
	fields: RawMetaField[],
	readable: Readable
): FilterField[] {
	const filterable = new Map(
		getFilterableFields(fields, doctype).map((field) => [field.fieldname, field])
	);
	const chosen: FilterField[] = [];
	for (const fieldname of asList(stored)) {
		if (typeof fieldname !== "string") continue;
		const field = filterable.get(fieldname);
		if (!field || !readable(fieldname) || chosen.includes(field)) continue;
		chosen.push(field);
	}
	return chosen;
}

/** Width travels; the label does not, since meta names the column at read time. */
export function toStoredColumns(columns: Column[]): StoredColumn[] {
	return columns.map(({ fieldname, width }) => (width ? { fieldname, width } : { fieldname }));
}

export function toStoredQuickFilterFields(fields: FilterField[]): string[] {
	return fields.map((field) => field.fieldname);
}

function asList(value: unknown): unknown[] {
	return Array.isArray(value) ? value : [];
}

function fieldnameOf(entry: unknown): string | null {
	const fieldname = (entry as { fieldname?: unknown } | null)?.fieldname;
	return typeof fieldname === "string" && fieldname ? fieldname : null;
}

function alignOf(fieldname: string, fields: RawMetaField[]): "left" | "right" {
	const fieldtype = fields.find((field) => field.fieldname === fieldname)?.fieldtype;
	return getColumnAlign(fieldtype ?? "Data");
}
