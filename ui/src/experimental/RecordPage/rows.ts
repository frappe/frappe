// How a script addresses a child row (wayfinder ticket 43) — `page.rows('products')`
// and the handle it hands back.
//
// A handle holds `(parentfield, key)` and **re-finds its row on every access**.
// Nothing about a row's position is ever captured, which is the whole of the
// staleness answer: a script that captures a row, `await`s a server call and then
// writes to it is doing the dangerous thing the ported script actually does, and
// v1 loses those writes silently by wrapping the row object. Here a removed row
// throws, attributed, aborting the handler — 47's precedent, for 47's reason.
//
// Fields are read and written bare (`row.amount = row.qty * row.rate`), and there
// is exactly one engine member, `trigger`, spelled as v1 spells it. That set is
// deliberately one: 43 designed a `$` prefix to keep engine members out of the
// fieldname namespace and then retired it by cutting the members it protected, and
// recorded that adding a second bare member is the moment to reopen it.
import { runningSource } from "./context";
import {
  holdsChildRows,
  identify,
  ROW_ID,
  rowKey,
} from "../../components/Fields/rowIdentity";
import type { RawMetaField } from "../../components/FormLayout/types";
import type { RowAddress } from "../../components/Fields/types";
import { ROW_EVENTS } from "./flattenHandlers";
import { readOnly, type ReadOnlyAdvice } from "./readOnly";
import { toastScriptError } from "./pageScripts";
import { reportCustomizationError } from "./reportError";
import type { PageRow } from "./types";

const ROWS_ARE_READ_ONLY: ReadOnlyAdvice = {
  path: "page.rows()",
  instead: "page.doc[parentfield], which is the table itself",
};

/** The one engine member on a handle; everything else is a child fieldname. */
const TRIGGER = "trigger";

// `markRaw`'s stamp, answered by the traps below rather than stored on the target.
// It is what tells both Vue's reactivity and the outbound read-only guard that a
// handle is not data to descend into — the guard wraps every object it hands back,
// and a read-only handle would refuse the writes that are the whole point of one.
const RAW = "__v_skip";

/**
 * What `trigger` will not dispatch: the structural half of the vocabulary. Note
 * these are the `on`-prefixed spellings (ticket 54) — a child field genuinely
 * called `add` is triggerable like any other, which is the whole reason the
 * lifecycle keys left the fieldname namespace.
 */
const STRUCTURAL: string[] = Object.values(ROW_EVENTS);

export interface RowsHost {
  /** The draft document; rows are re-found in it on every access. */
  doc: () => Record<string, any>;
  /** The parent doctype's flat meta `fields`; absent until the meta lands. */
  fields: () => RawMetaField[] | undefined;
  /** The child doctype's fields, for telling a typo'd `trigger` from a real one. */
  childFields?: (doctype: string) => RawMetaField[] | undefined;
  /** Fires a row-keyed event across every source; `trigger`'s whole body. */
  dispatch: (event: string, row: RowAddress) => Promise<void>;
}

export interface Rows {
  /** `page.rows` — the table's handles, in array order. */
  rows: (parentfield: string) => PageRow[];
  /** The handle a row-keyed event hands its handler. */
  handle: (address: RowAddress) => PageRow;
}

export function createRows(host: RowsHost): Rows {
  // One handle per address, for the page's life. Not an optimisation and not
  // optional: without it `page.rows('products')[0] !== page.rows('products')[0]`,
  // so `indexOf`, `includes`, `filter(r => r !== row)` and every `===` a script
  // writes are quietly wrong — and a handler comparing the row it was handed
  // against the table would find it nowhere. `readOnly.ts` keeps its own wrappers
  // for exactly this reason; a handle is the same kind of object.
  const handles = new Map<string, PageRow>();

  function rows(parentfield: string): PageRow[] {
    const table = holdsRows(parentfield) ? host.doc()?.[parentfield] : undefined;
    if (!Array.isArray(table)) return readOnly([], ROWS_ARE_READ_ONLY);
    const keys = keysOf(table);
    return readOnly(
      table.map((_row, index) => handle({ parentfield, key: keys[index] })),
      ROWS_ARE_READ_ONLY,
    );
  }

  /**
   * Every row's key, minted here as well as at the two mutation sites so a row a
   * script pushed onto `page.doc.products` itself is still addressable. A read
   * that writes, and safe because a painted document carries a server `name` on
   * every row: nothing is minted unless a script added the row.
   *
   * Two rows sharing a key would read as one — the grid selects and deletes them
   * together, and a handle would write into whichever comes first, silently.
   * A server name is unique by construction, so the only way it happens is a
   * script copying a row (`{ ...products[0] }`), which copies the `__row_id`
   * with it; that copy is re-minted rather than left aliasing the original.
   */
  function keysOf(table: Record<string, any>[]): string[] {
    const seen = new Set<string>();
    return table.map((row) => {
      const key = rowKey(identify(row))!;
      if (!seen.has(key)) return seen.add(key), key;
      if (row.name) {
        warnOnce(`Two rows share the child docname ${row.name} — addressing the first.`);
        return key;
      }
      delete row[ROW_ID];
      const minted = rowKey(identify(row))!;
      seen.add(minted);
      return minted;
    });
  }

  function handle(address: RowAddress): PageRow {
    const cached = handles.get(`${address.parentfield}\0${address.key}`);
    if (cached) return cached;
    const made = build(address);
    handles.set(`${address.parentfield}\0${address.key}`, made);
    return made;
  }

  function build({ parentfield, key }: RowAddress): PageRow {
    /** The row as it is *now*, or the throw. Every field trap starts here. */
    function required(prop: string | symbol): Record<string | symbol, any> {
      const row = resolve();
      if (!row) refuseRemovedRow(parentfield, prop);
      return row;
    }

    // Keyed by symbol as well as fieldname: the traps below answer probes too.
    function resolve(): Record<string | symbol, any> | undefined {
      const table = host.doc()?.[parentfield];
      return Array.isArray(table)
        ? table.find((row) => rowKey(row) === key)
        : undefined;
    }

    // A bare child fieldname, because the handle already knows its table and
    // forms the dotted key itself: the author spells the table once, when they
    // acquire the row (ticket 45 §3).
    const trigger = (fieldname: string) => {
      required(TRIGGER);
      if (!triggerable(parentfield, fieldname)) return Promise.resolve();
      return host.dispatch(`${parentfield}.${fieldname}`, { parentfield, key });
    };

    // The target is an empty object rather than the row: a Proxy may only lie
    // about a target's properties while the target is extensible and owns none,
    // and the row it would otherwise wrap is a different object on every access.
    return new Proxy({} as PageRow, {
      get(_target, prop) {
        if (prop === TRIGGER) return trigger;
        if (prop === RAW) return true;
        if (probe(prop)) return resolve()?.[prop];
        return required(prop)[prop];
      },
      set(_target, prop, value) {
        required(prop)[prop] = value;
        return true;
      },
      deleteProperty(_target, prop) {
        return Reflect.deleteProperty(required(prop), prop);
      },
      has(_target, prop) {
        if (prop === TRIGGER || prop === RAW) return true;
        if (probe(prop)) return !!resolve() && prop in resolve()!;
        return prop in required(prop);
      },
      // `{ ...row }` and `Object.keys(row)` answer with the row's own fields:
      // `trigger` and the stamp are not among them, so a spread copies data.
      // A removed row throws here rather than spreading to `{}` — silently
      // copying nothing is the v1 failure this whole handle exists to end.
      // `*` rather than a fieldname: enumerating asks about the whole row, and
      // naming a field the doctype does not have would be a worse message.
      ownKeys() {
        return Reflect.ownKeys(required("*"));
      },
      getOwnPropertyDescriptor(_target, prop) {
        if (prop === RAW) return RAW_DESCRIPTOR;
        const row = probe(prop) ? resolve() : required(prop);
        const descriptor = row && Object.getOwnPropertyDescriptor(row, prop);
        // Configurable, always: the target does not own the property, and a
        // Proxy may not report a non-configurable one it cannot produce.
        return descriptor ? { ...descriptor, configurable: true } : undefined;
      },
    });
  }

  /**
   * Only the meta can say a fieldname is not a child table, and it lands after
   * the first paint — so this stays quiet until it can tell, exactly as
   * `page.fields` does about a fieldname it cannot find yet.
   */
  function holdsRows(parentfield: string): boolean {
    const field = tableField(parentfield);
    if (!host.fields() || field) return true;
    warnOnce(`page.rows("${parentfield}") — not a child table; no rows to address.`);
    return false;
  }

  /**
   * `trigger` dispatches a *field* event, so it refuses the structural keys —
   * `'products.onAdd'` fired from here would hand a live row to a handler 45 §3
   * gives none, and `'products.onRemove'` would announce a removal that did not
   * happen. It also refuses a dotted argument, since the handle spells the
   * table itself, and warns about a fieldname the child doctype does not have:
   * the same typo written as a handler key is already named at load.
   */
  function triggerable(parentfield: string, fieldname: string): boolean {
    const said = `row.trigger("${fieldname}") on ${parentfield}`;
    if (STRUCTURAL.includes(fieldname))
      return refuseTrigger(
        `${said} — ${STRUCTURAL.join(" and ")} fire at the mutation site.`,
      );
    if (fieldname.includes("."))
      return refuseTrigger(`${said} — pass a bare child fieldname; the row knows its table.`);
    const child = childFieldsOf(parentfield);
    if (child && !child.some((one) => one.fieldname === fieldname))
      return refuseTrigger(`${said} — no such field on the child doctype.`);
    return true;
  }

  function childFieldsOf(parentfield: string): RawMetaField[] | undefined {
    const options = tableField(parentfield)?.options;
    return options ? host.childFields?.(options) : undefined;
  }

  function tableField(parentfield: string): RawMetaField | undefined {
    const field = host
      .fields()
      ?.find((one) => one.fieldname === parentfield);
    return field && holdsChildRows(field.fieldtype) ? field : undefined;
  }

  return { rows, handle };
}

// Vue's reactivity flags are plain strings, not symbols (`__v_isRef`, `__v_raw`,
// …), so the symbol test alone would let a `ref(row)` or an `isRef` in a template
// throw from inside a render effect. Neither kind is a fieldname a script wrote,
// and answering a probe with a throw makes a removed row blow up on being *looked
// at* rather than on being used.
function probe(prop: string | symbol): boolean {
  return typeof prop === "symbol" || prop.startsWith("__v_");
}

const RAW_DESCRIPTOR: PropertyDescriptor = {
  value: true,
  writable: false,
  enumerable: false,
  configurable: true,
};

/**
 * The tombstone channel, as [47] fixed its shape: the thrown `Error` carries the
 * standalone sentence, the console line and the toast add the attribution, and
 * the throw aborts the rest of the handler — report-but-continue is the silent
 * no-op wearing a report, which is the one thing v1 does here.
 */
function refuseRemovedRow(parentfield: string, prop: string | symbol): never {
  const path = `${parentfield}.${String(prop)}`;
  const advice = `re-acquire it with page.rows("${parentfield}")`;
  const source = runningSource();
  const error = new Error(
    `${path} — this row is no longer in the document; ${advice}`,
  );
  const sentence = `${source} reached ${path} on a row that has been removed — ${advice}`;
  console.error(`[record-page] ${sentence}`);
  reportCustomizationError(error, { source, event: `removed-row:${parentfield}` });
  toastScriptError(`removed-row:${parentfield}:${source}`, sentence);
  throw error;
}

/** A refused `trigger` is a dev warning and a no-op, not a throw: the row is
 *  fine, the argument is wrong, and the rest of the handler is still worth
 *  running — unlike a write that has nowhere to land. */
function refuseTrigger(message: string): false {
  warnOnce(message);
  return false;
}

const warned = new Set<string>();

function warnOnce(message: string) {
  if (!import.meta.env.DEV || warned.has(message)) return;
  warned.add(message);
  console.warn(`[record-page] ${message}`);
}

/** Test seam: the warn-once memory is module state. */
export function resetRowWarnings(): void {
  warned.clear();
}

/** The same once-per-session warning, for the row facts the controller knows. */
export { warnOnce as warnRowIssue };
