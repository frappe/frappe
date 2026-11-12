// The List Page Client Scripts a doctype's list runs after its list.js files: the same text, from a stored row.
import { shallowRef } from "vue";
import type { Handler, Registration } from "./types";

/** A list.js or a Client Script, loaded: its handlers. */
export type LoadedListScript = Registration;

// A shallowRef, so a computed that read a doctype's scripts before a swap reads them again.
const stored = shallowRef(new Map<string, LoadedListScript[]>());

/** A handlers module as the list runs it: its functions are the handlers. */
export function loadedListScript(source: string, exported: Record<string, unknown>): LoadedListScript {
  const handlers: Record<string, Handler> = {};
  for (const [key, value] of Object.entries(exported))
    if (typeof value === "function") handlers[key] = value as Handler;
  return { source, handlers };
}

/** The stored scripts of the doctype's list, in registration order; reactive. */
export function storedListScripts(doctype: string): LoadedListScript[] {
  return stored.value.get(doctype) ?? [];
}

export function registerStoredListScript(doctype: string, source: string, exported: Record<string, unknown>) {
  setStored(doctype, [...storedListScripts(doctype), loadedListScript(source, exported)]);
}

export function unregisterStoredListSource(doctype: string, source: string) {
  setStored(
    doctype,
    storedListScripts(doctype).filter((script) => script.source !== source),
  );
}

function setStored(doctype: string, scripts: LoadedListScript[]) {
  const next = new Map(stored.value);
  next.set(doctype, scripts);
  stored.value = next;
}
