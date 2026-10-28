// An app page's scripts: the handler file its own app ships beside it, then the Client Scripts
// that name its doctype and page. Another app's file never runs on it.
import { registeringSource } from "@/pageEngine/context";
import type { Handler, Registration } from "@/pageEngine/types";

type Handlers = Record<string, unknown>;

interface StoredScript extends Registration {
  target: string;
}

const files = new Map<string, Registration>();
const stored: StoredScript[] = [];

/** The handler file `app` ships for its page `page` of `doctype`. */
export function addPageFile(app: string, doctype: string, page: string, handlers: Handlers) {
  files.set(fileKey(app, doctype, page), { source: app, handlers: functionsOf(handlers) });
}

/** A stored script for every app page named `page` on `doctype`, under the registering source. */
export function registerPageScript(doctype: string, page: string, handlers: Handlers) {
  const target = targetKey(doctype, page);
  stored.push({ source: registeringSource(), target, handlers: functionsOf(handlers) });
}

/** The app's own handler file first, then the stored scripts in registration order. */
export function pageScriptsFor(app: string, doctype: string, page: string): Registration[] {
  const file = files.get(fileKey(app, doctype, page));
  const target = targetKey(doctype, page);
  const scripts = stored.filter((script) => script.target === target);
  return [...(file ? [file] : []), ...scripts];
}

export function unregisterPageSource(source: string, doctype: string, page: string) {
  const target = targetKey(doctype, page);
  for (let index = stored.length - 1; index >= 0; index--)
    if (stored[index].source === source && stored[index].target === target) stored.splice(index, 1);
}

export function resetPageScripts() {
  files.clear();
  stored.length = 0;
}

// An app page has no nested blocks, so a member that is no function is no handler.
function functionsOf(handlers: Handlers): Record<string, Handler> {
  const entries = Object.entries(handlers);
  const functions = entries.filter(([, value]) => typeof value === "function");
  if (import.meta.env.DEV && functions.length < entries.length)
    console.warn(`[page] ${registeringSource()} has members that are not handlers, ignored on an app page`);
  return Object.fromEntries(functions) as Record<string, Handler>;
}

function fileKey(app: string, doctype: string, page: string) {
  return `${app}\u0000${targetKey(doctype, page)}`;
}

function targetKey(doctype: string, page: string) {
  return `${doctype}\u0000${page}`;
}
