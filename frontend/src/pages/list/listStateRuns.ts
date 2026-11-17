// The runs of `list.set_filters`, `list.set_sort` and `list.select`, and the list's `state()` facts; loaded on first use.
import { ActInvalid } from "@/acts/dispatcher";
import { bareLike, completeFilters } from "@/list/query";
import type { ListPageController } from "@/listPage/createListPage";
import { getFilterableFields, parseFilters, serializeFilters, type FilterCondition, type WireFilters } from "@framework/ui/Filter";
import { getSortOptions, type Sort } from "@framework/ui/SortBy";

/** What the runs know of the doctype: its fields, and which of them this reader may see. */
export interface ListSchema {
  meta: () => Record<string, any> | null;
  readable: (fieldname: string) => boolean;
}

const ROWS = 20;
const TITLE_CHARS = 100;

// REST v2 spells `like` and `not like` in lower case; the filter control's wire form in upper.
const OPERATORS: Record<string, string> = {
  "=": "=",
  "!=": "!=",
  like: "LIKE",
  "not like": "NOT LIKE",
  in: "in",
  "not in": "not in",
  is: "is",
  "is not": "is not",
  ">": ">",
  "<": "<",
  ">=": ">=",
  "<=": "<=",
  between: "between",
  timespan: "timespan",
};
const LISTS = new Set(["in", "not in", "between"]);

export async function setFilters(list: ListPageController, schema: ListSchema, value: { filters: unknown[] }) {
  list.page.filters = parseConditions(value.filters, schema, list.page.doctype);
  await list.renderer().settled();
  return readRows(list, schema);
}

export async function setSort(list: ListPageController, schema: ListSchema, value: { sort: unknown[] }) {
  list.page.sort = parseSort(value.sort, schema);
  await list.renderer().settled();
  return readRows(list, schema);
}

export async function select(list: ListPageController, names: string[]) {
  const shown = new Set(list.page.rows.map((row) => row.name));
  const missing = names.filter((name) => !shown.has(name));
  if (missing.length)
    throw new ActInvalid(
      "list.select",
      `these are not loaded rows: ${missing.join(", ")}. Read state().rows, or narrow the list with list.set_filters so they show`,
    );
  const unique = [...new Set(names)];
  await list.renderer().select(unique);
  return { selected: unique };
}

/** The run of each act, by act name; the list's entries call them with the act's input. */
export const RUNS: Record<string, (list: ListPageController, schema: ListSchema, value: any) => Promise<unknown>> = {
  set_filters: setFilters,
  set_sort: setSort,
  select: (list, _schema, { names }) => select(list, names),
};

/** The page facts `window.desk.state` adds for a list: filters as REST v2 triples, sort, selection and the first rows. */
export function listFacts(list: ListPageController, schema: ListSchema) {
  const { page } = list;
  return {
    doctype: page.doctype,
    filters: serializeFilters(completeFilters(page.filters)),
    sort: page.sort.map(({ fieldname, direction }) => ({ fieldname, direction })),
    selected: [...page.selection],
    rows: rowsOf(list, schema),
  };
}

function readRows(list: ListPageController, schema: ListSchema) {
  return loadedRows(list.page.rows, list.renderer().total(), schema.meta()?.title_field);
}

/** What the acts that load rows return: how many records match, and the first rows with their titles. */
export function loadedRows(rows: readonly Record<string, unknown>[], total: number, titleField: string | undefined) {
  return { total, rows: titledRows(rows, titleField) };
}

function titledRows(rows: readonly Record<string, unknown>[], titleField: string | undefined) {
  return rows.slice(0, ROWS).map((row) => ({ name: String(row.name), title: titleOf(row, titleField) }));
}

function rowsOf(list: ListPageController, schema: ListSchema) {
  return titledRows(list.page.rows, schema.meta()?.title_field);
}

function titleOf(row: Record<string, unknown>, field: string | undefined) {
  const text = field && row[field] != null && row[field] !== "" ? String(row[field]) : String(row.name);
  return text.length > TITLE_CHARS ? `${text.slice(0, TITLE_CHARS)}…` : text;
}

function parseConditions(filters: unknown[], schema: ListSchema, doctype: string): FilterCondition[] {
  const fields = schema.meta()?.fields;
  if (!fields) throw new Error("the list has not loaded its fields yet");
  const filterable = getFilterableFields(fields, doctype).filter((field) => schema.readable(field.fieldname));
  const byName = new Map(filterable.map((field) => [field.fieldname, field]));
  const seen = new Set<unknown>();
  const wire: WireFilters = filters.map((entry, index) => {
    const at = `filters[${index}]`;
    if (!Array.isArray(entry) || entry.length !== 3) throw invalid("list.set_filters", `${at} must be [fieldname, operator, value]`);
    const [fieldname, operator, value] = entry;
    const field = typeof fieldname === "string" ? byName.get(fieldname) : undefined;
    if (!field) throw invalid("list.set_filters", `${at}: ${String(fieldname)} is not a field this list can filter on; use one of ${oneOf([...byName.keys()])}`);
    if (seen.has(fieldname)) throw invalid("list.set_filters", `${at}: ${fieldname} has a condition already; the list holds one for each field, so use between for a range`);
    seen.add(fieldname);
    const wireOperator = typeof operator === "string" ? OPERATORS[operator.toLowerCase()] : undefined;
    if (!wireOperator) throw invalid("list.set_filters", `${at}: ${String(operator)} is not an operator; use one of ${Object.keys(OPERATORS).join(", ")}`);
    const reason = valueFault(wireOperator, value);
    if (reason) throw invalid("list.set_filters", `${at}: ${reason}`);
    if (field.fieldtype === "Check") return checkTriple(at, fieldname as string, wireOperator, value);
    if (wireOperator === "is" || wireOperator === "is not") return emptiness(at, fieldname as string, wireOperator, value);
    return [fieldname as string, wireOperator, value];
  });
  return parseFilters(filterable, wire).map(bareLike);
}

function valueFault(operator: string, value: unknown): string | undefined {
  if (LISTS.has(operator)) {
    if (!Array.isArray(value) || (operator === "between" && value.length !== 2))
      return `${operator} takes ${operator === "between" ? "a list of two values, from and to" : "a list of values"}`;
    if (!value.length) return `${operator} needs at least one value`;
    return undefined;
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean")
    // Such a condition would match every record, not none.
    return blank(operator, value) ? `${operator} needs a value; to find empty fields use "is" with "not set"` : undefined;
  return `${operator} takes one text, number or boolean value`;
}

/** The server has `is` alone, with "set" or "not set"; `is not` is the other of the two. */
function emptiness(at: string, fieldname: string, operator: string, value: unknown): [string, string, string] {
  const text = typeof value === "string" ? value.toLowerCase() : "";
  if (text !== "set" && text !== "not set") throw invalid("list.set_filters", `${at}: ${operator} takes "set" or "not set"`);
  return [fieldname, "is", (text === "set") === (operator === "is") ? "set" : "not set"];
}

/** A Check holds a boolean, so only "=" and "!=" mean something; "!=" is the opposite boolean. */
function checkTriple(at: string, fieldname: string, operator: string, value: unknown): [string, string, boolean] {
  if (operator !== "=" && operator !== "!=") throw invalid("list.set_filters", `${at}: ${fieldname} is a checkbox; use = or != with true or false`);
  const on = value === true || value === 1 || value === "1";
  const off = value === false || value === 0 || value === "0";
  if (!on && !off) throw invalid("list.set_filters", `${at}: ${fieldname} is a checkbox; send true or false`);
  return [fieldname, "=", operator === "=" ? on : !on];
}

function parseSort(sort: unknown[], schema: ListSchema): Sort[] {
  const fields = schema.meta()?.fields;
  if (!fields) throw new Error("the list has not loaded its fields yet");
  const sortable = new Set(getSortOptions(fields, schema.meta() ?? {}).map((option) => option.fieldname));
  return sort.map((entry, index) => {
    const at = `sort[${index}]`;
    const { fieldname, direction } = (entry ?? {}) as Partial<Sort>;
    if (typeof fieldname !== "string" || !sortable.has(fieldname) || !schema.readable(fieldname))
      throw invalid("list.set_sort", `${at}: ${String(fieldname)} is not a field this list can sort on; use one of ${oneOf([...sortable].filter(schema.readable))}`);
    if (direction !== "asc" && direction !== "desc") throw invalid("list.set_sort", `${at}: direction must be "asc" or "desc"`);
    return { fieldname, direction };
  });
}

function invalid(act: string, reason: string) {
  return new ActInvalid(act, reason);
}

/** The list drops a condition with no text, and a Like with only `%` has none once the wire's `%` is stripped. */
function blank(operator: string, value: unknown): boolean {
  if (value === "") return true;
  return (operator === "LIKE" || operator === "NOT LIKE") && typeof value === "string" && value.replaceAll("%", "").trim() === "";
}

/** A long field list would drown the error: the first few, then how many more. */
export function oneOf(names: string[]): string {
  const SHOWN = 15;
  const more = names.length - SHOWN;
  return names.slice(0, SHOWN).join(", ") + (more > 0 ? `, and ${more} more` : "");
}
