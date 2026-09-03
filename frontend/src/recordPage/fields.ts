// The fields surface: a script overrides properties of fields authored elsewhere.
// Ops are recorded, not applied; `resolve()` folds them into one patch per field.
import { markRaw, shallowReactive } from "vue";
import { mapField } from "@framework/ui/components/FormLayout/buildLayoutFromMeta";
import type { Decorator } from "@framework/ui/components/FormLayout/buildLayoutFromMeta";
import { resolveFieldConditionals } from "@framework/ui/components/FormLayout/resolveLayout";
import type { RawMetaField } from "@framework/ui/components/FormLayout/types";
import type { FieldAccess } from "@framework/ui/composables/useDocPermissions";
import { withAccess } from "./formLayoutSource/fieldAccess";
import { applyFieldPatch, type FieldPatch } from "./formLayoutSource/fieldPatch";
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
  /** Handed back as itself, not a read-only view: comparing and re-feeding it is the point. */
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
 * The vocabulary and where each key lands. `hidden`/`read_only`/`reqd` are recomputed
 * on every keystroke from `depends_on`, so they ride the slot applied last.
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
  // The stamp is what tells the outbound read-only wrapper to leave the component alone.
  component: { on: "ui", as: "component", coerce: markRaw, opaque: true },
  props: { on: "ui", as: "props" },
};

/** The reader's keys, derived from the writer's so a key added above is read back from the right slot. */
const SNAPSHOT_KEYS = Object.entries(PATCH_KEYS);

export interface FieldsSurfaceHost {
  /** The doctype's flat meta `fields`; absent until the meta lands. */
  fields: () => RawMetaField[] | undefined;
  /** The draft document conditional expressions resolve against. */
  doc: () => Record<string, any>;
  fieldAccess: (fieldname: string) => FieldAccess;
  /** The host's per-field overlay hook; without it `get` would report a `component` the renderer disagrees with. */
  decorate?: Decorator;
}

type Op =
  | { verb: "hide" | "show"; fieldname: string }
  | { verb: "update"; fieldname: string; patch: FieldPatch };

export class FieldsSurface implements PageFields {
  // Reactive so the host's layout re-joins on a replay. Shallow: a deep proxy would
  // hand `v-bind` a Proxy of whatever a script put in `props`, breaking a class instance.
  private ops: Op[] = shallowReactive([]);
  // The replay's ops until it commits, so a script-hidden field does not flash into
  // view for a tick on every save. Non-null only inside a replay.
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
    // Named before the keys are read, so a mistyped fieldname is heard first.
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
    // The same calls the join makes, in the same order, so the reader cannot drift from the renderer.
    const node = mapField(
      withAccess(raw, (field) => this.host.fieldAccess(field.fieldname)),
      {},
      this.host.decorate,
    );
    // Over the replay in flight when there is one, as `Surface.has` reads: a source
    // reading back its own `refresh` work is told about it, not about last replay's.
    const patched = applyFieldPatch(node, this.fold(this.pending ?? this.ops)[fieldname]);
    const resolved = resolveFieldConditionals(patched, this.host.doc());
    return readOnly(snapshot(resolved), SNAPSHOT_IS_READ_ONLY);
  }

  // Host side, below: not part of what a script may call.

  /** Opens a replay: ops from here are staged. Counted, so a nested `page.refresh()` re-enters. */
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
   * One patch per field, in op order, later keys winning. A `Map`, not an object
   * literal: a script-chosen `"__proto__"` would otherwise land on `Object.prototype`.
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

  /** Layout breaks are excluded: `joinLayout` drops them before any patch could apply. */
  private raw(fieldname: string): RawMetaField | undefined {
    const field = this.host
      .fields()
      ?.find((one) => one.fieldname === fieldname);
    return field && !LAYOUT_BREAKS.has(field.fieldtype) ? field : undefined;
  }

  /**
   * The op is recorded either way: before the meta lands, "absent" and "not here
   * yet" are indistinguishable, and dropping it would lose it for good.
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
    // `hasOwn`, or `toString` and `constructor` would slip through as truthy prototype members.
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

/** Reads a resolved node back in the vocabulary `update` writes; the internal node carries far more. */
function snapshot(resolved: Record<string, any>): PageField {
  const field: PageField = {
    fieldname: resolved.fieldname,
    fieldtype: resolved.fieldtype,
  };
  for (const [key, { on, as, opaque }] of SNAPSHOT_KEYS) {
    const value = on === "ui" ? resolved.ui?.[as] : resolved[as];
    if (value === undefined) continue;
    // A decorator's component arrives unstamped; stamp it so the wrapper leaves it alone.
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
