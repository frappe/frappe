// The Form Layout tabs surface (wayfinder ticket 73) — the second tab strip,
// the one inside the record's Details form.
//
// Not a `Surface`, and modelled on `FieldsSurface` instead: these tabs are
// authored elsewhere, in a Form Layout an administrator edits, so a script only
// overrides their properties. That makes the verbs a strict subset — no `add`,
// `move` or `order`, since a tab here is a container of *fields* and inventing
// fields is `page.dialog`'s job — and the key an identity rather than a name.
//
// Ops are recorded, not applied: `resolve()` folds them into one override per
// tab, which the host hands to its layout source as plain data. Nothing is
// written into the Form Layout row or the doctype meta, and the replay clear is
// the whole of the undo, so an authored script is a plain `if` with no `else`.
import { shallowReactive } from "vue";
import {
  applyTabOverride,
  resolveTabConditionals,
} from "@framework/ui/components/FormLayout/resolveLayout";
import {
  identifyTabs,
  tabStripLabel,
} from "@framework/ui/components/FormLayout/tabIdentity";
import type {
  FormLayoutSchema,
  Tab,
  TabOverride,
} from "@framework/ui/components/FormLayout/types";
import { readOnly, type ReadOnlyAdvice } from "./readOnly";
import type { PageFormTab, PageFormTabPatch, PageFormTabs } from "./types";

const SNAPSHOT_IS_READ_ONLY: ReadOnlyAdvice = {
  path: "page.formTabs.get()",
  instead:
    "page.formTabs.hide(identity) / .show(identity) / .update(identity, { label })",
};

export interface FormTabsSurfaceHost {
  /**
   * The record's Details layout, as joined and before this surface's ops — the
   * whole authored strip, hidden tabs included, so `has()` answers "did the
   * administrator author this" rather than "is it on screen".
   */
  tabs: () => FormLayoutSchema | undefined;
  /** The draft document conditional expressions resolve against. */
  doc: () => Record<string, any>;
}

type Op =
  | { verb: "hide" | "show"; identity: string }
  | { verb: "update"; identity: string; patch: TabOverride };

export class FormTabsSurface implements PageFormTabs {
  // Reactive so the host's layout re-joins when a replay changes the overlay,
  // shallow for the reason `FieldsSurface` gives.
  private ops: Op[] = shallowReactive([]);
  // The replay's ops until it commits, so the host never renders a replay's
  // middle — which on this surface would tear the strip down and take the
  // reader's place in it with them (ticket 70).
  private pending: Op[] | null = null;
  private replaying = 0;

  /** Installed by `createRecordPage`, which reads it from the host's strip. */
  declare readonly active: string;
  /** Installed there too: a miss on one strip wants to name the other, and
   *  `createRecordPage` is the one place that holds both. */
  declare activate: (identity: string) => void;

  constructor(private host: FormTabsSurfaceHost) {}

  hide(identity: string) {
    this.record({ verb: "hide", identity });
    this.warnIfAbsent(identity, "hide");
  }

  show(identity: string) {
    this.record({ verb: "show", identity });
    this.warnIfAbsent(identity, "show");
  }

  update(identity: string, patch: PageFormTabPatch) {
    // Named before the keys are read, so an author who mistyped the identity
    // hears that first rather than after a list of keys it would never reach.
    this.warnIfAbsent(identity, "update");
    this.record({ verb: "update", identity, patch: translate(identity, patch) });
  }

  has(identity: string) {
    return !!this.raw(identity);
  }

  get(identity: string): PageFormTab | null {
    // Every tab, not just the one asked for: the strip's label fallback depends
    // on how many tabs are visible beside it, and a `get` that reported a label
    // the button does not carry is the asymmetry `get` exists to abolish.
    const strip = this.resolved();
    const tab = strip.find((one) => one.identity === identity);
    if (!tab) {
      this.warnIfAbsent(identity, "get");
      return null;
    }
    const multipleTabs = strip.filter((one) => !one.hidden).length > 1;
    return readOnly(
      {
        name: tab.name,
        identity,
        label: tabStripLabel(tab.label, multipleTabs),
        hidden: tab.hidden,
      },
      SNAPSHOT_IS_READ_ONLY,
    );
  }

  // Host side, below: not part of what a script may call.

  /**
   * Whether the tab is on the strip right now — `depends_on` and this surface's
   * ops both folded in, the replay in flight included. What `activate` asks to
   * tell a hidden tab from one the administrator never authored.
   */
  isVisible(identity: string) {
    const tab = this.resolved().find((one) => one.identity === identity);
    return !!tab && !tab.hidden;
  }

  /** Open a replay: ops recorded from here are staged, not applied. */
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
  resolve(): Record<string, TabOverride> {
    return this.fold(this.ops);
  }

  private record(op: Op) {
    (this.pending ?? this.ops).push(op);
  }

  /**
   * One override per tab, in op order — later verbs win, key by key. Folded in
   * a `Map` for the reason `FieldsSurface.fold` gives: an identity is a string
   * a script chooses, and `"__proto__"` would otherwise be written onto
   * `Object.prototype`.
   */
  private fold(ops: Op[]): Record<string, TabOverride> {
    const overrides = new Map<string, TabOverride>();
    for (const op of ops) {
      let into = overrides.get(op.identity);
      if (!into) overrides.set(op.identity, (into = {}));
      if (op.verb === "update") Object.assign(into, op.patch);
      else into.hidden = op.verb === "hide";
    }
    return Object.fromEntries(overrides);
  }

  private raw(identity: string): (Tab & { identity: string }) | undefined {
    return this.identified().find((tab) => tab.identity === identity);
  }

  /**
   * The strip as it stands: `depends_on` baked against the doc, then the ops
   * over the replay in flight when there is one — the same way `Surface.has`
   * reads, so a source that hides a tab and reads it back inside its own
   * `onRefresh` handler is told about its own work, not about last replay's.
   */
  private resolved() {
    const overrides = this.fold(this.pending ?? this.ops);
    const doc = this.host.doc();
    return this.identified().map((tab) => {
      const conditional = resolveTabConditionals(
        { ...tab, override: overrides[tab.identity] },
        doc,
      );
      return { ...conditional, ...applyTabOverride(conditional) };
    });
  }

  /**
   * The same identities `FormLayout` resolves: the join leaves every tab's
   * `name` and authored `label` alone, and this reads the layout the form is
   * handed, so the two cannot disagree about what a script's address means.
   */
  private identified() {
    return identifyTabs(this.host.tabs() ?? []);
  }

  /**
   * The op is recorded either way — an override keyed by a tab the layout does
   * not carry is simply never applied, and dropping it here would lose it for
   * good in the window before the layout lands, when "absent" and "not here
   * yet" are indistinguishable. This only says so when it can tell.
   */
  private warnIfAbsent(identity: string, verb: string) {
    const tabs = this.host.tabs();
    if (!tabs?.length || this.raw(identity)) return;
    warnOnce(`page.formTabs.${verb}("${identity}") — no such tab.`);
  }
}

/**
 * `label` and nothing else. `hidden` is `hide`/`show`'s, and `dependsOn` is
 * deliberately not patchable: rewriting the administrator's expression *string*
 * is the two-authorities objection in its one genuinely bad form, and a script
 * wanting conditional visibility already has a real `if` in `onRefresh`.
 */
function translate(identity: string, patch: PageFormTabPatch): TabOverride {
  const translated: TabOverride = {};
  for (const [key, value] of Object.entries(patch)) {
    if (key === "label") {
      translated.label = value as string;
      continue;
    }
    warnOnce(
      key === "hidden"
        ? `page.formTabs.update("${identity}", { hidden }) — use hide()/show(); dropped.`
        : `page.formTabs.update("${identity}", { ${key} }) — not a tab property a script may set; dropped.`,
    );
  }
  return translated;
}

const warned = new Set<string>();

function warnOnce(message: string) {
  if (!import.meta.env.DEV || warned.has(message)) return;
  warned.add(message);
  console.warn(`[record-page] ${message}`);
}

/** Test seam: the warn-once memory is module state. */
export function resetFormTabWarnings(): void {
  warned.clear();
}
