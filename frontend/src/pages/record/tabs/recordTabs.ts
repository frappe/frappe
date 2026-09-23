// The record's tab strip, host side: the four built-ins, the tab the address names, and its moves.
import { ref, watch, type Ref } from "vue";
import type { LocationQueryValue, RouteLocationNormalizedLoaded, Router } from "vue-router";
import type { Surface } from "@/recordPage/surface";
import type { TabItem } from "@/recordPage/types";
import { __ } from "@/i18n";

export const DETAILS_TAB = "details";

/** Every doctype's strip, in order; a script hides what its doctype does not need. */
export function recordTabBuiltins(): TabItem[] {
  return [
    { name: "activity", label: __("Activity"), icon: "lucide-activity" },
    { name: "emails", label: __("Emails"), icon: "lucide-mail" },
    { name: "files", label: __("Files"), icon: "lucide-paperclip" },
    { name: DETAILS_TAB, label: __("Details"), icon: "lucide-table-properties" },
  ];
}

/** Which record tab shows, and the `?tab=` that keeps it across a reload. */
export class RecordTabsHost {
  // The reader's tab, set at once by a move: the router settles a tick later, and the strip must not paint the old tab.
  private readonly wanted: Ref<string>;
  private focusClaim = "";

  constructor(
    private readonly route: RouteLocationNormalizedLoaded,
    private readonly router: Router,
    private readonly tabs: () => Surface<TabItem> | undefined,
  ) {
    this.wanted = ref(queryTab(route.query.tab));
    watch(
      () => route.query.tab,
      (tab) => (this.wanted.value = queryTab(tab)),
    );
  }

  /** `page.tabs.active`, read over the replay in flight so the first handler sees the tab the strip will paint. */
  active(): string {
    return this.pick(this.tabs()?.visibleInReplay() ?? []);
  }

  /** The tab the strip paints, from committed state alone. */
  shown(): string {
    return this.pick(this.tabs()?.visible() ?? []);
  }

  /** A `replace`: the open tab is view state, not a step in the reader's history. An arrow, so a template can pass it bare. */
  activate = (name: string) => {
    this.focusClaim = "";
    this.wanted.value = name;
    const to = { query: { ...this.route.query, tab: name }, hash: this.route.hash };
    return this.router.replace(to).catch((error) => console.error(error));
  };

  /** True once after `page.fields.focus` moved the reader to this tab, since that path places focus itself. */
  claimsFocus = (name: string) => {
    const claimed = this.focusClaim === name;
    this.focusClaim = "";
    return claimed;
  };

  /** Holds the painted tab when the address names none on the strip, so a later reorder never moves the reader. */
  remember(shown: string) {
    if (shown && !this.onStrip(this.wanted.value)) this.wanted.value = shown;
  }

  /** A new page follows the address alone. */
  reset() {
    this.wanted.value = queryTab(this.route.query.tab);
  }

  /** The form strip's tab while the reader is on Details, else `""`: the reader is not in the form. */
  formTab(identity: string) {
    return this.active() === DETAILS_TAB ? identity : "";
  }

  /** `page.fields.focus` lands on the form, so Details comes forward first; false when a script hid it. */
  async showDetails(fieldname: string): Promise<boolean> {
    if (this.shown() === DETAILS_TAB) return true;
    if (!this.tabs()?.visible().some((tab) => tab.name === DETAILS_TAB)) {
      warn(`page.fields.focus("${fieldname}") — the Details tab is hidden, so the reader was not moved.`);
      return false;
    }
    const moved = this.activate(DETAILS_TAB);
    this.focusClaim = DETAILS_TAB;
    await moved;
    return true;
  }

  /** A script hid the tab the reader was on, so the strip moved them, or has nothing left to show. */
  warnIfHidden(previous: string, next: string) {
    if (!this.onStrip(previous) || this.tabs()?.visible().some((tab) => tab.name === previous)) return;
    const outcome = next ? "they moved to the first visible tab" : "no tab is left to show";
    warn(`page.tabs.hide("${previous}") — the reader was on it, so ${outcome}.`);
  }

  private pick(visible: TabItem[]) {
    const wanted = this.wanted.value;
    return visible.some((tab) => tab.name === wanted) ? wanted : (visible[0]?.name ?? "");
  }

  private onStrip(name: string) {
    return !!name && !!this.tabs()?.resolve().some((entry) => entry.item.name === name);
  }
}

function warn(message: string) {
  if (import.meta.env.DEV) console.warn(`[record-page] ${message}`);
}

function queryTab(value: LocationQueryValue | LocationQueryValue[] | undefined) {
  return typeof value === "string" ? value : "";
}
