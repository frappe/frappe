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
import { runningSource } from "./context";
import { StagedOps } from "./staging";
import type {
  FormLayoutSchema,
  Tab,
  TabOverride,
} from "@framework/ui/components/FormLayout/types";
import { readOnly, type ReadOnlyAdvice } from "./readOnly";
import type { PageFormTab, PageFormTabPatch, PageFormTabs } from "./types";

const SNAPSHOT_IS_READ_ONLY: ReadOnlyAdvice = {
  path: "page.form.tabs.get()",
  instead:
    "page.form.tabs.hide(identity) / .show(identity) / .update(identity, { label })",
};

export interface FormTabsSurfaceHost {
  /** The record's Details layout before this surface's ops, hidden tabs included. */
  tabs: () => FormLayoutSchema | undefined;
  /** The draft document conditional expressions resolve against. */
  doc: () => Record<string, any>;
}

type Op =
  | { verb: "hide" | "show"; source: string; identity: string }
  | { verb: "update"; source: string; identity: string; patch: TabOverride }
  | { verb: "clear"; source: string };

export class FormTabsSurface implements PageFormTabs {
  // Reactive so the host's layout re-joins on a replay; shallow for the reason `FieldsSurface` gives.
  // Staged until the replay or hold commits: rendering a replay's middle tears the
  // strip down and takes the reader's place in it with them.
  private staged = new StagedOps<Op>(shallowReactive([]));

  /** Installed by `createRecordPage`, which reads it from the host's strip. */
  declare readonly active: string;
  /** Installed there too: a miss on one strip wants to name the other. */
  declare activate: (identity: string) => void;

  constructor(private host: FormTabsSurfaceHost) {}

  hide(identity: string) {
    this.record({ verb: "hide", source: runningSource(), identity });
    this.warnIfAbsent(identity, "hide");
  }

  show(identity: string) {
    this.record({ verb: "show", source: runningSource(), identity });
    this.warnIfAbsent(identity, "show");
  }

  update(identity: string, patch: PageFormTabPatch) {
    // Named before the keys are read, so a mistyped identity is heard first.
    this.warnIfAbsent(identity, "update");
    this.record({
      verb: "update",
      source: runningSource(),
      identity,
      patch: translate(identity, patch),
    });
  }

  /** Every tab the layout carries at the call; a later `show` brings one back. */
  clear() {
    this.record({ verb: "clear", source: runningSource() });
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

  /** Whether the tab is on the strip right now, the replay or hold in flight included. */
  isVisible(identity: string) {
    const tab = this.resolved().find((one) => one.identity === identity);
    return !!tab && !tab.hidden;
  }

  /** Open a replay: ops recorded from here are staged, not applied. */
  beginReplay() {
    this.staged.beginReplay();
  }

  /** Opens a hold: ops stage over what is drawn until the last open replay or hold commits. */
  beginHold() {
    this.staged.beginHold();
  }

  commitReplay() {
    this.staged.commit();
  }

  commitHold() {
    this.staged.commit();
  }

  /** Draws what has staged so far, less one source's ops, and keeps staging. */
  publishStaged(except?: string) {
    this.staged.publishStaged(except);
  }

  /** The applied overlay: committed ops only, never a replay or hold in flight. */
  resolve(): Record<string, TabOverride> {
    return this.fold(this.staged.committed);
  }

  private record(op: Op) {
    this.staged.record(op);
  }

  /** One override per tab, in op order. A `Map`, not an object, for the reason `FieldsSurface.fold` gives. */
  private fold(ops: Op[]): Record<string, TabOverride> {
    const overrides = new Map<string, TabOverride>();
    const into = (identity: string) => {
      let override = overrides.get(identity);
      if (!override) overrides.set(identity, (override = {}));
      return override;
    };
    for (const op of ops) {
      if (op.verb === "clear") {
        for (const tab of this.identified()) into(tab.identity).hidden = true;
      } else if (op.verb === "update") Object.assign(into(op.identity), op.patch);
      else into(op.identity).hidden = op.verb === "hide";
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
    const overrides = this.fold(this.staged.current);
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
    warnOnce(`page.form.tabs.${verb}("${identity}") — no such tab.`);
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
        ? `page.form.tabs.update("${identity}", { hidden }) — use hide()/show(); dropped.`
        : `page.form.tabs.update("${identity}", { ${key} }) — not a tab property a script may set; dropped.`,
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
