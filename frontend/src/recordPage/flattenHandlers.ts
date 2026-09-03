// A table's handlers nest under its fieldname and the engine dispatches against one
// flat keyspace, so `products: { onAdd, qty }` becomes `'products.onAdd'`, `'products.qty'`.
import type { AuthoredHandlers, Handler, RecordPageHandlers } from "./types";

/**
 * The lifecycle half of a table's vocabulary. `on`-prefixed because `add` is a
 * legal fieldname, and `products.add` would be a child field's commit event.
 */
export const ROW_EVENTS = { add: "onAdd", remove: "onRemove" } as const;

export function flattenHandlers(
  authored: AuthoredHandlers,
  source: string,
  doctype: string,
): RecordPageHandlers {
  // Null-prototype: a doctype may have a field called `constructor` or `toString`,
  // and an inherited hit would dispatch an event to `Object.prototype`.
  const flat: RecordPageHandlers = Object.create(null);
  const said = (key: string, message: string) =>
    warn(`${source}.${key} on ${doctype} ${message}`);

  const put = (key: string, handler: Handler) => {
    // Both spellings are accepted, so one can land on the other; last wins, but not in silence.
    if (key in flat) said(key, "is written twice — the later one wins");
    flat[key] = handler;
  };

  for (const [key, value] of Object.entries(authored)) {
    if (typeof value === "function") {
      warnRetiredSpelling(key, said);
      put(key, value);
      continue;
    }
    if (!isHandlerBlock(value)) {
      said(key, "is neither a handler nor a block of them — ignored");
      continue;
    }
    const nested = Object.entries(value);
    // Vacuously a block of functions, so it would otherwise pass unnoticed.
    if (!nested.length) said(key, "is an empty block — it registers nothing");
    for (const [child, handler] of nested) put(`${key}.${child}`, handler);
  }
  return flat;
}

/**
 * Names the retired `.add`/`.remove` spelling; advice, not a refusal, since a child
 * field may be called `add`. `<parent>_add` is not named: it is an ordinary fieldname.
 */
function warnRetiredSpelling(
  key: string,
  said: (key: string, message: string) => void,
) {
  const dotted = /^(.+)\.(add|remove)$/.exec(key);
  if (!dotted) return;
  const [, table, change] = dotted;
  said(
    key,
    `no longer fires on a row being ${change === "add" ? "added" : "removed"} — write ${table}: { ${ROW_EVENTS[change as "add" | "remove"]}() {} }`,
  );
}

/** A plain object of functions and nothing else; a non-function value would flatten to a key that never fires. */
function isHandlerBlock(value: unknown): value is Record<string, Handler> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const proto = Object.getPrototypeOf(value);
  if (proto !== Object.prototype && proto !== null) return false;
  return Object.values(value).every((one) => typeof one === "function");
}

function warn(message: string) {
  if (import.meta.env.DEV) console.warn(`[record-page] ${message}`);
}
