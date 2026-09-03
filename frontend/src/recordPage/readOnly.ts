// Every object `page` hands back is read-only: reads pass through, writes throw.
//
// Not deep-freeze: a frozen object is non-extensible, so Vue's `reactive()` hands
// back the raw object and `meta` stops being deeply reactive.
import { runningSource } from "./context";
import { toastScriptError } from "./pageScripts";
import { reportCustomizationError } from "./reportError";

/** What to write instead, per wrapped member. */
export interface ReadOnlyAdvice {
  /** Dotted path to the member: `"page.meta"`. Nested writes extend it. */
  path: string;
  /** The verb that does support this: `"page.fields.update(...)"`. */
  instead: string;
}

// Mandatory, not an optimisation: without it every read allocates a fresh Proxy,
// `page.meta.fields[0] !== page.meta.fields[0]`, and identity comparisons misbehave.
const wrappers = new WeakMap<object, any>();

// Wrapping a wrapper would nest two Proxies and report the inner path twice.
const wrapped = new WeakSet<object>();

/** Wraps `value` so reads pass through and writes throw. Lazy and recursive. */
export function readOnly<T>(value: T, advice: ReadOnlyAdvice): T {
  return wrap(value, advice.path, advice) as T;
}

// The report and the toast are keyed on the member, not the path, so a script
// writing to every row of an array files one row.
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
      // A Proxy must hand back a non-configurable, non-writable property exactly
      // as the target holds it, or the engine throws on the read.
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
    // These take no key, so `set` never sees them, and an untrapped operation
    // forwards to the target: `Object.freeze(page.meta)` would lock shared state.
    setPrototypeOf() {
      return refuse({ path: `${path}'s prototype`, member });
    },
    preventExtensions() {
      return refuse({ path: `${path}'s extensibility`, member });
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

// Arrays and plain objects only: a `Date`, a `Map` or a class instance keeps
// internal slots that a Proxy receiver breaks the moment a method is called.
function wrappable(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return false;
  // `markRaw`'s stamp; descending into a marked object breaks Vue's render caches.
  // Asked as an own-property question: `page.perms` files an unknown key as a typo.
  if (Object.hasOwn(value, "__v_skip")) return false;
  if (Array.isArray(value)) return true;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

// `page.meta.fields[3].hidden`, not `page.meta`.
function step(target: object, path: string, key: string | symbol) {
  const name = String(key);
  return Array.isArray(target) ? `${path}[${name}]` : `${path}.${name}`;
}

// Not dev-gated: this fires on a production site no developer is watching.
function refuse(refusal: { path: string; member: ReadOnlyAdvice }): never {
  const { path, member } = refusal;
  const source = runningSource();
  // The thrown message stands alone: it is what a `catch` and the Error Log row carry.
  const error = new Error(`${path} is read-only — use ${member.instead}`);
  const sentence = `${source} wrote to ${path}, which is read-only — use ${member.instead}`;
  console.error(`[record-page] ${sentence}`);
  reportCustomizationError(error, { source, event: `readonly:${member.path}` });
  toastScriptError(`readonly:${source}:${member.path}`, sentence);
  throw error;
}
