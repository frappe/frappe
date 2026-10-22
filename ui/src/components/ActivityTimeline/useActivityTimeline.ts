import { createResource } from "frappe-ui";
import { computed, effectScope, onMounted, onUnmounted, watch } from "vue";
import { compareActivities, dropDuplicateKeys } from "./grouping";
import {
  createLiveUpdates,
  type Subscribe,
  type Unsubscribe,
} from "./liveUpdates";
import {
  applyFirstPage,
  createHistoryPagination,
  createPagedSources,
  isPagedRow,
  type FirstPageResponse,
  type PagedSources,
} from "./pagination";
import {
  pendingRowsFor,
  retirePendingRows,
  withAdoptedKeys,
} from "./pendingRows";
import type { Activity, CustomActivity, VisibleTypes } from "./types";

// One store per cache key: reopening a doc is instant, paging state survives remounts.
interface TimelineStore {
  resource: ReturnType<typeof createResource>;
  pagedSources: PagedSources;
  /** one refetch however many callers ask; resolves when it lands */
  refresh: () => Promise<void>;
  subscribe: Subscribe;
}
const stores = new Map<string, TimelineStore>();

// one save can fire several doc_updates: wait a moment, then fetch once
const REFRESH_DEBOUNCE_MS = 300;

export function useActivityTimeline(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) {
  const store = getTimelineStore(doctype, docname, visibleTypes);
  const { resource } = store;

  // the store is shared, so one socket serves every consumer of it
  let unsubscribe: Unsubscribe | undefined;
  onMounted(() => {
    unsubscribe = store.subscribe();
  });
  onUnmounted(() => {
    unsubscribe?.();
    unsubscribe = undefined;
  });

  // deduped + sorted but ungrouped; the component folds version runs at render time
  const activities = computed<Array<Activity | CustomActivity>>(() => {
    const confirmed = dropDuplicateKeys(
      (resource.data as Activity[] | undefined) ?? []
    );
    return [
      ...withAdoptedKeys(doctype, docname, confirmed),
      ...pendingRowsFor(doctype, docname),
    ].sort(compareActivities);
  });

  return {
    activities,
    loading: computed<boolean>(() => resource.loading),
    reload: () => store.refresh(),
    paginate: createHistoryPagination(
      doctype,
      docname,
      resource,
      store.pagedSources
    ),
  };
}

// filters are part of the cache identity
const timelineCacheKey = (
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
) =>
  `${doctype}:${docname}:${visibleTypes ? JSON.stringify(visibleTypes) : "*"}`;

function getTimelineStore(
  doctype: string,
  docname: string,
  visibleTypes?: VisibleTypes
): TimelineStore {
  const cacheKey = timelineCacheKey(doctype, docname, visibleTypes);
  const existing = stores.get(cacheKey);
  if (existing) return existing;

  const visibleTypeNames = visibleTypes?.flatMap((visibleType) =>
    typeof visibleType === "string" ? [visibleType] : Object.keys(visibleType)
  );
  const pagedSources = createPagedSources();

  const resource: ReturnType<typeof createResource> = createResource({
    url: "frappe.desk.form.activity.get_activity_timeline",
    // filtered server-side so pagination math stays correct
    params: { doctype, name: docname, visible_types: visibleTypes },
    cache: `activities:${cacheKey}`,
    auto: true,
    // transform sets resource.data, onSuccess sees the raw response, so the paging flags are
    // read there. On reload, re-append the older pages already loaded.
    transform: (response: { activities: Activity[] }) => {
      const firstPageKeys = new Set(response.activities.map((row) => row.key));
      const olderRows = (
        (resource.data as Activity[] | undefined) ?? []
      ).filter((row) => isPagedRow(row) && !firstPageKeys.has(row.key));
      return [...response.activities, ...olderRows];
    },
    onSuccess: (response: FirstPageResponse) =>
      applyFirstPage(pagedSources, response),
  });

  const refresh = createRefresh(resource);
  const store: TimelineStore = {
    resource,
    pagedSources,
    refresh,
    subscribe: createLiveUpdates(
      doctype,
      docname,
      resource,
      visibleTypeNames,
      refresh
    ),
  };
  stores.set(cacheKey, store);

  // The store outlives the component that created it, so this watcher cannot hang off that
  // component's scope: rows would stop retiring the moment the first consumer unmounts.
  // sync: the feed and the rows drawn from it must not disagree for a render.
  effectScope(true).run(() =>
    watch(
      // A row is confirmed by the feed carrying it and by its create request answering with
      // the key, which lands on the pending row. Either can come last, so both are watched.
      () => [resource.data, pendingRowsFor(doctype, docname)],
      () =>
        retirePendingRows(
          doctype,
          docname,
          (resource.data as Activity[]) ?? []
        ),
      { flush: "sync" }
    )
  );

  return store;
}

/** Every trigger in the window joins the same fetch, so one save costs one request. */
function createRefresh(resource: ReturnType<typeof createResource>) {
  let runningRefresh: Promise<void> | undefined;
  let changedSinceFetch = false;

  return function refresh(): Promise<void> {
    if (runningRefresh) {
      changedSinceFetch = true;
      return runningRefresh;
    }
    runningRefresh = (async () => {
      do {
        await new Promise((resolve) =>
          setTimeout(resolve, REFRESH_DEBOUNCE_MS)
        );
        // a fetch already running was sent before the change, so it may miss it
        if (resource.loading) await resource.promise?.catch(() => {});
        // the window is closed, so everything in it is covered by the fetch below
        changedSinceFetch = false;
        await resource.reload();
        // a change that landed mid-fetch is not in what came back: go again
      } while (changedSinceFetch);
    })()
      .catch(() => {})
      .finally(() => {
        runningRefresh = undefined;
      });
    return runningRefresh;
  };
}
