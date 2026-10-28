// What the builder runs on an app page, from the provider the desk sets at boot: its app's handler
// file, then the Client Scripts that name the page, re-run when one of those changes on the server.
import { watch, type Ref } from "vue";
import type { Registration } from "./types";

/** An app page's scripts, by its app, doctype and `pages/<name>.js` name. */
export interface AppPageScriptSource {
  sources(app: string, doctype: string, page: string): Registration[];
  /** Resolves when the page's fresh Client Script tier has registered. */
  load(doctype: string, page: string): Promise<void>;
  loaded(doctype: string, page: string): boolean;
  /** The sources a tier still loading will replace. */
  replaced(doctype: string, page: string): ReadonlySet<string>;
  /** What the tier is still loading, or null. */
  wait(doctype: string, page: string): string | null;
  /** A reactive count that moves when the page's stored scripts change on the server. */
  changes(doctype: string, page: string): number;
}

interface ReplayState {
  ready: Ref<boolean>;
  isReplaying: Ref<boolean>;
  refresh: () => Promise<void>;
  hasLeft: () => boolean;
}

let provider: AppPageScriptSource | null = null;

export function setAppPageScripts(next: AppPageScriptSource | null) {
  provider = next;
}

/** Without a provider an app page runs no scripts. */
export function appPageScripts(app: string, doctype: string, page: string) {
  const source = provider;
  if (!source) return null;
  return {
    sources: () => source.sources(app, doctype, page),
    sourcesReady: () => source.load(doctype, page),
    loaded: () => source.loaded(doctype, page),
    skippedBeforeSources: () => source.replaced(doctype, page),
    lateLabel: () => source.wait(doctype, page) ?? "the page's scripts",
    rerunOnChange: (state: ReplayState) =>
      rerunOnChange(() => source.changes(doctype, page), `[${page} page]`, state),
  };
}

/** A change before the first paint, or during a replay, waits for it to end; returns the stop. */
function rerunOnChange(changes: () => number, label: string, state: ReplayState) {
  let pending = false;
  return watch([changes, state.ready, state.isReplaying], ([count, ready, replaying], [was]) => {
    if (count !== was) pending = true;
    if (!pending || !ready || replaying || state.hasLeft()) return;
    pending = false;
    state.refresh().catch((error) => {
      if (import.meta.env.DEV) console.warn(`${label} script re-run failed`, error);
    });
  });
}
