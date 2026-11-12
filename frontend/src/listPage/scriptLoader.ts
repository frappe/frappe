// The one loader the list page asks for a doctype's list.js files: the owning app's, then each `custom/` one.
import { shallowRef } from "vue";
import { listScriptsFor } from "@/contributions/registry";
import type { ListScript } from "@/contributions/types";
import type { Handler, Registration } from "@/pageEngine/types";

export interface ListScriptModule {
  default?: Record<string, unknown>;
}

/** A list.js, loaded: its handlers, and the default columns its `columns` key names. */
export interface LoadedListScript extends Registration {
  columns?: { fieldname: string; width?: number }[];
}

// One fetch per doctype at a time; the cache key of the list page's scripts.
const fetching = new Map<string, Promise<void>>();
// A shallowRef, so a computed that read a doctype's scripts before they landed reads them again.
// A doctype enters it once its files have loaded, so a failed fetch is tried again.
const loaded = shallowRef(new Map<string, LoadedListScript[]>());

/** Resolves when the doctype's list.js files have loaded; a failed fetch is logged and skipped. */
export function loadListScripts(doctype: string): Promise<void> {
  const inflight = fetching.get(doctype);
  if (inflight) return inflight;
  if (listScriptsLoaded(doctype)) return Promise.resolve();

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

/** True when the doctype has no list.js still to fetch. */
export function listScriptsLoaded(doctype: string): boolean {
  return loaded.value.has(doctype) || !listScriptsFor(doctype).length;
}

/** The doctype's loaded list.js files, in run order; reactive. */
export function listScriptsOf(doctype: string): LoadedListScript[] {
  return loaded.value.get(doctype) ?? [];
}

function loadedScript(doctype: string, { app }: ListScript, module: ListScriptModule): LoadedListScript[] {
  const exported = module.default;
  if (!exported) {
    console.warn(`[frappe] ignoring ${app}'s list script for ${doctype}: it has no default export`);
    return [];
  }
  const handlers: Record<string, Handler> = {};
  for (const [key, value] of Object.entries(exported))
    if (typeof value === "function") handlers[key] = value as Handler;
  const columns = Array.isArray(exported.columns) ? (exported.columns as LoadedListScript["columns"]) : undefined;
  return [{ source: app, handlers, columns }];
}
