// The two lists time orders, `page.activity` and `page.files`: the server's rows
// read from the host, a script's own rows kept on the surface so they outlive a reload.
import { ref } from "vue";
import { readOnly } from "./readOnly";
import { Surface } from "./surface";
import { FEED_ITEM_KEYS } from "./types";
import type {
  ActivityItem,
  ActivityRow,
  FeedItem,
  FileRow,
  PageActivity,
  PageFiles,
  VisibleTypes,
} from "./types";

export interface ActivityHost {
  rows: () => ActivityRow[];
  scrollTo: (key: string) => Promise<boolean>;
  reload: () => Promise<void>;
}

export interface FilesHost {
  rows: () => FileRow[];
  reload: () => Promise<void>;
}

/** What both lists share: a script adds and removes its own rows, and time places them. */
abstract class FeedSurface<Row extends Timed> extends Surface<FeedItem> {
  constructor(private readonly surface: "activity" | "files") {
    super({ surface, keys: FEED_ITEM_KEYS });
  }

  /** The server's rows, named as `items` hands them. */
  protected abstract serverItems(): Row[];

  get items(): ReadonlyArray<Row | FeedItem> {
    const server = this.serverItems();
    const taken = new Set(server.map((row) => row.name));
    const own = this.visible().filter((item) => !taken.has(item.name));
    const merged = [...server, ...own].sort(byTime);
    return readOnly(merged, {
      path: `page.${this.surface}.items`,
      instead: `page.${this.surface}.add(...) for a row of your own`,
    });
  }

  add(item: FeedItem | FeedItem[]) {
    const rows = (Array.isArray(item) ? item : [item]).filter((one) => this.canAdd(one));
    if (rows.length) super.add(rows);
  }

  remove(name: string) {
    if (super.has(name)) return super.remove(name);
    const why = this.isServerRow(name) ? "a server row stays" : "no such row";
    this.warn("remove", name, `${why}; nothing was removed`);
  }

  has(name: string) {
    return super.has(name) || this.isServerRow(name);
  }

  move(name: string) {
    this.warn("move", name, "time orders this list; nothing was moved");
  }

  order(names: string[]) {
    this.warn("order", names.join(", "), "time orders this list; nothing was moved");
  }

  private canAdd(item: FeedItem) {
    if (!item.component) return this.refuse(item, "a row needs a component");
    if (!item.timestamp) return this.refuse(item, "a row needs a timestamp to take its place");
    if (this.isServerRow(item.name)) return this.refuse(item, "that name is a server row's");
    return true;
  }

  private isServerRow(name: string) {
    return this.serverItems().some((row) => row.name === name);
  }

  private refuse(item: FeedItem, because: string) {
    this.warn("add", item.name, `${because}; dropped`);
    return false;
  }

  protected warn(verb: string, name: string, because: string) {
    if (!import.meta.env.DEV) return;
    console.warn(`[record-page] page.${this.surface}.${verb}("${name}") — ${because}.`);
  }
}

export class ActivitySurface extends FeedSurface<ActivityItem> implements PageActivity {
  // A replay's `types` waits for the commit, as its ops do.
  private stagedTypes: VisibleTypes | null = null;
  private shown = ref<VisibleTypes | null>(null);
  private heldScroll: string | null = null;

  constructor(private readonly host: ActivityHost) {
    super("activity");
  }

  /** Called in a replay, the move waits for `releaseScroll`, once the page on screen is this replay's. */
  scrollTo(key: string) {
    if (this.replaying) this.heldScroll = key;
    else void this.deliverScroll(key);
  }

  reload() {
    return this.host.reload();
  }

  types(list: VisibleTypes) {
    if (this.replaying) this.stagedTypes = [...list];
    else this.showTypes([...list]);
  }

  // Host side, below: not part of what a script may call.

  /** The types the Activity tab reads; `null` shows every type. */
  shownTypes(): VisibleTypes | null {
    return this.shown.value;
  }

  releaseScroll() {
    const key = this.heldScroll;
    this.heldScroll = null;
    if (key) void this.deliverScroll(key);
  }

  beginReplay() {
    this.stagedTypes = null;
    super.beginReplay();
  }

  commitReplay() {
    const outermost = this.replaying === 1;
    super.commitReplay();
    if (outermost) this.showTypes(this.stagedTypes);
  }

  protected serverItems(): ActivityItem[] {
    return this.host.rows().map(activityItem);
  }

  private async deliverScroll(key: string) {
    try {
      if (!(await this.host.scrollTo(key))) this.warn("scrollTo", key, "the list ended without it");
    } catch (error) {
      console.error(`[record-page] page.activity.scrollTo("${key}") — the host threw`, error);
    }
  }

  // Same list, same value: a new array would make the host read the feed again.
  private showTypes(list: VisibleTypes | null) {
    if (JSON.stringify(list) !== JSON.stringify(this.shown.value)) this.shown.value = list;
  }
}

export class FilesSurface extends FeedSurface<FileRow> implements PageFiles {
  constructor(private readonly host: FilesHost) {
    super("files");
  }

  reload() {
    return this.host.reload();
  }

  protected serverItems(): FileRow[] {
    return this.host.rows().map((row) => ({ ...row }));
  }
}

function activityItem(row: ActivityRow): ActivityItem {
  const item: ActivityItem = {
    name: row.key,
    type: row.type,
    timestamp: row.timestamp,
    author: row.author,
    data: row.data,
  };
  if (row.pending) item.pending = true;
  return item;
}

type Timed = { name: string; timestamp?: string; creation?: string };

// `(timestamp, name)`, as the server sorts; a row with no time yet is the newest.
function byTime(a: Timed, b: Timed) {
  const first = timeOf(a);
  const second = timeOf(b);
  if (first !== second) return first < second ? -1 : 1;
  return a.name < b.name ? -1 : a.name > b.name ? 1 : 0;
}

function timeOf(item: Timed): string {
  const at = item.timestamp ?? item.creation;
  return at ? String(at).replace("T", " ") : "\uffff";
}
