import type { RawMetaField } from "../FormLayout/types";
import type {
  Aggregate,
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

/** Fieldtypes whose values make sensible groups; free text and long text don't. */
const GROUPABLE_FIELDTYPES = new Set([
  "Select",
  "Link",
  "Data",
  "Check",
  "Int",
  "Date",
]);

const NUMERIC_FIELDTYPES = new Set([
  "Int",
  "Float",
  "Currency",
  "Percent",
  "Duration",
]);

const DATE_FIELDTYPES = new Set(["Date", "Datetime"]);

/** Standard fields every doctype can be grouped by, after the Meta fields. */
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

function isShown(f: RawMetaField): boolean {
  return Boolean(f.label && f.fieldname) && !f.hidden;
}

/** The fields a list can be grouped by: labelled, visible fields of a groupable
 *  fieldtype, then the standard user fields. */
export function getGroupByFields(fields: RawMetaField[]): GroupByField[] {
  return [
    ...fields
      .filter((f) => isShown(f) && GROUPABLE_FIELDTYPES.has(f.fieldtype))
      .map(toField),
    ...STANDARD_GROUP_FIELDS,
  ];
}

/** The fields an aggregate can run on. Sum and average need numbers; min and
 *  max also take dates. Count needs no field. */
export function getAggregateFields(
  fields: RawMetaField[],
  fn: AggregateFunction
): GroupByField[] {
  if (fn === "count") return [];
  const allowsDates = fn === "min" || fn === "max";
  return fields
    .filter(
      (f) =>
        isShown(f) &&
        (NUMERIC_FIELDTYPES.has(f.fieldtype) ||
          (allowsDates && DATE_FIELDTYPES.has(f.fieldtype)))
    )
    .map(toField);
}

/** Field lookup for labels and formatting, covering the standard user fields. */
export function findGroupByField(
  fields: RawMetaField[],
  fieldname: string
): GroupByField | undefined {
  const meta = fields.find((f) => f.fieldname === fieldname);
  if (meta) return toField(meta);
  return STANDARD_GROUP_FIELDS.find((f) => f.fieldname === fieldname);
}

/** Whether an aggregate has everything its function needs. */
export function isCompleteAggregate(aggregate: Aggregate): boolean {
  return aggregate.function === "count" || Boolean(aggregate.fieldname);
}

/** The row key an aggregate's value comes back under. */
export function aggregateKey(index: number): string {
  return `_aggregate_${index}`;
}

/** The arguments for `frappe.client.get_list` that fetch one row per group: the
 *  group fields, one aliased aggregate per complete Aggregate, the `group_by`
 *  clause, and an `order_by` on the first aggregate, largest first. Count runs on
 *  `name`, as desk's report view does, so `export_query` can label it too. */
export function serializeGroupBy(groupBy: GroupBySettings): {
  fields: (string | Record<string, string>)[];
  group_by: string;
  order_by?: string;
} {
  const aggregates = groupBy.aggregates.filter(isCompleteAggregate);
  return {
    fields: [
      ...groupBy.fields,
      ...aggregates.map((a, i) => ({
        [a.function.toUpperCase()]:
          a.function === "count" ? "name" : (a.fieldname as string),
        as: aggregateKey(i),
      })),
    ],
    group_by: groupBy.fields.join(", "),
    order_by: aggregates.length ? `${aggregateKey(0)} desc` : undefined,
  };
}

const FUNCTIONS = new Set(AGGREGATE_FUNCTIONS.map((f) => f.value));

function isAggregate(value: unknown): value is Aggregate {
  if (!value || typeof value !== "object") return false;
  const aggregate = value as Aggregate;
  return (
    FUNCTIONS.has(aggregate.function) &&
    (aggregate.fieldname === undefined ||
      typeof aggregate.fieldname === "string") &&
    isCompleteAggregate(aggregate)
  );
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
  return {
    fields: groupFields,
    aggregates: Array.isArray(aggregates) ? aggregates.filter(isAggregate) : [],
  };
}
