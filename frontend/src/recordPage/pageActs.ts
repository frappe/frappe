// The record page's acts on the dispatcher: the header items, quick actions and tab `create`
// entries that have `run`, read as drawn after the replay.
import { acts, type ActEntry, type ActScope } from "@/acts/dispatcher";
import { containerDisplay, surviving } from "./headerRenderings";
import type { ResolvedItem, Surface } from "./surface";
import type { HeaderItem, QuickAction, RecordPageApi, TabItem } from "./types";
import type { PagePermissions } from "./pagePermissions";

export interface PageActsHost {
  page: RecordPageApi;
  header: Surface<HeaderItem>;
  quickActions: Surface<QuickAction>;
  tabs: Surface<TabItem>;
  permissions: Pick<PagePermissions, "passes" | "settled">;
  hold: ActScope["hold"];
  failed: ActScope["failed"];
}

/** Registers the page's three act surfaces; the returned function takes them off again. */
export function registerPageActs(host: PageActsHost): () => void {
  return acts.register({
    surfaces: {
      header: () => headerEntries(host.header.resolve()),
      quickActions: () => host.quickActions.resolve(),
      tabs: () => createEntries(host.tabs.resolve()),
    },
    context: () => host.page,
    passes: host.permissions.passes,
    settled: host.permissions.settled,
    hold: host.hold,
    failed: host.failed,
  });
}

/** A container is no act, and a member of a hidden container is hidden with it. */
function headerEntries(resolved: ResolvedItem<HeaderItem>[]): ActEntry[] {
  const drawn = new Set(surviving(resolved).map((entry) => entry.item.name));
  return resolved
    .filter((entry) => !containerDisplay(entry.item))
    .map((entry) => ({ item: entry.item, hidden: !drawn.has(entry.item.name) }));
}

/** A tab's `create` entry is hidden with its tab. */
function createEntries(resolved: ResolvedItem<TabItem>[]): ActEntry[] {
  return resolved.flatMap(({ item, hidden }) =>
    item.create?.name ? [{ item: item.create, hidden }] : []
  );
}
