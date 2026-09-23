// One document's feed for one filter: the pages read so far, the cursor, and the live wiring.
import { ref } from "vue";
import { getDocumentPart } from "../../api";
import type { Activity, VisibleTypes } from "./types";
import { compareActivities } from "./grouping";
import {
  createLiveUpdates,
  type LiveFeed,
  type Subscribe,
  type Unsubscribe,
} from "./liveUpdates";
import { docKey, trackPendingRows } from "./pendingRows";

interface ActivityPage {
  /** oldest first */
  activities: Activity[];
  /** cursor for the older page; null once the list has ended */
  next: string | null;
}

export class TimelineStore implements LiveFeed {
  readonly doc: string;
  readonly data = ref<Activity[]>([]);
  readonly loading = ref(false);
  readonly error = ref<unknown>(null);
  /** whether the newest page has ever landed */
  readonly fetched = ref(false);
  /** the newest page was read for a mount still to come, so that mount needs no catch-up */
  readonly prefetched = ref(false);
  readonly next = ref<string | null>(null);
  readonly fetchingOlder = ref(false);
  /** one refetch however many callers ask; resolves when it lands */
  readonly refresh: () => Promise<void>;
  /** components mounted on this store */
  mounted = 0;
  private readonly subscribe: Subscribe;
  private readonly untrack: () => void;
  /** keys a server read returned; a row the socket spliced in is not one */
  private readKeys = new Set<string>();
  private newestRead: Promise<void> | undefined;
  private olderRead: Promise<void> | undefined;

  constructor(
    private readonly doctype: string,
    private readonly docname: string,
    private readonly visibleTypes: VisibleTypes | undefined,
    types: string[] | undefined
  ) {
    this.doc = docKey(doctype, docname);
    this.untrack = trackPendingRows(this.doc, this.data);
    this.refresh = new RefreshQueue(
      () => this.load(),
      () => this.newestRead
    ).request;
    this.subscribe = createLiveUpdates(
      doctype,
      docname,
      this,
      types,
      this.refresh
    );
  }

  /** Subscribes one mounted component; the socket stays wired while any is mounted. */
  mount(): Unsubscribe {
    this.mounted++;
    const unsubscribe = this.subscribe();
    return () => {
      this.mounted--;
      unsubscribe();
    };
  }

  dispose() {
    this.untrack();
  }

  load(): Promise<void> {
    this.newestRead ??= this.readNewest().finally(() => {
      this.newestRead = undefined;
    });
    return this.newestRead;
  }

  loadOlder(): Promise<void> {
    if (this.olderRead) return this.olderRead;
    if (this.next.value === null) return Promise.resolve();
    this.olderRead = this.readOlder(this.next.value).finally(() => {
      this.olderRead = undefined;
    });
    return this.olderRead;
  }

  private async readNewest() {
    this.loading.value = true;
    try {
      this.takeNewest(await this.readPage());
      this.error.value = null;
      this.fetched.value = true;
    } catch (failure) {
      this.error.value = failure;
    } finally {
      this.loading.value = false;
    }
  }

  private async readOlder(before: string) {
    this.fetchingOlder.value = true;
    try {
      const page = await this.readPage(before);
      // a refresh that moved the cursor meanwhile has made this page stale
      if (this.next.value === before) this.takeOlder(page, before);
    } catch (failure) {
      this.error.value = failure;
    } finally {
      this.fetchingOlder.value = false;
    }
  }

  private takeNewest(page: ActivityPage) {
    const held = { activities: this.data.value, next: this.next.value };
    const feed = mergeNewestPage(held, page, this.readKeys);
    const read = new Set([...this.readKeys, ...keysOf(page.activities)]);
    this.readKeys = new Set(
      keysOf(feed.activities).filter((key) => read.has(key))
    );
    this.data.value = feed.activities;
    this.next.value = feed.next;
  }

  private takeOlder(page: ActivityPage, before: string) {
    const held = this.data.value;
    this.data.value = prependOlder(held, page.activities);
    keysOf(page.activities).forEach((key) => this.readKeys.add(key));
    // a page that adds nothing and hands back its own cursor would repeat forever
    const stuck =
      this.data.value.length === held.length && page.next === before;
    this.next.value = stuck ? null : page.next;
    this.error.value = null;
  }

  // filtered server-side so the cursor walks only the rows this view shows
  private async readPage(before?: string): Promise<ActivityPage> {
    const params = { types: this.visibleTypes, before };
    const response = await getDocumentPart<ActivityPage>(
      this.doctype,
      this.docname,
      "activity",
      params
    );
    return response.data;
  }
}

/** The newest page, joined to the held older rows when it reaches them, and live rows newer than it. */
function mergeNewestPage(
  held: ActivityPage,
  page: ActivityPage,
  read: Set<string>
): ActivityPage {
  const feed = reachesHeldRows(held, page, read)
    ? joinHeldRows(held, page)
    : page;
  const live = newerLiveRows(held.activities, page, read);
  return { activities: [...feed.activities, ...live], next: feed.next };
}

// Only a row a read returned proves the held pages run on unbroken to this one.
function reachesHeldRows(
  held: ActivityPage,
  page: ActivityPage,
  read: Set<string>
) {
  const oldest = page.activities[0];
  if (!oldest || page.next === null || !read.has(oldest.key)) return false;
  return held.activities.some((a) => a.key === oldest.key);
}

function joinHeldRows(held: ActivityPage, page: ActivityPage): ActivityPage {
  const oldest = page.activities[0];
  const older = held.activities.filter((a) => compareActivities(a, oldest) < 0);
  return { activities: [...older, ...page.activities], next: held.next };
}

// rows the socket spliced in after the server built the page
function newerLiveRows(
  held: Activity[],
  page: ActivityPage,
  read: Set<string>
) {
  const newest = page.activities.at(-1);
  const onPage = new Set(keysOf(page.activities));
  return held.filter(
    (a) =>
      !read.has(a.key) &&
      !onPage.has(a.key) &&
      (!newest || compareActivities(a, newest) > 0)
  );
}

function prependOlder(current: Activity[], older: Activity[]): Activity[] {
  const known = new Set(keysOf(current));
  return [...older.filter((a) => !known.has(a.key)), ...current];
}

function keysOf(activities: Activity[]): string[] {
  return activities.map((a) => a.key);
}

// one save can fire several doc_updates: wait a moment, then fetch once
const REFRESH_DEBOUNCE_MS = 300;

/** Every trigger in the window joins the same fetch, so one save costs one request. */
class RefreshQueue {
  private pending: Promise<void> | undefined;
  private changedSinceFetch = false;

  constructor(
    private readonly load: () => Promise<void>,
    private readonly running: () => Promise<void> | undefined
  ) {}

  request = (): Promise<void> => {
    if (this.pending) {
      this.changedSinceFetch = true;
      return this.pending;
    }
    this.pending = this.drain()
      .catch(() => {})
      .finally(() => {
        this.pending = undefined;
      });
    return this.pending;
  };

  // a change that landed mid-fetch is not in what came back: go again
  private async drain() {
    do {
      await this.fetchOnce();
    } while (this.changedSinceFetch);
  }

  private async fetchOnce() {
    await new Promise((done) => setTimeout(done, REFRESH_DEBOUNCE_MS));
    // a fetch already running was sent before the change, so it may miss it
    await this.running()?.catch(() => {});
    this.changedSinceFetch = false;
    await this.load();
  }
}
