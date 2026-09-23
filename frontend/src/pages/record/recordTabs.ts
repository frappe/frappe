// The record's tab strip, host side: the four built-ins, the tab the address names, and its moves.
import { ref, watch, type Ref } from "vue";
import type { LocationQueryValue, RouteLocationNormalizedLoaded, Router } from "vue-router";
import type { RecordPageController } from "@/recordPage/createRecordPage";
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
  // Moves with `activate` at once: the router settles a tick later, and the strip must not paint the old tab first.
  private readonly wanted: Ref<string>;

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

  /** The address's tab while it is visible, else the first visible tab, else `""`. */
  active(): string {
    const tabs = this.tabs();
    if (!tabs) return "";
    if (this.wanted.value && tabs.isVisible(this.wanted.value)) return this.wanted.value;
    return tabs.showing()[0]?.name ?? "";
  }

  /** A `replace`: the open tab is view state, not a step in the reader's history. */
  activate(name: string) {
    this.wanted.value = name;
    return this.router.replace({ query: { ...this.route.query, tab: name } });
  }

  /** The form strip's tab while the reader is on Details, else `""`: the reader is not in the form. */
  formTab(identity: string) {
    return this.active() === DETAILS_TAB ? identity : "";
  }

  /** `page.fields.focus` lands on the form, so Details comes forward first when it is on the strip. */
  async showDetails() {
    if (this.active() !== DETAILS_TAB && this.tabs()?.isVisible(DETAILS_TAB))
      await this.activate(DETAILS_TAB);
  }

  /** A script hid the tab the reader was on, so the strip moved them. */
  warnIfHidden(name: string) {
    const tabs = this.tabs();
    if (!import.meta.env.DEV || !tabs?.has(name) || tabs.isVisible(name)) return;
    console.warn(
      `[record-page] page.tabs.hide("${name}") — the reader was on it, so they moved to the first visible tab.`,
    );
  }
}

/** `onTabChange` and `onFormTabChange`, each fired when its strip moves between two shown tabs. */
export function watchTabEvents(
  host: RecordTabsHost,
  controller: () => RecordPageController | null,
  shown: { tab: () => string; formTab: () => string },
) {
  watchShownTab(controller, shown.tab, (previous, next) => {
    host.warnIfHidden(previous);
    if (next) void controller()?.fireEvent("onTabChange");
  });
  watchShownTab(controller, shown.formTab, (_, next) => {
    if (next) void controller()?.fireEvent("onFormTabChange");
  });
}

/** Calls `moved` when the shown tab changes within one page: never on a page's first tab. */
export function watchShownTab(
  page: () => unknown,
  shown: () => string,
  moved: (previous: string, next: string) => void,
) {
  watch([page, shown] as const, ([owner, next], [previousOwner, previous]) => {
    if (owner === previousOwner && previous && next !== previous) moved(previous, next);
  });
}

function queryTab(value: LocationQueryValue | LocationQueryValue[] | undefined) {
  return typeof value === "string" ? value : "";
}
