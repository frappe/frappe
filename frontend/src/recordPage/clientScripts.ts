// The Client Script tier: the doctype's stored scripts, fetched once per doctype,
// evaluated as modules and registered as sources after file scripts and extensions.
import { reactive, readonly, ref } from "vue";
import { call, toast } from "frappe-ui";
import type { RealtimeSocket } from "@framework/ui/socket";
import { withRegisteringSource } from "./context";
import { evaluateClientScript } from "./evaluateClientScript";
import { CLIENT_SCRIPT_CHANGED, GET_CLIENT_SCRIPTS } from "./clientScriptTypes";
import type { ClientScriptRow, ClientScriptsResponse } from "./clientScriptTypes";
import { registerRecordPage, unregisterSource } from "./registry";
import {
  reportCustomizationError,
  resetCustomizationErrorReports,
} from "./reportError";

// The tier's own fetch has no script to blame, so it reports under its own name.
const TIER_SOURCE = "client-scripts";

const tiers = new Map<string, Promise<void>>();
const sources = new Map<string, string[]>();
const toasted = new Set<string>();
// The shared toast channel; the compatibility layer reports a removal hit through it.
const notified = new Set<string>();
// Two saves in quick succession overlap: the later build must win, and the
// earlier one must not register its now-stale scripts behind it.
const builds = new Map<string, number>();
// Whether this session may write Client Scripts; the permission is on the doctype,
// so it is one answer for every doctype. Gates the failure toast and the editor.
const writable = ref(false);
// How often each doctype's stored scripts changed on the server since this tab opened.
const changes = reactive(new Map<string, number>());

export const canWriteClientScripts = readonly(writable);

/** A count that moves when the doctype's stored scripts change; a page on screen watches its own. */
export function clientScriptChanges(doctype: string): number {
  return changes.get(doctype) ?? 0;
}

/** Drops the cached tier so the next load re-reads, and moves the doctype's change count. */
export function invalidateClientScripts(doctype: string) {
  tiers.delete(doctype);
  changes.set(doctype, clientScriptChanges(doctype) + 1);
}

/** A Client Script saved, reordered or deleted anywhere invalidates its doctype's tier; returns the stop. */
export function watchClientScripts(socket: RealtimeSocket | undefined) {
  const onChanged = (...args: unknown[]) => {
    const { dt, view } = (args[0] ?? {}) as { dt?: unknown; view?: unknown };
    if (typeof dt === "string" && dt && view === "Record") invalidateClientScripts(dt);
  };
  socket?.on(CLIENT_SCRIPT_CHANGED, onChanged);
  return () => socket?.off(CLIENT_SCRIPT_CHANGED, onChanged);
}

/** Tells a script author, and only a script author, about a customization failure, once per key. */
export function toastScriptError(key: string, message: string) {
  if (!writable.value || notified.has(key)) return;
  notified.add(key);
  toast.error(message);
}

/** Resolves when the doctype's tier has registered; one fetch per doctype. */
export function loadClientScripts(doctype: string): Promise<void> {
  const loading = tiers.get(doctype) ?? buildTier(doctype);
  tiers.set(doctype, loading);
  return loading;
}

/** Drops the cached tier and builds it again — a saved or deleted script. */
export function reloadClientScripts(doctype: string): Promise<void> {
  tiers.delete(doctype);
  return loadClientScripts(doctype);
}

export function resetClientScripts() {
  for (const doctype of sources.keys()) clearTier(doctype);
  tiers.clear();
  changes.clear();
  builds.clear();
  toasted.clear();
  notified.clear();
  resetCustomizationErrorReports();
  writable.value = false;
}

async function buildTier(doctype: string) {
  const build = (builds.get(doctype) ?? 0) + 1;
  builds.set(doctype, build);
  clearTier(doctype);

  const response = await fetchScripts(doctype);
  if (builds.get(doctype) !== build) return;
  // Only an answer the server actually gave: a failed fetch must not read as
  // "no permission" and retract the editor's entry point.
  if (response) writable.value = response.can_write;
  for (const row of response?.scripts ?? []) {
    if (builds.get(doctype) !== build) return;
    await addScript(doctype, row, response!.can_write);
  }
}

/** Null when the tier could not be fetched — distinct from an empty tier. */
async function fetchScripts(
  doctype: string,
): Promise<ClientScriptsResponse | null> {
  try {
    return await call(GET_CLIENT_SCRIPTS, { dt: doctype, view: "Record" });
  } catch (error) {
    console.error(`[client-script] could not load scripts for ${doctype}`, error);
    reportCustomizationError(error, {
      source: TIER_SOURCE,
      tier: "client_script",
      event: "load",
      doctype,
    });
    return null;
  }
}

// A script that fails to load is skipped whole; the rest of the tier still runs.
async function addScript(
  doctype: string,
  row: ClientScriptRow,
  canWrite: boolean,
) {
  const source = sourceName(row.name);
  try {
    const handlers = await evaluateClientScript(row);
    await withRegisteringSource(source, async () =>
      registerRecordPage(doctype, handlers),
    );
    sources.get(doctype)?.push(source);
  } catch (error) {
    reportFailure(doctype, row.name, error, canWrite);
  }
}

function reportFailure(
  doctype: string,
  name: string,
  error: unknown,
  canWrite: boolean,
) {
  console.error(`[client-script] ${name} failed to load, skipped`, error);
  reportCustomizationError(error, {
    source: sourceName(name),
    event: "load",
    doctype,
  });
  if (!canWrite || toasted.has(name)) return;
  toasted.add(name);
  toast.error(`Client Script '${name}' failed to load`);
}

function clearTier(doctype: string) {
  for (const source of sources.get(doctype) ?? []) unregisterSource(source);
  sources.set(doctype, []);
}

function sourceName(name: string) {
  return `client-script:${name}`;
}
