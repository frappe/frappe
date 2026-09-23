// Rows shown before the server confirms them, per document, and the keys they drew under.
import { effectScope, ref, watch, type Ref } from "vue";
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

const trackedFeeds: Array<{ doc: string; data: Ref<Activity[]> }> = [];

const PENDING_KEY = "pending:";
const isUnresolved = (row: PendingRow) => row.key.startsWith(PENDING_KEY);

export const docKey = (doctype: string, docname: string) =>
  `${doctype}:${docname}`;

/**
 * Shows a row in the feed before the server has confirmed it. The row carries
 * `pending`, so the timeline renders it muted.
 */
export function addPendingActivity(
  doctype: string,
  docname: string,
  activity: Omit<Activity | CustomActivity, "key"> & { key?: string }
): PendingActivity {
  const doc = docKey(doctype, docname);
  const renderKey = activity.key ?? `${PENDING_KEY}${crypto.randomUUID()}`;
  const row = { ...activity, key: renderKey, renderKey, pending: true };
  setPendingRows(doc, (rows) => [...rows, row as PendingRow]);
  return {
    resolve: (key, timestamp) => resolvePendingRow(doc, renderKey, key, timestamp),
    drop: () =>
      setPendingRows(doc, (rows) => rows.filter((r) => r.renderKey !== renderKey)),
  };
}

/** Retires a document's pending rows as the server echoes them into `data`. */
export function trackPendingRows(doc: string, data: Ref<Activity[]>) {
  trackedFeeds.push({ doc, data });
  // Detached: the store outlives the component that built it. Sync: the feed and the
  // rows drawn from it must not disagree for a render.
  effectScope(true).run(() =>
    watch(data, (feed) => retirePendingRows(doc, feed), { flush: "sync" })
  );
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
  setPendingRows(doc, (rows) =>
    rows.map((r) => (r.renderKey === renderKey ? { ...r, ...confirmed } : r))
  );
  // a resolved row may already be in a feed: the socket can beat the request's answer
  for (const feed of trackedFeeds)
    if (feed.doc === doc) retirePendingRows(doc, feed.data.value);
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

/** Drops pending rows the server echoed back, keeping the key each rendered under. */
function retirePendingRows(doc: string, feed: Activity[]) {
  const rows = pendingActivities.value[doc];
  if (!rows?.length) return;
  const echoed = echoedKeys(rows, feed);
  if (!echoed.size) return;

  const adopted = Object.fromEntries(
    [...echoed].map(([row, key]) => [key, row.renderKey])
  );
  pendingActivities.value = {
    ...pendingActivities.value,
    [doc]: rows.filter((row) => !echoed.has(row)),
  };
  adoptedKeys.value = {
    ...adoptedKeys.value,
    [doc]: { ...adoptedKeys.value[doc], ...adopted },
  };
}

/** Each pending row the feed holds, with the server key it holds it under. */
function echoedKeys(rows: PendingRow[], feed: Activity[]) {
  const serverKeys = new Set(feed.map((a) => a.key));
  const keyByText = rows.some(isUnresolved) ? keysByText(feed) : undefined;
  const echoed = new Map<PendingRow, string>();
  for (const row of rows) {
    const real = isUnresolved(row) ? keyByText?.get(rowText(row) ?? "") : row.key;
    if (real && serverKeys.has(real)) echoed.set(row, real);
  }
  return echoed;
}

// A row with no key yet is matched on its text. An identical older row can swallow it.
function keysByText(feed: Activity[]): Map<string, string> {
  const keys = new Map<string, string>();
  for (const a of feed) {
    const text = rowText(a);
    if (text) keys.set(text, a.key);
  }
  return keys;
}

/** What a row says, for matching one the server echoed back under a key we don't know yet. */
function rowText(activity: Activity | CustomActivity) {
  const content = (activity.data as { content?: unknown } | null)?.content;
  if (typeof content !== "string") return undefined;
  const text = stripHtml(content).replace(/\s+/g, " ").trim();
  return text && JSON.stringify([activity.type, text]);
}
