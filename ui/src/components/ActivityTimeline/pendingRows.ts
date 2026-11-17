import { ref } from "vue";
import type { Activity, CustomActivity, PendingActivity } from "./types";

/** A row drawn before the server confirms it. `key` is a throwaway it renders under for life;
 * `confirmedKey` is the server's key, known once the create request answers. */
export type PendingRow = (Activity | CustomActivity) & {
  key: string;
  confirmedKey?: string;
};

// per document, so every filtered view draws the same pending rows
const pendingRowsByDocument = ref<Record<string, PendingRow[]>>({});

// confirmed key to the pending key it keeps rendering under, per document
// e.g. { "HD Ticket:123": { "comment:0a1b4f9e2c": "pending:7c3e" } }
const adoptedKeysByDocument = ref<Record<string, Record<string, string>>>({});

const toDocumentId = (doctype: string, docname: string) =>
  `${doctype}:${docname}`;

/** Draws a muted row in the feed before the server confirms it. */
export function addPendingActivity(
  doctype: string,
  docname: string,
  activity: Omit<Activity | CustomActivity, "key"> & { key?: string }
): PendingActivity {
  const documentId = toDocumentId(doctype, docname);
  const pendingKey = activity.key ?? `pending:${crypto.randomUUID()}`;

  const updateRows = (update: (rows: PendingRow[]) => PendingRow[]) => {
    pendingRowsByDocument.value = {
      ...pendingRowsByDocument.value,
      [documentId]: update(pendingRowsByDocument.value[documentId] ?? []),
    };
  };

  updateRows((rows) => [
    ...rows,
    { ...activity, key: pendingKey, pending: true } as PendingRow,
  ]);

  return {
    resolve: (confirmedKey: string) =>
      updateRows((rows) =>
        rows.map((row) =>
          row.key === pendingKey ? { ...row, confirmedKey } : row
        )
      ),
    drop: () =>
      updateRows((rows) => rows.filter((row) => row.key !== pendingKey)),
  };
}

/** The document's pending rows, oldest first. */
export function pendingRowsFor(doctype: string, docname: string): PendingRow[] {
  return pendingRowsByDocument.value[toDocumentId(doctype, docname)] ?? [];
}

/** True while a row of this type has no confirmed key yet. A live row arriving then
 * can't be told apart from it, and drawing both would duplicate it. */
export function hasUnresolvedRowOfType(
  doctype: string,
  docname: string,
  type: string
): boolean {
  return pendingRowsFor(doctype, docname).some(
    (row) => row.type === type && !row.confirmedKey
  );
}

/** The feed as it should draw: a confirmed row keeps the key its pending row rendered under. */
export function withAdoptedKeys(
  doctype: string,
  docname: string,
  feed: Activity[]
): Activity[] {
  const adoptedKeys =
    adoptedKeysByDocument.value[toDocumentId(doctype, docname)];
  if (!adoptedKeys) return feed;
  return feed.map((activity) => {
    const pendingKey = adoptedKeys[activity.key];
    return pendingKey ? { ...activity, key: pendingKey } : activity;
  });
}

/** Drops pending rows the feed now carries. The real row adopts the pending key, so Vue patches
 * the node instead of remounting it (a remounted email iframe collapses and jumps). */
export function retirePendingRows(
  doctype: string,
  docname: string,
  feed: Activity[]
) {
  const documentId = toDocumentId(doctype, docname);
  const rows = pendingRowsByDocument.value[documentId];
  if (!rows?.length) return;

  const keysInFeed = new Set(feed.map((activity) => activity.key));
  const newlyAdopted: Record<string, string> = {};
  const stillPending = rows.filter((row) => {
    if (!row.confirmedKey || !keysInFeed.has(row.confirmedKey)) return true;
    newlyAdopted[row.confirmedKey] = row.key;
    return false;
  });
  if (stillPending.length === rows.length) return;

  pendingRowsByDocument.value = {
    ...pendingRowsByDocument.value,
    [documentId]: stillPending,
  };
  adoptedKeysByDocument.value = {
    ...adoptedKeysByDocument.value,
    [documentId]: {
      ...adoptedKeysByDocument.value[documentId],
      ...newlyAdopted,
    },
  };
}
