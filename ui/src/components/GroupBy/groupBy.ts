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
  "Rating",
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

/** The standard column holding a record's assignees, as a JSON list of users. */
const ASSIGNED_TO = "_assign";

/** Standard fields every doctype can be grouped by, after the Meta fields: desk's
 *  standard fields of a groupable fieldtype, less `name` and `idx`. */
const STANDARD_GROUP_FIELDS: ReadonlyArray<GroupByField> = [
  {
    label: "Assigned To",
    value: ASSIGNED_TO,
    fieldname: ASSIGNED_TO,
    fieldtype: "Link",
    options: "User",
  },
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
 *  then the standard fields, less any fieldnames in `exclude`. */
export function getGroupByFields(
  fields: RawMetaField[],
  exclude: string[] = []
): GroupByField[] {
  return [
    ...fields
      .filter((f) => isQueryable(f) && GROUPABLE_FIELDTYPES.has(f.fieldtype))
      .map(toField),
    ...STANDARD_GROUP_FIELDS,
  ].filter((f) => !exclude.includes(f.fieldname));
}

/** The fields an aggregate can run on. Sum and average need numbers; min and
 *  max also take dates and times, including the standard timestamps. A rating can
 *  be averaged or ranged but not summed. Count needs no field. Fieldnames in
 *  `exclude` are left out. */
export function getAggregateFields(
  fields: RawMetaField[],
  fn: AggregateFunction,
  exclude: string[] = []
): GroupByField[] {
  if (fn === "count") return [];
  const allowsTimes = fn === "min" || fn === "max";
  const allowsRating = fn !== "sum";
  const metaFields = fields
    .filter(
      (f) =>
        isQueryable(f) &&
        (NUMERIC_FIELDTYPES.has(f.fieldtype) ||
          (allowsRating && f.fieldtype === "Rating") ||
          (allowsTimes && TIME_FIELDTYPES.has(f.fieldtype)))
    )
    .map(toField);
  return (
    allowsTimes ? [...metaFields, ...STANDARD_TIME_FIELDS] : metaFields
  ).filter((f) => !exclude.includes(f.fieldname));
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

type RowSort = { key: string; direction: Sort["direction"] };

// The effective sort by row key, then the group fields so ties keep their place as loadMore pages.
function rowSort(groupBy: GroupBySettings): RowSort[] {
  const [sort] = effectiveSort(groupBy);
  const tieBreakers: RowSort[] = groupBy.fields
    .filter((f) => f !== sort?.fieldname)
    .map((f) => ({ key: f, direction: "asc" }));
  if (!sort) return tieBreakers;
  const index = groupBy.aggregates.findIndex(
    (a) => columnId(a) === sort.fieldname
  );
  const key = index >= 0 ? aggregateKey(index) : sort.fieldname;
  return [{ key, direction: sort.direction }, ...tieBreakers];
}

function orderBy(groupBy: GroupBySettings): string {
  return rowSort(groupBy)
    .map((s) => `${s.key} ${s.direction}`)
    .join(", ");
}

/** Whether the list is grouped by assignee, whose rows need `splitAssignees`. */
export function groupsByAssignee(groupBy: GroupBySettings): boolean {
  return groupBy.fields.includes(ASSIGNED_TO);
}

// Split groups are added up, so each average comes as a sum and a count of values.
function splittableAggregateFields(
  aggregates: Aggregate[]
): Record<string, string>[] {
  return aggregates.flatMap((a, i) =>
    a.function === "avg"
      ? [
          { SUM: a.fieldname, as: `${aggregateKey(i)}_sum` },
          { COUNT: a.fieldname, as: `${aggregateKey(i)}_count` },
        ]
      : aggregateFields([a]).map((f) => ({ ...f, as: aggregateKey(i) }))
  );
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
  if (groupsByAssignee(groupBy)) {
    return {
      fields: [
        ...groupBy.fields,
        ...splittableAggregateFields(groupBy.aggregates),
      ],
      group_by: groupBy.fields.join(", "),
      order_by: groupBy.fields.map((f) => `${f} asc`).join(", "),
    };
  }
  return {
    fields: [...groupBy.fields, ...aggregateFields(groupBy.aggregates)],
    group_by: groupBy.fields.join(", "),
    order_by: orderBy(groupBy),
  };
}

// The users in an `_assign` value, or one `null` for a record assigned to no one.
function assignees(value: unknown): (string | null)[] {
  let users: unknown = value;
  if (typeof value === "string") {
    try {
      users = JSON.parse(value);
    } catch {
      users = [];
    }
  }
  const list = Array.isArray(users)
    ? users.filter((u): u is string => typeof u === "string" && u !== "")
    : [];
  return list.length ? [...new Set(list)] : [null];
}

function addValues(a: unknown, b: unknown): unknown {
  if (a === null || a === undefined) return b;
  if (b === null || b === undefined) return a;
  return Number(a) + Number(b);
}

const TIME = /^(\d+):(\d{2})(?::(\d{2}(?:\.\d+)?))?$/;

// Times come back unpadded ("9:00:00"), so compare them as seconds; dates sort as text.
function orderable(value: unknown): number | string {
  if (typeof value === "number") return value;
  const time = TIME.exec(String(value));
  if (!time) return String(value);
  return Number(time[1]) * 3600 + Number(time[2]) * 60 + Number(time[3] ?? 0);
}

function pickValue(a: unknown, b: unknown, fn: "min" | "max"): unknown {
  if (a === null || a === undefined) return b;
  if (b === null || b === undefined) return a;
  const [x, y] = [orderable(a), orderable(b)];
  if (fn === "min") return y < x ? b : a;
  return y > x ? b : a;
}

// Fold `row` into `group`, both the same group's values from different records.
function mergeInto(
  group: Record<string, unknown>,
  row: Record<string, unknown>,
  aggregates: Aggregate[]
) {
  aggregates.forEach((a, i) => {
    const key = aggregateKey(i);
    if (a.function === "avg") {
      for (const part of [`${key}_sum`, `${key}_count`]) {
        group[part] = addValues(group[part], row[part]);
      }
    } else if (a.function === "min" || a.function === "max") {
      group[key] = pickValue(group[key], row[key], a.function);
    } else {
      group[key] = addValues(group[key], row[key]);
    }
  });
}

// Nulls sort first going up, as the database sorts them.
function compareValues(a: unknown, b: unknown): number {
  const aEmpty = a === null || a === undefined || a === "";
  const bEmpty = b === null || b === undefined || b === "";
  if (aEmpty || bEmpty) return Number(bEmpty) - Number(aEmpty);
  const [x, y] = [orderable(a), orderable(b)];
  if (typeof x === "number" && typeof y === "number") return x - y;
  return String(x).localeCompare(String(y));
}

/** Turn rows per list of assignees into sorted rows per user, a record counting under each assignee. */
export function splitAssignees(
  rows: Record<string, unknown>[],
  groupBy: GroupBySettings
): Record<string, unknown>[] {
  const { aggregates } = groupBy;
  const groups = new Map<string, Record<string, unknown>>();
  for (const row of rows) {
    for (const user of assignees(row[ASSIGNED_TO])) {
      const split = { ...row, [ASSIGNED_TO]: user };
      const key = JSON.stringify(groupBy.fields.map((f) => split[f] ?? null));
      const group = groups.get(key);
      if (group) mergeInto(group, split, aggregates);
      else groups.set(key, split);
    }
  }

  const result = [...groups.values()].map((group) => {
    aggregates.forEach((a, i) => {
      if (a.function !== "avg") return;
      const key = aggregateKey(i);
      const count = Number(group[`${key}_count`]) || 0;
      group[key] = count ? Number(group[`${key}_sum`]) / count : null;
      delete group[`${key}_sum`];
      delete group[`${key}_count`];
    });
    return group;
  });

  const order = rowSort(groupBy);
  return result.sort((a, b) => {
    for (const { key, direction } of order) {
      const diff = compareValues(a[key], b[key]);
      if (diff) return direction === "desc" ? -diff : diff;
    }
    return 0;
  });
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

const ratingFormat = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 1,
});

/** A Rating is stored as a fraction of its stars (0.6 of 5 is 3 stars); show it on
 *  the field's own scale, as "3 / 5". `options` holds the star count, 5 when unset. */
export function formatRating(value: number, options?: string): string {
  const stars = Number(options) || 5;
  return `${ratingFormat.format(value * stars)} / ${stars}`;
}
