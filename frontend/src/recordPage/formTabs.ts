// The Form Layout tabs surface: the strip inside the record's Details form, whose
// tabs a script overrides but cannot add. Modelled on `FieldsSurface`.
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
  /** The record's Details layout before this surface's ops, hidden tabs included. */
  tabs: () => FormLayoutSchema | undefined;
  /** The draft document conditional expressions resolve against. */
  doc: () => Record<string, any>;
}

type Op =
  | { verb: "hide" | "show"; identity: string }
  | { verb: "update"; identity: string; patch: TabOverride };

export class FormTabsSurface implements PageFormTabs {
  // Reactive so the host's layout re-joins on a replay; shallow for the reason `FieldsSurface` gives.
  private ops: Op[] = shallowReactive([]);
  // The replay's ops until it commits: rendering a replay's middle tears the strip
  // down and takes the reader's place in it with them.
  private pending: Op[] | null = null;
  private replaying = 0;

  /** Installed by `createRecordPage`, which reads it from the host's strip. */
  declare readonly active: string;
  /** Installed there too: a miss on one strip wants to name the other. */
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
    // Named before the keys are read, so a mistyped identity is heard first.
    this.warnIfAbsent(identity, "update");
    this.record({ verb: "update", identity, patch: translate(identity, patch) });
  }

  has(identity: string) {
    return !!this.raw(identity);
  }

  get(identity: string): PageFormTab | null {
    // Every tab, not just the one asked for: the strip's label fallback depends
    // on how many tabs are visible beside it.
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

  /** Whether the tab is on the strip right now, the replay in flight included. */
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

  /** One override per tab, in op order. A `Map`, not an object, for the reason `FieldsSurface.fold` gives. */
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
   * The strip as it stands: `depends_on` against the doc, then the ops over the
   * replay in flight, so a source reading back its own `onRefresh` work is told about it.
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

  /** The same identities `FormLayout` resolves, so the two cannot disagree about an address. */
  private identified() {
    return identifyTabs(this.host.tabs() ?? []);
  }

  /**
   * The op is recorded either way: before the layout lands, "absent" and "not
   * here yet" are indistinguishable, and dropping it would lose it for good.
   */
  private warnIfAbsent(identity: string, verb: string) {
    const tabs = this.host.tabs();
    if (!tabs?.length || this.raw(identity)) return;
    warnOnce(`page.formTabs.${verb}("${identity}") — no such tab.`);
  }
}

/**
 * `label` and nothing else: `hidden` is `hide`/`show`'s, and `dependsOn` is not
 * patchable, since a script wanting conditional visibility has an `if` in `onRefresh`.
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
