// The fields surface (wayfinder ticket 42) — clause 2 of the v1-parity map.
//
// Not a `Surface`. The four list surfaces arrange items a script may also
// create; fields are a set authored elsewhere whose *properties* a script
// overrides, so the verbs are a strict subset and the key is a fieldname
// rather than an item name.
//
// Ops are recorded, not applied: `resolve()` folds them into one patch per
// field, which the host hands to `useFormLayout` as plain data. That keeps the
// override a render-time overlay — nothing is written into the layout, the Form
// Layout row or the doctype meta — and makes `reset()` the whole of the replay
// clear, so an authored script is a plain `if` with no `else`.
import { markRaw, shallowReactive } from "vue";
import { mapField } from "../../components/FormLayout/buildLayoutFromMeta";
import type { Decorator } from "../../components/FormLayout/buildLayoutFromMeta";
import { resolveFieldConditionals } from "../../components/FormLayout/resolveLayout";
import type { RawMetaField } from "../../components/FormLayout/types";
import type { FieldAccess } from "../../composables/useDocPermissions";
import { withAccess } from "../FormLayoutSource/fieldAccess";
import { applyFieldPatch, type FieldPatch } from "../FormLayoutSource/fieldPatch";
import { readOnly, type ReadOnlyAdvice } from "./readOnly";
import type { PageField, PageFieldPatch, PageFields } from "./types";

const SNAPSHOT_IS_READ_ONLY: ReadOnlyAdvice = {
  path: "page.fields.get()",
  instead: "page.fields.update(fieldname, { … }), which is the writable half",
};

/** What `joinLayout` drops before any patch could apply. */
export const LAYOUT_BREAKS = new Set([
  "Tab Break",
  "Section Break",
  "Column Break",
]);

type Slot = "meta" | "override" | "ui";

interface Landing {
  /** Which half of the `FieldPatch` this key lands on. */
  on: Slot;
  /** Its name there — the pipeline is camelCase, the script vocabulary is not. */
  as: string;
  coerce?: (value: any) => any;
  /**
   * A reference rather than data, so it is handed back as itself: comparing and
   * re-feeding it is the point, and a read-only view of a component's options
   * breaks both. `markRaw` is how that is said to the rest of Vue.
   */
  opaque?: boolean;
}

const asBoolean = (value: any) => !!value;

/** Meta writes `precision` as a number; a script may reasonably say `"2"`. */
function asPrecision(value: any): number | undefined {
  if (value == null || value === "") return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

/**
 * The enumerated vocabulary and where each key goes: v1's ten minus
 * `button_color` (nothing renders it), plus `component`/`props`, which
 * `FieldUI` already carries through the render path.
 *
 * The split is not cosmetic. `hidden`/`read_only`/`reqd` are recomputed on
 * every keystroke from the `depends_on` family, so they ride the carrier
 * `resolveFieldConditionals` applies last; the rest are computed once when the
 * node is built, so they are merged there.
 */
const PATCH_KEYS: Record<string, Landing> = {
  hidden: { on: "override", as: "hidden", coerce: asBoolean },
  read_only: { on: "override", as: "readOnly", coerce: asBoolean },
  reqd: { on: "override", as: "reqd", coerce: asBoolean },
  label: { on: "meta", as: "label" },
  placeholder: { on: "meta", as: "placeholder" },
  description: { on: "meta", as: "description" },
  options: { on: "meta", as: "options" },
  link_filters: { on: "meta", as: "filters" },
  precision: { on: "meta", as: "precision", coerce: asPrecision },
  // Belt and braces beside `shallowReactive` — and the stamp is also what tells
  // the outbound read-only wrapper to leave the component alone.
  component: { on: "ui", as: "component", coerce: markRaw, opaque: true },
  props: { on: "ui", as: "props" },
};

/**
 * The reader's key list, derived from the writer's rather than written twice —
 * and carrying each key's whole landing, so a key added above is read back from
 * the right slot without anyone remembering to come here.
 */
const SNAPSHOT_KEYS = Object.entries(PATCH_KEYS);

export interface FieldsSurfaceHost {
  /** The doctype's flat meta `fields`; absent until the meta lands. */
  fields: () => RawMetaField[] | undefined;
  /** The draft document conditional expressions resolve against. */
  doc: () => Record<string, any>;
  fieldAccess: (fieldname: string) => FieldAccess;
  /**
   * The same per-field UI overlay hook the host passes its layout source. `get`
   * needs it or it would report `component`/`props` the renderer disagrees
   * with, which is the asymmetry `get` exists to abolish.
   */
  decorate?: Decorator;
}

type Op =
  | { verb: "hide" | "show"; fieldname: string }
  | { verb: "update"; fieldname: string; patch: FieldPatch };

export class FieldsSurface implements PageFields {
  // Reactive so the host's layout re-joins when a replay changes the overlay,
  // exactly as the four list surfaces re-resolve. *Shallow*: a deep proxy would
  // reach inside a patch's `props` and hand `v-bind` a Proxy of whatever a
  // script put there — a nested component, a `Date`, a class instance — which
  // is the internal-slots hazard `readOnly.ts` documents for its own wrapper.
  private ops: Op[] = shallowReactive([]);
  // The replay's ops until it commits, so the host's overlay never carries a
  // half-applied replay — which is what made a script-hidden field flash into
  // view for a tick on every save. Non-null only inside a replay; see
  // `Surface.beginReplay`, which this mirrors.
  private pending: Op[] | null = null;
  private replaying = 0;

  constructor(private host: FieldsSurfaceHost) {}

  hide(fieldname: string) {
    this.record({ verb: "hide", fieldname });
    this.warnIfAbsent(fieldname, "hide");
  }

  show(fieldname: string) {
    this.record({ verb: "show", fieldname });
    this.warnIfAbsent(fieldname, "show");
  }

  update(fieldname: string, patch: PageFieldPatch) {
    // Named before the keys are read, so an author who mistyped the fieldname
    // hears that first rather than after a list of keys it would never reach.
    this.warnIfAbsent(fieldname, "update");
    this.record({ verb: "update", fieldname, patch: translate(fieldname, patch) });
  }

  has(fieldname: string) {
    return !!this.raw(fieldname);
  }

  get(fieldname: string): PageField | null {
    const raw = this.raw(fieldname);
    if (!raw) {
      this.warnIfAbsent(fieldname, "get");
      return null;
    }
    // The same three calls the join makes for one field, in the same order, so
    // the reader cannot drift from what the renderer decided.
    const node = mapField(
      withAccess(raw, (field) => this.host.fieldAccess(field.fieldname)),
      {},
      this.host.decorate,
    );
    // Over the replay in flight when there is one, the same way `Surface.has`
    // reads: a source that hides a field and then reads it back inside its own
    // `refresh` handler is told about its own work, not about last replay's.
    const patched = applyFieldPatch(node, this.fold(this.pending ?? this.ops)[fieldname]);
    const resolved = resolveFieldConditionals(patched, this.host.doc());
    return readOnly(snapshot(resolved), SNAPSHOT_IS_READ_ONLY);
  }

  // Host side, below: not part of what a script may call.

  /**
   * Open a replay: ops recorded from here are staged, not applied. The clear is
   * the replay clear `reset()` used to be — the next commit starts from the
   * authored layout alone. Counted, so a nested `page.refresh()` re-enters
   * without publishing a half-built overlay.
   */
  beginReplay() {
    this.pending = [];
    this.replaying += 1;
  }

  /** Close a replay: the outermost one publishes the staged ops in one flush. */
  commitReplay() {
    if (this.replaying === 0) return;
    this.replaying -= 1;
    if (this.replaying > 0) return;
    const staged = this.pending ?? [];
    this.pending = null;
    this.ops.splice(0, this.ops.length, ...staged);
  }

  /** The applied overlay: committed ops only, never a replay in flight. */
  resolve(): Record<string, FieldPatch> {
    return this.fold(this.ops);
  }

  private record(op: Op) {
    (this.pending ?? this.ops).push(op);
  }

  /**
   * One patch per field, in op order — later verbs win, key by key.
   *
   * Folded in a `Map`, not an object literal: a fieldname is a string a script
   * chooses, and `patches["__proto__"] ??= {}` would leave `into` pointing at
   * `Object.prototype`, so the next `override.hidden` would be inherited by
   * every field object in the application for the rest of the session.
   */
  private fold(ops: Op[]): Record<string, FieldPatch> {
    const patches = new Map<string, FieldPatch>();
    for (const op of ops) {
      let into = patches.get(op.fieldname);
      if (!into) patches.set(op.fieldname, (into = {}));
      if (op.verb === "update") mergeInto(into, op.patch);
      else (into.override ??= {}).hidden = op.verb === "hide";
    }
    return Object.fromEntries(patches);
  }

  /**
   * Layout breaks are excluded: `joinLayout` drops them before any patch is
   * applied, so an override on one could never render, and sections and tabs
   * have their own surfaces anyway.
   */
  private raw(fieldname: string): RawMetaField | undefined {
    const field = this.host
      .fields()
      ?.find((one) => one.fieldname === fieldname);
    return field && !LAYOUT_BREAKS.has(field.fieldtype) ? field : undefined;
  }

  /**
   * The op is recorded either way — a patch keyed by a fieldname the layout
   * does not carry is simply never applied, and dropping it here would lose it
   * for good in the window before the meta lands, when "absent" and "not here
   * yet" are indistinguishable. This only says so when it can tell.
   */
  private warnIfAbsent(fieldname: string, verb: string) {
    const fields = this.host.fields();
    if (!fields || this.raw(fieldname)) return;
    warnOnce(`page.fields.${verb}("${fieldname}") — no such field.`);
  }
}

/** Translate the script's vocabulary into the pipeline's, dropping the rest. */
function translate(fieldname: string, patch: PageFieldPatch): FieldPatch {
  const translated: FieldPatch = {};
  for (const [key, value] of Object.entries(patch)) {
    // `hasOwn`, or `toString` and `constructor` would each resolve to a truthy
    // `Object.prototype` member and slip through the enumeration unwarned.
    const landing = Object.hasOwn(PATCH_KEYS, key) ? PATCH_KEYS[key] : undefined;
    if (!landing) {
      warnOnce(
        `page.fields.update("${fieldname}", { ${key} }) — not a field property a script may set; dropped.`,
      );
      continue;
    }
    const slot = (translated[landing.on] ??= {}) as Record<string, any>;
    slot[landing.as] = landing.coerce ? landing.coerce(value) : value;
  }
  return translated;
}

/** Shallow per half: two patches for one field merge key by key, last wins. */
function mergeInto(into: FieldPatch, from: FieldPatch) {
  if (from.meta) into.meta = { ...into.meta, ...from.meta };
  if (from.override) into.override = { ...into.override, ...from.override };
  if (from.ui) into.ui = { ...into.ui, ...from.ui };
}

/**
 * Read a resolved node back out in the vocabulary `update` writes. Curated the
 * same way, and for the same reason: the internal node also carries the child
 * doctype's whole layout, the raw conditional expressions and the permission
 * bookkeeping, none of which is a field property a script asked about.
 */
function snapshot(resolved: Record<string, any>): PageField {
  const field: PageField = {
    fieldname: resolved.fieldname,
    fieldtype: resolved.fieldtype,
  };
  for (const [key, { on, as, opaque }] of SNAPSHOT_KEYS) {
    const value = on === "ui" ? resolved.ui?.[as] : resolved[as];
    if (value === undefined) continue;
    // A decorator's component arrives unstamped, unlike one a script passed
    // through `update` — stamp it here so the wrapper below leaves it alone.
    (field as Record<string, any>)[key] = opaque ? markRaw(value) : value;
  }
  return field;
}

const warned = new Set<string>();

function warnOnce(message: string) {
  if (!import.meta.env.DEV || warned.has(message)) return;
  warned.add(message);
  console.warn(`[record-page] ${message}`);
}

/** Test seam: the warn-once memory is module state. */
export function resetFieldWarnings(): void {
  warned.clear();
}
