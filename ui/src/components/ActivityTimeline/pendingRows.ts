// Rows shown before the server confirms them, per document, and the keys they drew under.
import { effectScope, ref, watch, type EffectScope, type Ref } from "vue";
import type { Activity, CustomActivity, PendingActivity } from "./types";
import { compareActivities } from "./grouping";
import { stripHtml } from "./utils";

// `renderKey` is the key a row was first drawn under; the server row adopts it,
// so Vue patches the node instead of remounting it.
type PendingRow = (Activity | CustomActivity) & {
  key: string;
  renderKey: string;
};
const pendingActivities = ref<Record<string, PendingRow[]>>({});

// All a retired pending row leaves behind, by server key, per document. The picture fills
// in for a confirmed row by the same author that has none: a live row only knows the feed's.
type AdoptedRow = { renderKey: string; email?: string; image?: string };
const adoptedRows = ref<Record<string, Record<string, AdoptedRow>>>({});

type TrackedFeed = { doc: string; data: Ref<Activity[]> };
const trackedFeeds = new Set<TrackedFeed>();

// The newest non-email row the feeds held when an unresolved row was added, by render
// key; its echo can only sort after it. An email's time is the sender's clock.
type Position = Pick<Activity, "timestamp" | "key">;
const newestHeldAtAdd = new Map<string, Position>();

const PENDING_KEY = "pending:";
const isUnresolved = (row: PendingRow) => row.key.startsWith(PENDING_KEY);

export const docKey = (doctype: string, docname: string) =>
  `${doctype}:${docname}`;

/** Shows a row, marked `pending` so it draws muted, before the server confirms it. */
export function addPendingActivity(
  doctype: string,
  docname: string,
  activity: Omit<Activity | CustomActivity, "key"> & { key?: string }
): PendingActivity {
  const doc = docKey(doctype, docname);
  const renderKey = activity.key ?? `${PENDING_KEY}${crypto.randomUUID()}`;
  const newest = renderKey.startsWith(PENDING_KEY) && newestHeld(doc);
  if (newest) newestHeldAtAdd.set(renderKey, newest);
  const row = { ...activity, key: renderKey, renderKey, pending: true };
  setPendingRows(doc, (rows) => [...rows, row as PendingRow]);
  return {
    resolve: (key, timestamp) => resolvePendingRow(doc, renderKey, key, timestamp),
    drop: () => dropPendingRow(doc, renderKey),
  };
}

/** Retires pending rows as the server echoes them into `data`; returns the function that stops it. */
export function trackPendingRows(doc: string, data: Ref<Activity[]>): () => void {
  const feed = { doc, data };
  trackedFeeds.add(feed);
  // Detached: the store outlives the component that built it. Sync: the feed and the
  // rows drawn from it must not disagree for a render.
  const scope = effectScope(true);
  scope.run(() =>
    watch(data, (rows) => retirePendingRows(doc, rows), { flush: "sync" })
  );
  return () => untrackFeed(feed, scope);
}

/** A feed's confirmed rows under the keys they first drew with, and the rows still waiting. */
export function withPendingRows(
  doc: string,
  confirmed: Activity[],
  types: string[] | undefined
): Array<Activity | CustomActivity> {
  const adopted = adoptedRows.value[doc] ?? {};
  const drawn = confirmed.map((a) =>
    adopted[a.key] ? drawAdopted(a, adopted[a.key]) : a
  );
  const waiting = (pendingActivities.value[doc] ?? []).filter(
    (row) => !types || types.includes(row.type)
  );
  return [...drawn, ...waiting];
}

function drawAdopted(row: Activity, adopted: AdoptedRow): Activity {
  const drawn = { ...row, renderKey: adopted.renderKey };
  if (adopted.image && !row.author?.image && sameAuthor(row, adopted))
    drawn.author = { ...row.author, image: adopted.image };
  return drawn;
}

function sameAuthor(row: Activity, adopted: AdoptedRow) {
  const email = row.author?.email?.toLowerCase();
  return !!email && email === adopted.email?.toLowerCase();
}

function resolvePendingRow(
  doc: string,
  renderKey: string,
  key: string,
  timestamp?: string
) {
  const confirmed = { key, pending: false, ...(timestamp ? { timestamp } : {}) };
  newestHeldAtAdd.delete(renderKey);
  setPendingRows(doc, (rows) =>
    rows.map((r) => (r.renderKey === renderKey ? { ...r, ...confirmed } : r))
  );
  // a resolved row may already be in a feed: the socket can beat the request's answer
  for (const feed of trackedFeeds)
    if (feed.doc === doc) retirePendingRows(doc, feed.data.value);
}

function dropPendingRow(doc: string, renderKey: string) {
  newestHeldAtAdd.delete(renderKey);
  setPendingRows(doc, (rows) => rows.filter((r) => r.renderKey !== renderKey));
}

function setPendingRows(
  doc: string,
  change: (rows: PendingRow[]) => PendingRow[]
) {
  pendingActivities.value = {
    ...pendingActivities.value,
    [doc]: change(pendingActivities.value[doc] ?? []),
  };
}

function untrackFeed(feed: TrackedFeed, scope: EffectScope) {
  scope.stop();
  trackedFeeds.delete(feed);
  if ([...trackedFeeds].some((f) => f.doc === feed.doc)) return;
  const adopted = { ...adoptedRows.value };
  delete adopted[feed.doc];
  adoptedRows.value = adopted;
}

function newestHeld(doc: string): Position | undefined {
  let newest: Position | undefined;
  for (const feed of trackedFeeds)
    if (feed.doc === doc)
      for (const a of feed.data.value)
        if (a.type !== "email" && (!newest || compareActivities(a, newest) > 0))
          newest = a;
  return newest;
}

/** Drops pending rows the server echoed back, keeping the key each rendered under. */
function retirePendingRows(doc: string, feed: Activity[]) {
  const rows = pendingActivities.value[doc];
  const echoed = rows?.length ? echoedKeys(rows, feed) : undefined;
  if (echoed?.size) adoptEchoedRows(doc, echoed);
}

function adoptEchoedRows(doc: string, echoed: Map<PendingRow, string>) {
  setPendingRows(doc, (rows) => rows.filter((row) => !echoed.has(row)));
  const adopted: Record<string, AdoptedRow> = {};
  for (const [row, key] of echoed) {
    const { email, image } = row.author ?? {};
    adopted[key] = { renderKey: row.renderKey, email, image };
    newestHeldAtAdd.delete(row.renderKey);
  }
  adoptedRows.value = {
    ...adoptedRows.value,
    [doc]: { ...adoptedRows.value[doc], ...adopted },
  };
}

/** Each pending row the feed holds, with the server key it holds it under. */
function echoedKeys(rows: PendingRow[], feed: Activity[]) {
  const serverKeys = new Set(feed.map((a) => a.key));
  const texts = rows.some(isUnresolved) ? feedTexts(feed) : [];
  const echoed = new Map<PendingRow, string>();
  for (const row of rows) {
    const real = isUnresolved(row) ? matchByText(row, texts, echoed) : row.key;
    if (real && serverKeys.has(real)) echoed.set(row, real);
  }
  return echoed;
}

// A row with no key yet is matched on its text, among unclaimed rows that sort after
// the newest row held when it was added.
function matchByText(
  row: PendingRow,
  texts: Array<[Activity, string]>,
  claimed: Map<PendingRow, string>
): string | undefined {
  const text = rowText(row);
  if (!text) return undefined;
  const mark = newestHeldAtAdd.get(row.renderKey);
  const taken = new Set(claimed.values());
  return texts.find(
    ([a, t]) =>
      t === text &&
      !taken.has(a.key) &&
      (!mark || compareActivities(a, mark) > 0)
  )?.[0].key;
}

function feedTexts(feed: Activity[]): Array<[Activity, string]> {
  return feed.flatMap((a) => {
    const text = rowText(a);
    return text ? [[a, text] as [Activity, string]] : [];
  });
}

/** What a row says, for matching one the server echoed back under a key we don't know yet. */
function rowText(activity: Activity | CustomActivity) {
  const content = (activity.data as { content?: unknown } | null)?.content;
  if (typeof content !== "string") return undefined;
  const text = stripHtml(content).replace(/\s+/g, " ").trim();
  return text && JSON.stringify([activity.type, text]);
}
