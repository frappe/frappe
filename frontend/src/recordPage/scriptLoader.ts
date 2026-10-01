// The one loader the record page asks for a doctype's scripts: the file scripts apps ship, then its Client Scripts.
import { loadClientScripts } from "./clientScripts";
import { withRegisteringSource } from "./context";
import { registerRecordPage } from "./registry";
import type { AuthoredHandlers } from "./types";

export interface FileScript {
  app: string;
  handlers: AuthoredHandlers;
}

// In run order; a doctype leaves the map when its first load registers them.
const fileScripts = new Map<string, FileScript[]>();

/** Adds an app's file script behind the doctype's earlier ones; the doctype's first load registers it. */
export function addFileScript(doctype: string, script: FileScript) {
  fileScripts.set(doctype, [...(fileScripts.get(doctype) ?? []), script]);
}

/** Resolves when the doctype's file scripts and its fresh Client Script tier have registered. */
export function loadRecordScripts(doctype: string): Promise<void> {
  const pending = fileScripts.get(doctype) ?? [];
  fileScripts.delete(doctype);
  for (const { app, handlers } of pending)
    withRegisteringSource(app, () => registerRecordPage(doctype, handlers));
  return loadClientScripts(doctype);
}
