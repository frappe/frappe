// The record strip's wiring on the page: the host, what the strip draws, and when each tab event fires.
import { computed, watch } from "vue";
import type { RouteLocationNormalizedLoaded, Router } from "vue-router";
import type { RecordPageController } from "@/recordPage/createRecordPage";
import { DETAILS_TAB, RecordTabsHost } from "./recordTabs";

export interface RecordTabsOptions {
  route: RouteLocationNormalizedLoaded;
  router: Router;
  controller: () => RecordPageController | null;
  /** The tab the Details form reports it is on. */
  formTab: () => string;
}

export function useRecordTabs({ route, router, controller, formTab }: RecordTabsOptions) {
  const host = new RecordTabsHost(route, router, () => controller()?.tabs);
  const entries = computed(() => controller()?.tabs.resolve() ?? []);
  // Nothing until the first replay commits, so a script's `hide` never flashes on the strip.
  const shown = computed(() => (controller()?.ready.value ? host.shown() : ""));
  const shownFormTab = computed(() => (shown.value === DETAILS_TAB ? formTab() : ""));

  watch(controller, () => host.reset(), { flush: "sync" });
  watch(shown, (tab) => host.remember(tab));
  watchShownTab(controller, () => shown.value, (previous, next) => {
    host.warnIfHidden(previous, next);
    if (next) void controller()?.fireEvent("onTabChange");
  });
  watchShownTab(controller, () => shownFormTab.value, (_, next) => {
    if (next) void controller()?.fireEvent("onFormTabChange");
  });

  // The page engine's tab members, as the page hands them to `createRecordPage`.
  const pageHost = {
    activeTab: () => host.active(),
    activateTab: (name: string) => void host.activate(name),
    activeFormTab: () => host.formTab(formTab()),
  };

  return { host, entries, shown, pageHost };
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
