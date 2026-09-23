// Rows shown before the server confirms them, per document, and the keys they drew under.
import { effectScope, ref, watch, type EffectScope, type Ref } from "vue";
import type { Activity, CustomActivity, PendingActivity } from "./types";
import { stripHtml } from "./utils";

// `renderKey` is the key a row was first drawn under; the server row adopts it,
// so Vue patches the node instead of remounting it.
type PendingRow = (Activity | CustomActivity) & {
  key: string;
  renderKey: string;
};
const pendingActivities = ref<Record<string, PendingRow[]>>({});

// All a retired pending row leaves behind: server key to render key, per document.
const adoptedKeys = ref<Record<string, Record<string, string>>>({});

type TrackedFeed = { doc: string; data: Ref<Activity[]> };
const trackedFeeds = new Set<TrackedFeed>();

// Keys the feeds held when an unresolved row was added, by render key; none can be its echo.
const keysHeldAtAdd = new Map<string, Set<string>>();

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
  if (renderKey.startsWith(PENDING_KEY)) keysHeldAtAdd.set(renderKey, heldKeys(doc));
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
  const adopted = adoptedKeys.value[doc] ?? {};
  const drawn = confirmed.map((a) =>
    adopted[a.key] ? { ...a, renderKey: adopted[a.key] } : a
  );
  const waiting = (pendingActivities.value[doc] ?? []).filter(
    (row) => !types || types.includes(row.type)
  );
  return [...drawn, ...waiting];
}

function resolvePendingRow(
  doc: string,
  renderKey: string,
  key: string,
  timestamp?: string
) {
  const confirmed = { key, pending: false, ...(timestamp ? { timestamp } : {}) };
  keysHeldAtAdd.delete(renderKey);
  setPendingRows(doc, (rows) =>
    rows.map((r) => (r.renderKey === renderKey ? { ...r, ...confirmed } : r))
  );
  // a resolved row may already be in a feed: the socket can beat the request's answer
  for (const feed of trackedFeeds)
    if (feed.doc === doc) retirePendingRows(doc, feed.data.value);
}

function dropPendingRow(doc: string, renderKey: string) {
  keysHeldAtAdd.delete(renderKey);
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
  const adopted = { ...adoptedKeys.value };
  delete adopted[feed.doc];
  adoptedKeys.value = adopted;
}

function heldKeys(doc: string): Set<string> {
  const held = new Set<string>();
  for (const feed of trackedFeeds)
    if (feed.doc === doc) feed.data.value.forEach((a) => held.add(a.key));
  return held;
}

/** Drops pending rows the server echoed back, keeping the key each rendered under. */
function retirePendingRows(doc: string, feed: Activity[]) {
  const rows = pendingActivities.value[doc];
  const echoed = rows?.length ? echoedKeys(rows, feed) : undefined;
  if (echoed?.size) adoptEchoedRows(doc, echoed);
}

function adoptEchoedRows(doc: string, echoed: Map<PendingRow, string>) {
  setPendingRows(doc, (rows) => rows.filter((row) => !echoed.has(row)));
  const adopted: Record<string, string> = {};
  for (const [row, key] of echoed) {
    adopted[key] = row.renderKey;
    keysHeldAtAdd.delete(row.renderKey);
  }
  adoptedKeys.value = {
    ...adoptedKeys.value,
    [doc]: { ...adoptedKeys.value[doc], ...adopted },
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

// A row with no key yet is matched on its text, among rows that came after it and are unclaimed.
function matchByText(
  row: PendingRow,
  texts: Array<[string, string]>,
  claimed: Map<PendingRow, string>
): string | undefined {
  const text = rowText(row);
  if (!text) return undefined;
  const before = keysHeldAtAdd.get(row.renderKey);
  const taken = new Set(claimed.values());
  return texts.find(
    ([key, t]) => t === text && !before?.has(key) && !taken.has(key)
  )?.[0];
}

function feedTexts(feed: Activity[]): Array<[string, string]> {
  return feed.flatMap((a) => {
    const text = rowText(a);
    return text ? [[a.key, text] as [string, string]] : [];
  });
}

/** What a row says, for matching one the server echoed back under a key we don't know yet. */
function rowText(activity: Activity | CustomActivity) {
  const content = (activity.data as { content?: unknown } | null)?.content;
  if (typeof content !== "string") return undefined;
  const text = stripHtml(content).replace(/\s+/g, " ").trim();
  return text && JSON.stringify([activity.type, text]);
}
