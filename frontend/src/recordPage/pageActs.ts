// The record page's acts on the dispatcher: the header items, quick actions and tab `create`
// entries that have `run`, read as drawn after the replay.
import { acts, passesRight, type ActEntry, type ActScope } from "@/acts/dispatcher";
import { containerDisplay, hidingDenied, surviving } from "./headerRenderings";
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
      header: () =>
        headerEntries(host.header.resolve(), (item) => passesRight(host.permissions, item)),
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

/** A container is no act, and a member of a container hidden or denied is hidden with it. */
function headerEntries(
  resolved: ResolvedItem<HeaderItem>[],
  allows: (item: HeaderItem) => boolean
): ActEntry[] {
  const shown = namesOf(surviving(resolved));
  const drawn = namesOf(surviving(hidingDenied(resolved, allows)));
  // An item denied by its own right stays shown, so the dispatcher refuses it for that right.
  const hidden = (item: HeaderItem) =>
    !shown.has(item.name) || (allows(item) && !drawn.has(item.name));
  return resolved
    .filter((entry) => !containerDisplay(entry.item))
    .map((entry) => ({ item: entry.item, hidden: hidden(entry.item) }));
}

function namesOf(entries: ResolvedItem<HeaderItem>[]) {
  return new Set(entries.map((entry) => entry.item.name));
}

/** A tab's `create` entry is hidden with its tab. */
function createEntries(resolved: ResolvedItem<TabItem>[]): ActEntry[] {
  return resolved.flatMap(({ item, hidden }) =>
    item.create?.name ? [{ item: item.create, hidden }] : []
  );
}
