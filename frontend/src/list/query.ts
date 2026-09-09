// The list's address: filters and sort in the URL query, one key per filtered field and the
// sort under `_sort`, so Copy link carries them and Back restores them.
import {
	getFilterableFields,
	parseFilters,
	serializeFilters,
	type FilterCondition,
	type FilterField,
	type WireFilters,
} from "@framework/ui/Filter";
import { parseOrderBy, serializeOrderBy, type Sort } from "@framework/ui/SortBy";
import type { RawMetaField } from "@framework/ui/FormLayout";
import type { LocationQuery } from "vue-router";

export const SORT_KEY = "_sort";
/** The shell's own query keys on a generated route; never read as a filter. */
const RESERVED_KEYS = new Set([SORT_KEY, "view", "layout", "from"]);

export interface ListAddress {
	filters: FilterCondition[];
	sort: Sort[];
}

export type Query = Record<string, string>;

/** An equals filter is written bare, any other operator as a `[operator, value]` pair. */
export function queryFromAddress(address: ListAddress): Query {
	const query: Query = {};
	for (const [fieldname, operator, value] of serializeFilters(completeFilters(address.filters))) {
		query[fieldname] = operator === "=" ? bareValue(value) : JSON.stringify([operator, value]);
	}
	const orderBy = serializeOrderBy(address.sort);
	if (orderBy) query[SORT_KEY] = orderBy;
	return query;
}

/** The address a query holds; a key that names no filterable field is not ours to read. */
export function addressFromQuery(
	query: LocationQuery,
	doctype: string,
	fields: RawMetaField[]
): Partial<ListAddress> {
	const filterable = getFilterableFields(fields, doctype);
	const byName = new Map(filterable.map((field) => [field.fieldname, field]));
	const wire: WireFilters = [];
	for (const [key, raw] of Object.entries(query)) {
		if (RESERVED_KEYS.has(key)) continue;
		const field = byName.get(key);
		if (field && typeof raw === "string" && raw) wire.push([key, ...wirePair(field, raw)]);
	}
	const address: Partial<ListAddress> = {};
	if (wire.length) address.filters = parseFilters(filterable, wire).map(bareLike);
	const sort = query[SORT_KEY];
	if (typeof sort === "string" && sort) address.sort = parseOrderBy(sort);
	return address;
}

/** The query keys this list writes; every other key is carried through untouched. */
export function ownedKeys(doctype: string, fields: RawMetaField[]): Set<string> {
	const owned = new Set([SORT_KEY]);
	for (const field of getFilterableFields(fields, doctype)) {
		if (!RESERVED_KEYS.has(field.fieldname)) owned.add(field.fieldname);
	}
	return owned;
}

export function sameQuery(a: LocationQuery, b: LocationQuery): boolean {
	return stableQuery(a) === stableQuery(b);
}

/** A condition with no value is still being typed and is not sent. */
export function completeFilters(filters: FilterCondition[]): FilterCondition[] {
	return filters.filter((condition) => {
		const { value } = condition;
		if (value === null || value === undefined || value === "") return false;
		return !(Array.isArray(value) && !value.length);
	});
}

function stableQuery(query: LocationQuery): string {
	return JSON.stringify(
		Object.keys(query)
			.sort()
			.map((key) => [key, query[key]])
	);
}

function bareValue(value: unknown): string {
	if (typeof value === "boolean") return value ? "1" : "0";
	return String(value);
}

function wirePair(field: FilterField, raw: string): [string, unknown] {
	const parsed = parseJson(raw);
	if (Array.isArray(parsed) && parsed.length === 2 && typeof parsed[0] === "string") {
		return [parsed[0], parsed[1]];
	}
	if (field.fieldtype === "Check") return ["=", ["1", "true", "yes"].includes(raw.toLowerCase())];
	return ["=", raw];
}

/** The wire wraps a `like` value in `%`; the control shows the bare text. */
function bareLike(condition: FilterCondition): FilterCondition {
	const { operator, value } = condition;
	if (!operator.includes("like") || typeof value !== "string") return condition;
	if (!value.startsWith("%") || !value.endsWith("%")) return condition;
	return { ...condition, value: value.slice(1, -1) };
}

function parseJson(raw: string): unknown {
	try {
		return JSON.parse(raw);
	} catch {
		return undefined;
	}
}
