import type {
  Filter,
  FilterField,
  FilterOperator,
  FilterValue,
} from "../Filter/types";

// Fieldtype groups, re-declared here (as `operators.ts` does) so this stays a
// pure, frappe-ui-free helper. A Quick Filter projects over the shared Filter
// list by *operator*: it owns only conditions on its field whose operator is in
// the field's canonical quick-filter set, leaving precise popover-built
// conditions (a `Status in […]`, an `amount between …`) untouched.
const CHECK_TYPES = ["Check"];
const LINK_TYPES = ["Link", "Dynamic Link"];
const EQUALS_TYPES = ["Check", "Select", "Autocomplete", "Date", "Datetime"];

/**
 * The operator(s) a Quick Filter owns for a fieldtype, default first. A faithful
 * port of CRM's `['Check','Select','Link','Date','Datetime'] → direct value`
 * mapping, with one deliberate divergence: **Link** owns BOTH `like` (default)
 * and `equals`, surfaced as a per-input operator toggle. You rarely recall a
 * record's exact name, so a Link quick filter substring-searches by default
 * (`like`) but can be flipped to an exact `equals` pick. Everything outside the
 * equals set (Data/Text/Number/Duration) is `like`-only.
 */
export function quickFilterOperators(fieldtype: string): FilterOperator[] {
  if (LINK_TYPES.includes(fieldtype)) return ["like", "equals"];
  if (EQUALS_TYPES.includes(fieldtype)) return ["equals"];
  return ["like"];
}

/** The default (canonical) operator a Quick Filter starts on for a fieldtype. */
export function quickFilterOperator(fieldtype: string): FilterOperator {
  return quickFilterOperators(fieldtype)[0];
}

/** Whether the field offers an operator toggle (more than one owned operator). */
export function hasOperatorToggle(fieldtype: string): boolean {
  return quickFilterOperators(fieldtype).length > 1;
}

const isCheck = (field: FilterField) => CHECK_TYPES.includes(field.fieldtype);

function isEmpty(value: FilterValue): boolean {
  if (Array.isArray(value)) return value.length === 0;
  return value === "" || value == null;
}

/** The first condition on `field` the Quick Filter owns (operator in the field's
 *  canonical set), or `undefined` when only non-owned conditions exist. */
function ownedCondition(
  filters: Filter[],
  field: FilterField
): Filter | undefined {
  const ops = quickFilterOperators(field.fieldtype);
  return filters.find(
    (f) => f.fieldname === field.fieldname && ops.includes(f.operator)
  );
}

/**
 * Read: the value a Quick Filter input shows for `field`, projected from the
 * shared Filter list. Surfaces the first owned condition's value; a Check maps to
 * a boolean (checked ⇔ `equals "Yes"`). When no owned condition exists — including
 * when the field carries only a precise, non-owned condition (a `Status in […]`) —
 * the input shows empty.
 */
export function quickValue(filters: Filter[], field: FilterField): FilterValue {
  const owned = ownedCondition(filters, field);
  if (isCheck(field)) return owned?.value === "Yes";
  return owned ? owned.value : "";
}

/** Read: the active operator for `field`'s Quick Filter input — the owned
 *  condition's operator, or the field's default when none exists. Drives the
 *  Link operator toggle's current state. */
export function quickOperator(
  filters: Filter[],
  field: FilterField
): FilterOperator {
  return (
    ownedCondition(filters, field)?.operator ??
    quickFilterOperator(field.fieldtype)
  );
}

/**
 * Write: upsert `field`'s Quick Filter condition to `value` (under `operator`, or
 * the field's default), or remove it when `value` is empty. Only conditions the
 * Quick Filter owns are touched — a precise popover condition with a different
 * operator survives, so setting a quick filter **appends** a coexisting condition
 * rather than overwriting the precise one. The first owned condition is replaced
 * in place (position preserved); any other owned duplicate is dropped. Check maps
 * checked → `equals "Yes"`, unchecked → removed (never `equals "No"`); a `like`
 * value is stored **bare** (`serializeFilters` wraps the `%`).
 */
export function applyQuick(
  filters: Filter[],
  field: FilterField,
  value: FilterValue,
  operator?: FilterOperator
): Filter[] {
  const ops = quickFilterOperators(field.fieldtype);
  const op = operator && ops.includes(operator) ? operator : ops[0];
  const owns = (f: Filter) =>
    f.fieldname === field.fieldname && ops.includes(f.operator);
  const cleared = isCheck(field) ? !value : isEmpty(value);
  const firstIdx = filters.findIndex(owns);

  if (cleared) {
    return firstIdx === -1 ? filters : filters.filter((f) => !owns(f));
  }

  const condition: Filter = {
    field,
    fieldname: field.fieldname,
    operator: op,
    value: isCheck(field) ? "Yes" : value,
  };
  if (firstIdx === -1) return [...filters, condition];
  // Replace the first owned condition in place; drop any other owned duplicate.
  return filters
    .map((f, i) => (i === firstIdx ? condition : f))
    .filter((f, i) => i === firstIdx || !owns(f));
}
