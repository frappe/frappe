// The reader's view of a record: kept in the history entry for Back and Forward, and per
// record while its complete entry stays in the shared cache. The history entry wins.
import { documentKey, onRecordLeft, readCachedDocument } from "@framework/ui/cache";

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

export interface ViewKeeper {
  /** Every change, a scroll frame included: the record's own copy only. */
  keep(view: RecordView): void;
  /** A change the reader made, or a leave: the history entry too. */
  mark(view: RecordView): void;
}

interface HistoryView {
  doctype: string;
  name: string;
  view: RecordView;
}

/** The history entry it was written from, so it stands for that entry when newer than the entry's own. */
interface OwnView {
  entry: unknown;
  view: RecordView;
}

const byRecord = new Map<string, OwnView>();

onRecordLeft((doctype, name) => byRecord.delete(documentKey(doctype, name)));

/** The history entry's view of this record, else, on a return that is not a new navigation, the record's own. */
export function recallView(doctype: string, name: string, newNavigation: boolean): RecordView | null {
  const own = byRecord.get(documentKey(doctype, name));
  const kept = historyView();
  if (kept?.doctype === doctype && kept.name === name)
    return own?.entry === historyEntry() ? own.view : kept.view;
  return newNavigation ? null : (own?.view ?? null);
}

/** Writes for the history entry the page opened on; a write after Back leaves the new entry alone. */
export function viewKeeper(doctype: string, name: string): ViewKeeper {
  const entry = historyEntry();
  let written = "";
  const keep = (view: RecordView) => {
    if (readCachedDocument(doctype, name)?.complete)
      byRecord.set(documentKey(doctype, name), { entry, view });
  };
  return {
    keep,
    mark(view) {
      keep(view);
      const state = JSON.stringify(view);
      if (historyEntry() !== entry || state === written) return;
      written = state;
      writeHistory({ doctype, name, view });
    },
  };
}

/** Test seam: a test's router starts on the entry the last test left, view and all. */
export function resetViewMemory() {
  byRecord.clear();
  history.replaceState({ ...history.state, recordView: undefined }, "");
}

// A browser refuses writes past a rate; the record's own copy then still holds the view.
function writeHistory(recordView: HistoryView) {
  try {
    history.replaceState({ ...history.state, recordView }, "");
  } catch (error) {
    console.warn("[record-page] the view was not kept in the history entry", error);
  }
}

function historyView(): HistoryView | undefined {
  const kept = (history.state as { recordView?: HistoryView } | null)?.recordView;
  return kept && typeof kept === "object" ? kept : undefined;
}

/** vue-router numbers each history entry; a replace keeps the number. */
function historyEntry(): unknown {
  return (history.state as { position?: unknown } | null)?.position;
}
