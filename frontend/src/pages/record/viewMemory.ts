// The reader's view of a record: kept in the history entry for Back and Forward, and per
// record while its complete entry stays in the shared cache. The history entry wins.
import { documentKey, onRecordLeft, readCachedDocument } from "@framework/ui/cache";
import { keepInHistory } from "@framework/ui/utils/scrollLanding";

export interface RecordView {
  /** The record strip's tab. */
  tab: string;
  /** The Details form's tab, by identity. */
  formTab: string;
  /** The Details sections, as `FormLayout` keys them. */
  sections: Record<string, boolean>;
  /** Each panel section as last shown, a script's acts included. */
  panel: Record<string, boolean>;
  /** Scroll tops: the shown tab body under `tab`, each body column under its name. */
  offsets: { tab?: number; columns: Record<string, number> };
}

interface HistoryView {
  doctype: string;
  name: string;
  view: RecordView;
}

const byRecord = new Map<string, RecordView>();

onRecordLeft((doctype, name) => byRecord.delete(documentKey(doctype, name)));

/** The history entry's view of this record, else, on a return that is not a new navigation, the record's own. */
export function recallView(doctype: string, name: string, newNavigation: boolean): RecordView | null {
  const kept = historyView();
  if (kept?.doctype === doctype && kept.name === name) return kept.view;
  return newNavigation ? null : (byRecord.get(documentKey(doctype, name)) ?? null);
}

/** Writes for the history entry the page opened on; a write after Back leaves the new entry alone. */
export function viewKeeper(doctype: string, name: string): (view: RecordView) => void {
  const entry = historyEntry();
  let written = "";
  return (view) => {
    if (readCachedDocument(doctype, name)?.complete) byRecord.set(documentKey(doctype, name), view);
    const state = JSON.stringify(view);
    if (historyEntry() !== entry || state === written) return;
    if (keepInHistory("recordView", { doctype, name, view })) written = state;
  };
}

/** Test seam: a test's router starts on the entry the last test left, view and all. */
export function resetViewMemory() {
  byRecord.clear();
  history.replaceState({ ...history.state, recordView: undefined }, "");
}

function historyView(): HistoryView | undefined {
  const kept = (history.state as { recordView?: HistoryView } | null)?.recordView;
  return kept && typeof kept === "object" ? kept : undefined;
}

/** vue-router numbers each history entry; a replace keeps the number. */
function historyEntry(): unknown {
  return (history.state as { position?: unknown } | null)?.position;
}
