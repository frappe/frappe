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
// Free-text inputs you type into — these (and `name`) carry the `like`/`equals`
// toggle. Number/Duration/etc. stay `like`-only: the toggle lives only where you
// type, and their value controls have no prefix slot to host it.
const TEXT_TYPES = ["Data", "Small Text", "Text", "Long Text", "Text Editor"];

/** The `name` standard field is a self-Link in Meta, but a quick filter treats
 *  it as free-text (substring `like` by default), only swapping in a Link picker
 *  when flipped to `equals`. Detected by fieldname so the operator set and the
 *  control dispatch agree. */
export const isNameField = (field: FilterField) => field.fieldname === "name";

/**
 * The operator(s) a Quick Filter owns for a field, default first. A port of CRM's
 * `['Check','Select','Link','Date','Datetime'] → direct value` mapping, with one
 * deliberate divergence: text fields (Data/Text/…, plus the `name` field) own BOTH
 * `like` (default) and `equals`, surfaced as a per-input operator toggle —
 * substring-search by default, flip to an exact match. Link and Dynamic Link own a
 * single `equals` (an exact Link pick, no toggle); the equals set is `equals`-only;
 * everything else (Number/Duration/…) is `like`-only.
 */
export function quickFilterOperators(field: FilterField): FilterOperator[] {
  if (isNameField(field)) return ["like", "equals"];
  if (LINK_TYPES.includes(field.fieldtype)) return ["equals"];
  if (EQUALS_TYPES.includes(field.fieldtype)) return ["equals"];
  if (TEXT_TYPES.includes(field.fieldtype)) return ["like", "equals"];
  return ["like"];
}

/** The default (canonical) operator a Quick Filter starts on for a field. */
export function quickFilterOperator(field: FilterField): FilterOperator {
  return quickFilterOperators(field)[0];
}

/** Whether the field offers an operator toggle (more than one owned operator) —
 *  true for free-text fields and `name`, false for Link/Select/Date/Check. */
export function hasOperatorToggle(field: FilterField): boolean {
  return quickFilterOperators(field).length > 1;
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
  const ops = quickFilterOperators(field);
  return filters.find(
    (f) => f.fieldname === field.fieldname && ops.includes(f.operator)
  );
}

/** Whether the shared list has a condition this field's Quick Filter owns. The
 *  operator toggle reads its state from that condition when present, falling back
 *  to a transient override only while the input is still empty. */
export function hasOwnedCondition(
  filters: Filter[],
  field: FilterField
): boolean {
  return ownedCondition(filters, field) !== undefined;
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
  return ownedCondition(filters, field)?.operator ?? quickFilterOperator(field);
}

/**
 * Write: upsert `field`'s Quick Filter condition to `value` (under `operator`, or
 * the field's default), or remove it when `value` is empty. The Quick Filter
 * projects only the **first owned** condition, so a write touches only that one —
 * a precise popover condition with a different operator (and any further owned
 * duplicate the popover allows on the same field) survives untouched. The first
 * owned condition is replaced (or removed) in place, position preserved; when none
 * exists a new condition is appended. Check maps checked → `equals "Yes"`,
 * unchecked → removed (never `equals "No"`); a `like` value is stored **bare**
 * (`serializeFilters` wraps the `%`).
 */
export function applyQuick(
  filters: Filter[],
  field: FilterField,
  value: FilterValue,
  operator?: FilterOperator
): Filter[] {
  const ops = quickFilterOperators(field);
  const op = operator && ops.includes(operator) ? operator : ops[0];
  const owns = (f: Filter) =>
    f.fieldname === field.fieldname && ops.includes(f.operator);
  const cleared = isCheck(field) ? !value : isEmpty(value);
  const firstIdx = filters.findIndex(owns);

  if (cleared) {
    // Nothing owned to clear → no-op. Return the *same* array (not a fresh
    // `.filter()` copy) so a reassignment doesn't change `conditions` identity and
    // spuriously churn `view.snapshot` (→ a phantom autosave/refetch).
    if (firstIdx === -1) return filters;
    // Quick Filter is authoritative for any field it owns: clearing removes
    // *every* owned condition on the field — including a duplicate added via the
    // Filter popover — because the popover should not co-own a field already
    // controlled by the quick-filter bar (Option C; the deliberate, documented
    // contract). Removing only the projected (first owned) one would let a sibling
    // owned duplicate (`status = Open`, `status = Won`) re-project as the input's
    // new shown value, leaving it visibly un-cleared and the list still filtered.
    // Precise, non-owned conditions (a `Status in […]`) survive untouched.
    return filters.filter((f) => !owns(f));
  }

  const condition: Filter = {
    field,
    fieldname: field.fieldname,
    operator: op,
    value: isCheck(field) ? "Yes" : value,
  };
  if (firstIdx === -1) return [...filters, condition];
  // Replace the projected condition in place; every other condition on the field
  // — including a further owned duplicate the popover allows — is preserved.
  return filters.map((f, i) => (i === firstIdx ? condition : f));
}
