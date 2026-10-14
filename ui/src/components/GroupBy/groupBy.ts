import type { RawMetaField } from "../FormLayout/types";
import type { Sort } from "../SortBy/types";
import type {
  Aggregate,
  AggregateDraft,
  AggregateFunction,
  GroupByField,
  GroupBySettings,
} from "./types";

export const AGGREGATE_FUNCTIONS: ReadonlyArray<{
  label: string;
  value: AggregateFunction;
}> = [
  { label: "Count", value: "count" },
  { label: "Sum", value: "sum" },
  { label: "Average", value: "avg" },
  { label: "Min", value: "min" },
  { label: "Max", value: "max" },
];

/** Fieldtypes whose values make sensible groups, as desk's report view offers them;
 *  free text and long text don't. */
const GROUPABLE_FIELDTYPES = new Set([
  "Select",
  "Link",
  "Dynamic Link",
  "Data",
  "Autocomplete",
  "Check",
  "Int",
  "Date",
]);

/** Desk's `frappe.model.numeric_fieldtypes`, the ones sum and average take. */
const NUMERIC_FIELDTYPES = new Set([
  "Int",
  "Float",
  "Currency",
  "Percent",
  "Duration",
]);

const TIME_FIELDTYPES = new Set(["Date", "Datetime", "Time"]);

/** Standard timestamps every doctype has, which min and max can run on. */
const STANDARD_TIME_FIELDS: ReadonlyArray<GroupByField> = [
  {
    label: "Created On",
    value: "creation",
    fieldname: "creation",
    fieldtype: "Datetime",
  },
  {
    label: "Last Modified",
    value: "modified",
    fieldname: "modified",
    fieldtype: "Datetime",
  },
];

/** Standard fields every doctype can be grouped by, after the Meta fields: desk's
 *  standard fields of a groupable fieldtype, less `name` and `idx`. */
const STANDARD_GROUP_FIELDS: ReadonlyArray<GroupByField> = [
  {
    label: "Created By",
    value: "owner",
    fieldname: "owner",
    fieldtype: "Link",
    options: "User",
  },
  {
    label: "Last Modified By",
    value: "modified_by",
    fieldname: "modified_by",
    fieldtype: "Link",
    options: "User",
  },
  {
    label: "Tags",
    value: "_user_tags",
    fieldname: "_user_tags",
    fieldtype: "Data",
  },
  {
    label: "Document Status",
    value: "docstatus",
    fieldname: "docstatus",
    fieldtype: "Int",
  },
];

function toField(f: RawMetaField): GroupByField {
  return {
    label: f.label as string,
    value: f.fieldname,
    fieldname: f.fieldname,
    fieldtype: f.fieldtype,
    options: f.options,
  };
}

// Hidden fields are offered, as desk does; a virtual field has no column to query.
function isQueryable(f: RawMetaField): boolean {
  return Boolean(f.label && f.fieldname) && !f.is_virtual;
}

/** The fields a list can be grouped by: labelled fields of a groupable fieldtype,
 *  then the standard fields. */
export function getGroupByFields(fields: RawMetaField[]): GroupByField[] {
  return [
    ...fields
      .filter((f) => isQueryable(f) && GROUPABLE_FIELDTYPES.has(f.fieldtype))
      .map(toField),
    ...STANDARD_GROUP_FIELDS,
  ];
}

/** The fields an aggregate can run on. Sum and average need numbers; min and
 *  max also take dates and times, including the standard timestamps. Count needs
 *  no field. */
export function getAggregateFields(
  fields: RawMetaField[],
  fn: AggregateFunction
): GroupByField[] {
  if (fn === "count") return [];
  const allowsTimes = fn === "min" || fn === "max";
  const metaFields = fields
    .filter(
      (f) =>
        isQueryable(f) &&
        (NUMERIC_FIELDTYPES.has(f.fieldtype) ||
          (allowsTimes && TIME_FIELDTYPES.has(f.fieldtype)))
    )
    .map(toField);
  return allowsTimes ? [...metaFields, ...STANDARD_TIME_FIELDS] : metaFields;
}

/** Field lookup for labels and formatting, covering the standard fields. */
export function findGroupByField(
  fields: RawMetaField[],
  fieldname: string
): GroupByField | undefined {
  const meta = fields.find((f) => f.fieldname === fieldname);
  if (meta) return toField(meta);
  return [...STANDARD_GROUP_FIELDS, ...STANDARD_TIME_FIELDS].find(
    (f) => f.fieldname === fieldname
  );
}

/** Whether an aggregate has everything its function needs. */
export function isCompleteAggregate(
  aggregate: AggregateDraft
): aggregate is Aggregate {
  return aggregate.function === "count" || Boolean(aggregate.fieldname);
}

/** A column's id, which its saved width and sort refer to: the fieldname for a
 *  grouped field, and function plus field for an aggregate, so removing one column
 *  leaves the others' settings alone. */
export function columnId(column: string | Aggregate): string {
  if (typeof column === "string") return column;
  return column.function === "count"
    ? "count:"
    : `${column.function}:${column.fieldname}`;
}

/** Whether a row other than `index` already has `candidate`, by `columnId`, which
 *  `parseGroupBy` also dedups on. A row with no field yet is never a duplicate. */
export function isAggregateTaken(
  aggregates: AggregateDraft[],
  index: number,
  candidate: AggregateDraft
): boolean {
  if (!isCompleteAggregate(candidate)) return false;
  const id = columnId(candidate);
  return aggregates.some(
    (a, i) => i !== index && isCompleteAggregate(a) && columnId(a) === id
  );
}

/** The row key an aggregate's value comes back under. */
export function aggregateKey(index: number): string {
  return `_aggregate_${index}`;
}

function aggregateFields(aggregates: Aggregate[]): Record<string, string>[] {
  return aggregates.map((a, i) => ({
    [a.function.toUpperCase()]: a.function === "count" ? "name" : a.fieldname,
    as: aggregateKey(i),
  }));
}

/** The sort the groups come back in, by column id: the chosen header sort while
 *  its column is still shown, else the first aggregate, largest first, as desk
 *  does. Empty when there's nothing to sort by. */
export function effectiveSort(groupBy: GroupBySettings): Sort[] {
  const { aggregates } = groupBy;
  const chosen = groupBy.sort?.[0];
  const ids = [...groupBy.fields, ...aggregates.map(columnId)];
  if (chosen && ids.includes(chosen.fieldname)) return [chosen];
  return aggregates.length
    ? [{ fieldname: columnId(aggregates[0]), direction: "desc" }]
    : [];
}

// The effective sort on the wire, then the group fields so ties keep their place as loadMore pages.
function orderBy(groupBy: GroupBySettings): string {
  const [sort] = effectiveSort(groupBy);
  const tieBreakers = groupBy.fields
    .filter((f) => f !== sort?.fieldname)
    .map((f) => `${f} asc`);
  if (!sort) return tieBreakers.join(", ");
  const index = groupBy.aggregates.findIndex(
    (a) => columnId(a) === sort.fieldname
  );
  const column = index >= 0 ? aggregateKey(index) : sort.fieldname;
  return [`${column} ${sort.direction}`, ...tieBreakers].join(", ");
}

/** The arguments for `frappe.client.get_list` that fetch one row per group: the
 *  group fields, one aliased aggregate per Aggregate, the `group_by`
 *  clause, and the `order_by` of the chosen sort, tie-broken by the group fields.
 *  Count runs on `name`, as desk's report view does, so `export_query` can label
 *  it too. */
export function serializeGroupBy(groupBy: GroupBySettings): {
  fields: (string | Record<string, string>)[];
  group_by: string;
  order_by: string;
} {
  return {
    fields: [...groupBy.fields, ...aggregateFields(groupBy.aggregates)],
    group_by: groupBy.fields.join(", "),
    order_by: orderBy(groupBy),
  };
}

/** The `frappe.client.get_list` fields for the totals row: the same aggregates over
 *  every matching record, ungrouped, so an average or a max is the true one rather
 *  than a sum of the groups'. `null` when there's nothing to total. */
export function serializeGroupByTotals(
  groupBy: GroupBySettings
): { fields: Record<string, string>[] } | null {
  const { aggregates } = groupBy;
  return aggregates.length ? { fields: aggregateFields(aggregates) } : null;
}

const FUNCTIONS = new Set(AGGREGATE_FUNCTIONS.map((f) => f.value));

function isAggregate(value: unknown): value is Aggregate {
  if (!value || typeof value !== "object") return false;
  const aggregate = value as AggregateDraft;
  return (
    FUNCTIONS.has(aggregate.function) &&
    (aggregate.fieldname === undefined ||
      typeof aggregate.fieldname === "string") &&
    isCompleteAggregate(aggregate)
  );
}

function parseSort(raw: unknown): Sort[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  const sort = raw.filter(
    (s): s is Sort =>
      Boolean(s) &&
      typeof s.fieldname === "string" &&
      (s.direction === "asc" || s.direction === "desc")
  );
  return sort.length ? [{ ...sort[0] }] : undefined;
}

function parseWidths(raw: unknown): Record<string, string> | undefined {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return undefined;
  const widths = Object.fromEntries(
    Object.entries(raw).filter(([, width]) => typeof width === "string")
  ) as Record<string, string>;
  return Object.keys(widths).length ? widths : undefined;
}

/** Read a stored grouping back, from JSON text or a parsed object. Anything
 *  malformed is dropped, and a grouping with no fields left reads as `null`. */
export function parseGroupBy(raw: unknown): GroupBySettings | null {
  let value = raw;
  if (typeof raw === "string") {
    try {
      value = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (!value || typeof value !== "object") return null;
  const { fields, aggregates } = value as Partial<
    Record<keyof GroupBySettings, unknown>
  >;
  const groupFields = Array.isArray(fields)
    ? fields.filter((f): f is string => typeof f === "string" && f !== "")
    : [];
  if (!groupFields.length) return null;
  // An aggregate saved twice reads once, as the control only lets it be added once.
  const valid = Array.isArray(aggregates) ? aggregates.filter(isAggregate) : [];
  const ids = valid.map(columnId);
  const parsed: GroupBySettings = {
    fields: groupFields,
    aggregates: valid.filter((a, i) => ids.indexOf(columnId(a)) === i),
  };
  const extras = value as {
    widths?: unknown;
    sort?: unknown;
    showTotals?: unknown;
  };
  const widths = parseWidths(extras.widths);
  if (widths) parsed.widths = widths;
  const sort = parseSort(extras.sort);
  if (sort) parsed.sort = sort;
  if (extras.showTotals === true) parsed.showTotals = true;
  return parsed;
}
