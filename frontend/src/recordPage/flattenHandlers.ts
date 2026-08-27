// A table's handlers nest under its fieldname (ticket 54), and the engine
// dispatches against one flat keyspace — so the authored shape is flattened
// here, once, at the choke point every script passes through.
//
//   products: { onAdd, onRemove, qty }  →  'products.onAdd', 'products.onRemove',
//                                          'products.qty'
//
// The lifecycle events are spelled `onAdd` / `onRemove` rather than `add` /
// `remove` because `add` is a legal, unreserved fieldname: `products.add` is the
// same string as the commit event of a child field called `add`, which is the
// collision ticket 45 rejected the underscore spelling for and then shipped one
// level down. `on`-prefixing moves the lifecycle keys out of the fieldname
// namespace, and the two child fields that could still collide are warned about
// by name at load (`createRecordPage`) — an announced capability hole rather
// than a silent misfire.
import type { AuthoredHandlers, Handler, RecordPageHandlers } from "./types";

/** The lifecycle half of a table's vocabulary, in the one spelling used end to end. */
export const ROW_EVENTS = { add: "onAdd", remove: "onRemove" } as const;

export function flattenHandlers(
  authored: AuthoredHandlers,
  source: string,
  doctype: string,
): RecordPageHandlers {
  // Null-prototype, so `handlers[event]` can only answer with what the author
  // wrote: a doctype may have a field called `constructor` or `toString`, and
  // an inherited hit there would dispatch an event to `Object.prototype`.
  const flat: RecordPageHandlers = Object.create(null);
  const said = (key: string, message: string) =>
    warn(`${source}.${key} on ${doctype} ${message}`);

  const put = (key: string, handler: Handler) => {
    // Both spellings are accepted, so one can quietly land on the other. Last
    // wins, as it would anywhere else — but not in silence, in a module that
    // names every other authoring mistake.
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
    // Vacuously a block of functions, and the one authoring mistake this would
    // otherwise wave through.
    if (!nested.length) said(key, "is an empty block — it registers nothing");
    for (const [child, handler] of nested) put(`${key}.${child}`, handler);
  }
  return flat;
}

/**
 * The spelling this replaced, named at the one moment the engine can say what to
 * write instead. It is a *legal* key — a child field may genuinely be called
 * `add`, which is the whole reason the lifecycle names moved — so this is advice
 * rather than a refusal, and it belongs here rather than in the vocabulary
 * check, which has no reason to doubt a key it can resolve.
 *
 * The underscore spelling is deliberately not named here: `<parent>_add` is an
 * ordinary parent fieldname, and accusing one would be a warning that lies. The
 * vocabulary check already names it if it is not a fieldname at all.
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

/**
 * A plain object of functions and nothing else. Anything else nested under a
 * fieldname is a mistake the author wants named rather than a shape to guess
 * at — and a non-function value would flatten to a key that could never fire.
 */
function isHandlerBlock(value: unknown): value is Record<string, Handler> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const proto = Object.getPrototypeOf(value);
  if (proto !== Object.prototype && proto !== null) return false;
  return Object.values(value).every((one) => typeof one === "function");
}

function warn(message: string) {
  if (import.meta.env.DEV) console.warn(`[record-page] ${message}`);
}
