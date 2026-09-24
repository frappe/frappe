import { ref } from "vue";
import type { Activity, CustomActivity, PendingActivity } from "./types";

/**
 * A row drawn before the server confirmed it. `key` is a throwaway the row renders under for
 * its whole life; `confirmedKey` is the key the server's row will carry, which is known only
 * once the create request answers.
 */
export type PendingRow = (Activity | CustomActivity) & {
  key: string;
  confirmedKey?: string;
};

// Kept per document, so every filtered view of it draws the same pending rows.
const pendingRowsByDocument = ref<Record<string, PendingRow[]>>({});

// All a retired pending row leaves behind, per document: confirmed key to the key it rendered under.
// { "HD Ticket:123": { "comment:0a1b4f9e2c": "pending:7c3e" } } draws that comment as pending:7c3e.
const adoptedKeysByDocument = ref<Record<string, Record<string, string>>>({});

const toDocumentId = (doctype: string, docname: string) =>
  `${doctype}:${docname}`;

/**
 * Draws a row in the feed before the server has confirmed it. The row carries `pending`, so
 * the timeline renders it muted.
 */
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

/**
 * True while a row of this type has not been resolved. A live row arriving in that window
 * cannot be told apart from the one being waited for, and drawing both is a visible duplicate.
 */
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

/**
 * Drops the pending rows the feed now carries, keeping the key each rendered under so the real
 * row adopts it. Vue then patches that node rather than remounting it, which would rebuild the
 * email iframe at its collapsed height and jump.
 */
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
