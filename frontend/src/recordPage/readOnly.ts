// The outbound half of the compatibility policy (wayfinder ticket 47): every
// object `page` hands back is read-only. Ticket 20 curated what goes *in* to
// `page`; nothing said what a script may do to what comes back out, and the
// answer was "corrupt the application" — `page.roles` is a module-level array
// shared by the whole session, `page.perms` a memoised view shared by every
// source, `page.meta` a cached resource that outlives navigation to another
// doctype.
//
// A write is refused, not softened: it reports on the tombstone channel and
// throws, which aborts the rest of the handler. The engine already skips a
// throwing handler half-applied and this is not the exception (47 §3) —
// report-but-continue is the silent no-op wearing a report.
//
// Not deep-freeze. A frozen object is non-extensible, Vue 3's `getTargetType`
// returns INVALID for a non-extensible target, and `reactive()` then hands the
// raw object back — meta would stop being deeply reactive. That is a repo-wide
// reactivity change, and it stays addable underneath this Proxy later.
import { runningSource } from "./context";
import { toastScriptError } from "./pageScripts";
import { reportCustomizationError } from "./reportError";

/**
 * What to write instead, per wrapped member. A bare `TypeError` names nothing;
 * the whole reason this is a redirect rather than a removal is that there is a
 * supported verb to point at.
 */
export interface ReadOnlyAdvice {
  /** Dotted path to the member: `"page.meta"`. Nested writes extend it. */
  path: string;
  /** The verb that does support this: `"page.fields.update(...)"`. */
  instead: string;
}

// Raw object to wrapper. Mandatory, not an optimisation: without it every read
// allocates a fresh Proxy, `page.meta.fields[0] !== page.meta.fields[0]`, and
// `.indexOf()` / `.includes()` / any identity comparison quietly misbehaves.
//
// It also fixes the reported path to the one the object was *first* reached
// through, when the same object is reachable two ways. That is the price of the
// identity guarantee, and identity is the one that breaks working scripts.
const wrappers = new WeakMap<object, any>();

// Wrapping a wrapper would nest two Proxies and report the inner path twice.
// Nothing does it today — every wrap starts from a raw host value — but this is
// one lookup to make it impossible rather than a rule to remember.
const wrapped = new WeakSet<object>();

/**
 * Wraps `value` so reads pass through and writes throw. Lazy and recursive: a
 * nested object is wrapped when it is read, not walked up front, so an untouched
 * meta costs nothing.
 */
export function readOnly<T>(value: T, advice: ReadOnlyAdvice): T {
  return wrap(value, advice.path, advice) as T;
}

// `member` is the wrap's root, fixed for the whole descent: the message names
// the full path, because the author has to find the line, but the report and the
// toast are keyed on the member, so a script that walks an array writing to
// every row of it files one row rather than one per row.
function wrap(value: unknown, path: string, member: ReadOnlyAdvice): unknown {
  if (!wrappable(value)) return value;
  const target = value as object;
  if (wrapped.has(target)) return target;
  const existing = wrappers.get(target);
  if (existing) return existing;

  const refusal = (key: string | symbol) => ({
    path: step(target, path, key),
    member,
  });

  const wrapper = new Proxy(target, {
    get(owner, key, receiver) {
      const read = Reflect.get(owner, key, receiver);
      // A Proxy must hand back a non-configurable, non-writable property
      // exactly as the target holds it, or the engine throws on the read. That
      // is not hypothetical here: deep-freezing meta at source stays on the
      // table (ticket 47 §1), and the day it happens this would start throwing
      // TypeErrors on every read instead of quietly staying correct.
      if (fixed(owner, key)) return read;
      return wrap(read, step(owner, path, key), member);
    },
    set(_owner, key) {
      return refuse(refusal(key));
    },
    defineProperty(_owner, key) {
      return refuse(refusal(key));
    },
    deleteProperty(_owner, key) {
      return refuse(refusal(key));
    },
  });

  wrappers.set(target, wrapper);
  wrapped.add(wrapper);
  return wrapper;
}

function fixed(target: object, key: string | symbol) {
  const descriptor = Object.getOwnPropertyDescriptor(target, key);
  return !!descriptor && !descriptor.configurable && !descriptor.writable;
}

// Arrays and plain objects only. A `Date`, a `Map` or any class instance keeps
// its internal slots, which a Proxy receiver breaks the moment a method is
// called on it — and nothing `page` hands back is one of those. Functions pass
// through as themselves: `roles.push` is reached as a function and called on the
// wrapper, so its writes land in the `set` trap anyway. That is the whole of the
// `page.roles.push('System Manager')` fix — no array special case exists.
function wrappable(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return false;
  // `markRaw`'s stamp. A component's options object is a plain object, so it
  // would otherwise be descended into: identity would stop holding
  // (`get('x').component === MyComponent` false), and Vue's own render-time
  // caches onto those options (`__vccOpts`, normalized props) would start
  // throwing from inside a render effect.
  //
  // Asked as an own-property question, not a read: `page.perms` is itself a
  // Proxy that warns about any key it does not recognise, and probing it for
  // `__v_skip` would file that probe as the author's typo.
  if (Object.hasOwn(value, "__v_skip")) return false;
  if (Array.isArray(value)) return true;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

// `page.meta.fields[3].hidden`, not `page.meta` — the author has to be able to
// find the line.
function step(target: object, path: string, key: string | symbol) {
  const name = String(key);
  return Array.isArray(target) ? `${path}[${name}]` : `${path}.${name}`;
}

// Not dev-gated, for the reason `pageCompatibility.ts` gives and this inherits
// unchanged: no production site runs a dev build, and this fires on a site no
// developer is watching.
function refuse(refusal: { path: string; member: ReadOnlyAdvice }): never {
  const { path, member } = refusal;
  const source = runningSource();
  // The thrown message stands alone — it is what a `catch` and the Error Log row
  // carry. The console line and the toast add the attribution around it.
  const error = new Error(`${path} is read-only — use ${member.instead}`);
  const sentence = `${source} wrote to ${path}, which is read-only — use ${member.instead}`;
  console.error(`[record-page] ${sentence}`);
  reportCustomizationError(error, { source, event: `readonly:${member.path}` });
  toastScriptError(`readonly:${source}:${member.path}`, sentence);
  throw error;
}
