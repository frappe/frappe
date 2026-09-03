// How a script addresses a child row: `page.rows('products')` and the handle it hands
// back, which re-finds its row on every access and throws once the row is gone.
import { runningSource } from "./context";
import {
  holdsChildRows,
  identify,
  ROW_ID,
  rowKey,
} from "@framework/ui/components/Fields/rowIdentity";
import type { RawMetaField } from "@framework/ui/components/FormLayout/types";
import type { RowAddress } from "@framework/ui/components/Fields/types";
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

// `markRaw`'s stamp, answered by the traps below: it tells both Vue and the
// outbound read-only guard that a handle is not data to descend into.
const RAW = "__v_skip";

/** What `trigger` will not dispatch: the `on`-prefixed lifecycle keys, not any child fieldname. */
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
  // One handle per address, for the page's life. Mandatory: without it
  // `page.rows('products')[0] !== page.rows('products')[0]` and every `===` a script writes is wrong.
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
   * Every row's key, minted here too so a row a script pushed onto `page.doc` is
   * addressable. A copied row (`{ ...products[0] }`) carries the original's key and is re-minted.
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

    // A bare child fieldname: the handle knows its table and forms the dotted key itself.
    const trigger = (fieldname: string) => {
      required(TRIGGER);
      if (!triggerable(parentfield, fieldname)) return Promise.resolve();
      return host.dispatch(`${parentfield}.${fieldname}`, { parentfield, key });
    };

    // The target is an empty object, not the row: a Proxy may only lie about a
    // target's properties while the target is extensible and owns none.
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
      // A spread copies the row's own fields, not `trigger` or the stamp, and a
      // removed row throws instead of spreading to `{}`; `*` names the whole row.
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

  /** Quiet until the meta lands: only the meta can say a fieldname is not a child table. */
  function holdsRows(parentfield: string): boolean {
    const field = tableField(parentfield);
    if (!host.fields() || field) return true;
    warnOnce(`page.rows("${parentfield}") — not a child table; no rows to address.`);
    return false;
  }

  /**
   * `trigger` dispatches a field event: it refuses the structural keys and a dotted
   * argument, and warns about a fieldname the child doctype does not have.
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

// Vue's reactivity flags are plain strings (`__v_isRef`, `__v_raw`), so the symbol
// test alone would let an `isRef` in a template throw on a removed row inside a render effect.
function probe(prop: string | symbol): boolean {
  return typeof prop === "symbol" || prop.startsWith("__v_");
}

const RAW_DESCRIPTOR: PropertyDescriptor = {
  value: true,
  writable: false,
  enumerable: false,
  configurable: true,
};

/** The thrown `Error` carries the standalone sentence; the console line and the toast add the attribution. */
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

/** A refused `trigger` is a dev warning and a no-op: the row is fine, only the argument is wrong. */
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
