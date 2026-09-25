// The two lists time orders, `page.activity` and `page.files`: the server's rows
// read from the host, a script's own rows kept on the surface so they outlive a reload.
import { ref } from "vue";
import { dayjs } from "frappe-ui";
import { compareActivities } from "@framework/ui/ActivityTimeline";
import { currentSession } from "@framework/ui/composables/useSession";
import { runningSource } from "./context";
import { readOnly } from "./readOnly";
import { dropReason, type Release } from "./staging";
import { BUILTIN, Surface } from "./surface";
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
  scrollTo: (key: string) => Promise<boolean | null>;
  reload: () => Promise<void>;
  /** The page's rule for whether an act waits for a commit. */
  isStaging: () => boolean;
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
    const rows = (Array.isArray(item) ? item : [item]).flatMap(
      (one) => this.checked("add", one.name, one, true) ?? []
    );
    if (rows.length) super.add(rows);
  }

  update(name: string, patch: Partial<FeedItem>) {
    const checked = this.checked("update", name, patch, false);
    if (checked) super.update(name, checked);
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

  // What `add` and `update` both hold a row to; an `update` checks only the keys it sets.
  private checked<Fields extends Partial<FeedItem>>(
    verb: string,
    name: string,
    fields: Fields,
    whole: boolean
  ) {
    const clears = (key: keyof FeedItem) => (whole || key in fields) && !fields[key];
    if (clears("component")) return this.refuse(verb, name, "a row needs a component");
    if (clears("timestamp")) return this.refuse(verb, name, "a row needs a timestamp to take its place");
    if (this.isServerRow(name)) return this.refuse(verb, name, "that name is a server row's");
    return this.inServerTime(verb, name, fields);
  }

  // Rows sort by their timestamp's text, so a script's row is written as the server writes one.
  private inServerTime<Fields extends Partial<FeedItem>>(verb: string, name: string, fields: Fields) {
    const [, date, time, zone] = SCRIPT_TIME.exec(String(fields.timestamp)) ?? [];
    if (!date) return fields;
    const timestamp = zone ? onSiteClock(date, time, zone) : `${date} ${time}`;
    if (timestamp) return { ...fields, timestamp };
    // In production too: a row placed hours off is worse than a missing one.
    console.warn(
      `[record-page] page.${this.surface}.${verb}("${name}") — "${fields.timestamp}" could not be read on the site's clock; pass site-local time, as "2026-09-23 10:15:00"; dropped.`
    );
  }

  protected isUndrawn(name: string) {
    return super.has(name) && !this.isDrawn(name);
  }

  private isServerRow(name: string) {
    return this.serverItems().some((row) => row.name === name);
  }

  private refuse(verb: string, name: string, because: string): undefined {
    this.warn(verb, name, `${because}; dropped`);
  }

  protected warn(verb: string, name: string, because: string) {
    if (!import.meta.env.DEV) return;
    console.warn(`[record-page] page.${this.surface}.${verb}("${name}") — ${because}.`);
  }
}

export class ActivitySurface extends FeedSurface<ActivityItem> implements PageActivity {
  // `types` stages with its source, as an op does; the first entry is what the buffer starts from.
  private stagedTypes: { source: string; list: VisibleTypes | null }[] = [];
  private shown = ref<VisibleTypes | null>(null);
  private heldScroll: string | null = null;

  constructor(private readonly host: ActivityHost) {
    super("activity");
  }

  /** Called in a replay or a hold, the move waits for `releaseScroll`, once the page on screen is its own. */
  scrollTo(key: string) {
    if (this.host.isStaging()) this.heldScroll = key;
    else void this.deliverScroll(key);
  }

  reload() {
    return this.host.reload();
  }

  types(list: VisibleTypes) {
    if (this.staging) this.stagedTypes.push({ source: runningSource(), list: [...list] });
    else this.showTypes([...list]);
  }

  // Host side, below: not part of what a script may call.

  /** The types the Activity tab reads; `null` shows every type. */
  shownTypes(): VisibleTypes | null {
    return this.shown.value;
  }

  /** Takes the held move out of the way; the returned function puts it back. */
  setAsideScroll() {
    const key = this.heldScroll;
    this.heldScroll = null;
    return () => void (this.heldScroll = key);
  }

  /** Delivers the held move, or drops it with a warning as `release` says. */
  releaseScroll(release: Release = "all") {
    const key = this.heldScroll;
    this.heldScroll = null;
    if (!key) return;
    const dropped = dropReason(release, () => !this.isUndrawn(key));
    if (dropped) this.warn("scrollTo", key, `${dropped}; the reader was not moved`);
    else void this.deliverScroll(key);
  }

  beginReplay() {
    this.stagedTypes = [{ source: BUILTIN, list: null }];
    super.beginReplay();
  }

  // A hold starts from the types on screen, as its ops start from the drawn list.
  beginHold() {
    if (!this.staging) this.stagedTypes = [{ source: BUILTIN, list: this.shown.value }];
    super.beginHold();
  }

  commit() {
    const last = super.commit();
    if (last) this.showTypes(this.typesWithout());
    return last;
  }

  publishStaged(except: ReadonlySet<string>) {
    super.publishStaged(except);
    if (this.staging) this.showTypes(this.typesWithout(except));
  }

  protected serverItems(): ActivityItem[] {
    return this.host.rows().map(activityItem);
  }

  private async deliverScroll(key: string) {
    try {
      if ((await this.host.scrollTo(key)) === false) this.warn("scrollTo", key, "the list ended without it");
    } catch (error) {
      console.error(`[record-page] page.activity.scrollTo("${key}") — the host threw`, error);
    }
  }

  private typesWithout(except?: ReadonlySet<string>) {
    return this.stagedTypes.findLast((write) => !except?.has(write.source))?.list ?? null;
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

// `2026-09-23T10:15:00.5+05:30`: the date, the time, and a zone the server never writes.
const SCRIPT_TIME = /^(\d{4}-\d{2}-\d{2})[T ]([\d:.]+)(Z|[+-]\d{2}(?::?\d{2})?)?$/;

// The same instant in the site's time zone, which the session carries; undefined without one.
function onSiteClock(date: string, time: string, zone: string): string | undefined {
  const siteZone = currentSession()?.timezone;
  const [whole, fraction] = time.split(".");
  const instant = new Date(`${date}T${whole}${isoOffset(zone)}`);
  if (!siteZone || Number.isNaN(instant.getTime())) return undefined;
  const clock = dayjs(instant).tz(siteZone).format("YYYY-MM-DD HH:mm:ss");
  return fraction ? `${clock}.${fraction}` : clock;
}

// `Date` reads `Z` and `+05:30`, not `+0530` or `+05`.
function isoOffset(zone: string) {
  if (zone === "Z") return zone;
  const digits = zone.slice(1).replace(":", "");
  return `${zone[0]}${digits.slice(0, 2)}:${digits.slice(2) || "00"}`;
}

// As the timeline draws its rows; a file row's time is its `creation`.
function byTime(a: Timed, b: Timed) {
  return compareActivities(timed(a), timed(b));
}

function timed(item: Timed) {
  return { timestamp: item.timestamp ?? item.creation, key: item.name };
}
