// The one loader the record page asks for a doctype's scripts: the file scripts apps ship, then its Client Scripts.
import { loadClientScripts } from "./clientScripts";
import { withRegisteringSource } from "@/pageEngine/context";
import { registerRecordPage } from "./registry";
import { reportCustomizationError } from "./reportError";
import type { AuthoredHandlers } from "./types";

const FILE_SCRIPTS_SOURCE = "file-scripts";

export interface FileScript {
  app: string;
  load: () => Promise<{ default?: AuthoredHandlers }>;
}

// In run order. A doctype leaves the map once its scripts have registered, so a failed fetch is tried again.
const fileScripts = new Map<string, FileScript[]>();
// One fetch per doctype at a time: the record page asks early and again when it needs them.
const fetching = new Map<string, Promise<void>>();

/** Adds an app's file script behind the doctype's earlier ones; the doctype's first load fetches and registers it. */
export function addFileScript(doctype: string, script: FileScript) {
  fileScripts.set(doctype, [...(fileScripts.get(doctype) ?? []), script]);
}

/** Resolves when the doctype's file scripts and its fresh Client Script tier have registered. */
export function loadRecordScripts(doctype: string): Promise<void> {
  // The tier is fetched beside the file scripts and registers after them; a failed fetch skips only them.
  const files = loadFileScripts(doctype).catch((error) => {
    console.error(`[frappe] the record scripts of ${doctype} failed to load, skipped`, error);
    reportCustomizationError(error, { source: FILE_SCRIPTS_SOURCE, event: "load", doctype, tier: "file_script" });
  });
  return loadClientScripts(doctype, undefined, files);
}

function loadFileScripts(doctype: string): Promise<void> {
  const inflight = fetching.get(doctype);
  const pending = fileScripts.get(doctype);
  if (inflight || !pending) return inflight ?? Promise.resolve();

  const loading = Promise.all(pending.map((script) => script.load())).then((modules) => {
    fileScripts.delete(doctype);
    pending.forEach(({ app }, index) => {
      const handlers = modules[index].default;
      if (!handlers) {
        console.warn(`[frappe] ignoring ${app}'s record script for ${doctype}: it has no default export`);
        return;
      }
      withRegisteringSource(app, () => registerRecordPage(doctype, handlers));
    });
  });
  fetching.set(doctype, loading);
  const done = () => fetching.delete(doctype);
  loading.then(done, done);
  return loading;
}
