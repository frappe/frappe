// The one loader the list page asks for a doctype's list.js files: the owning app's, then each `custom/` one.
import { shallowRef } from "vue";
import { listScriptsFor } from "./listScriptFiles";
import type { ListScript } from "@/contributions/types";
import { clientScriptsLoaded, clientScriptsStale, loadClientScripts } from "@/recordPage/clientScripts";
import { LIST_PAGE_TIER } from "@/recordPage/clientScriptTypes";
import { loadedListScript, storedListScripts, type LoadedListScript } from "@/pageEngine/storedListScripts";

export type { LoadedListScript };

export interface ListScriptModule {
  default?: Record<string, unknown>;
}

// One fetch per doctype at a time; the cache key of the list page's scripts.
const fetching = new Map<string, Promise<void>>();
// A shallowRef, so a computed that read a doctype's scripts before they landed reads them again.
// A doctype enters it once its files have loaded, so a failed fetch is tried again.
const loaded = shallowRef(new Map<string, LoadedListScript[]>());

/**
 * Resolves when the doctype's list.js files and its fresh List Page Client Scripts have loaded.
 * `scripted` is whether boot lists the doctype as holding a Client Script; false skips the fetch.
 */
export function loadListScripts(doctype: string, scripted = true): Promise<void> {
  // The tier is fetched beside the files and registers after them; a failed fetch skips only the files.
  const files = loadListFiles(doctype);
  return Promise.all([loadClientScripts(doctype, LIST_PAGE_TIER, files, !scripted), files]).then(() => {});
}

function loadListFiles(doctype: string): Promise<void> {
  const inflight = fetching.get(doctype);
  if (inflight) return inflight;
  if (listFilesLoaded(doctype)) return Promise.resolve();

  const scripts = listScriptsFor(doctype);
  const loading = Promise.all(scripts.map((script) => script.load()))
    .then((modules) => {
      const next = new Map(loaded.value);
      next.set(doctype, scripts.flatMap((script, index) => loadedScript(doctype, script, modules[index])));
      loaded.value = next;
    })
    .catch((error) => console.error(`[frappe] the list scripts of ${doctype} failed to load, skipped`, error));
  fetching.set(doctype, loading);
  const done = () => fetching.delete(doctype);
  loading.then(done, done);
  return loading;
}

/** True when the doctype has no list.js still to fetch and its Client Scripts have registered and are fresh. */
export function listScriptsLoaded(doctype: string): boolean {
  return (
    listFilesLoaded(doctype) &&
    clientScriptsLoaded(doctype, LIST_PAGE_TIER) &&
    !clientScriptsStale(doctype, LIST_PAGE_TIER)
  );
}

/** The doctype's list scripts in run order: its list.js files, then its Client Scripts; reactive. */
export function listScriptsOf(doctype: string): LoadedListScript[] {
  return [...(loaded.value.get(doctype) ?? []), ...storedListScripts(doctype)];
}

function listFilesLoaded(doctype: string) {
  return loaded.value.has(doctype) || !listScriptsFor(doctype).length;
}

function loadedScript(doctype: string, { app }: ListScript, module: ListScriptModule): LoadedListScript[] {
  if (!module.default) {
    console.warn(`[frappe] ignoring ${app}'s list script for ${doctype}: it has no default export`);
    return [];
  }
  return [loadedListScript(app, module.default)];
}
