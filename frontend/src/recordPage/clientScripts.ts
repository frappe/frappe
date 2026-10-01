// The Client Script tier: the doctype's stored scripts, fetched once per doctype,
// evaluated as modules and registered as sources after file scripts and extensions.
import { reactive, readonly, ref } from "vue";
import { toast } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import type { RealtimeSocket } from "@framework/ui/socket";
import { withRegisteringSource } from "./context";
import { evaluateClientScript } from "./evaluateClientScript";
import { CLIENT_SCRIPT_CHANGED, GET_CLIENT_SCRIPTS } from "./clientScriptTypes";
import type { ClientScriptRow, ClientScriptsResponse } from "./clientScriptTypes";
import { registerRecordPage, unregisterSource } from "./registry";
import type { AuthoredHandlers } from "./types";
import {
  reportCustomizationError,
  resetCustomizationErrorReports,
} from "./reportError";

// The tier's own fetch has no script to blame, so it reports under its own name.
const TIER_SOURCE = "client-scripts";

const tiers = new Map<string, Promise<void>>();
// The sources each doctype's registered tier holds; a doctype is absent until its first tier lands.
const sources = new Map<string, string[]>();
// Changed on the server: the registered tier stays until a fresh one replaces it.
const stale = new Set<string>();
const toasted = new Set<string>();
// The shared toast channel: one toast per key per session.
const notified = new Set<string>();
// Two saves in quick succession overlap: the later build must win, and the
// earlier one must not register its now-stale scripts behind it.
const builds = new Map<string, number>();
// Whether this session may write Client Scripts; the permission is on the doctype,
// so it is one answer for every doctype. Gates the failure toast and the editor.
const writable = ref(false);
// How often each doctype's stored scripts changed on the server since this tab opened.
const changes = reactive(new Map<string, number>());
const waits = new Map<string, string>();

export const canWriteClientScripts = readonly(writable);

/** A count that moves when the doctype's stored scripts change; a page on screen watches its own. */
export function clientScriptChanges(doctype: string): number {
  return changes.get(doctype) ?? 0;
}

/** Marks the tier stale so the next load re-reads, and moves the doctype's change count. */
export function invalidateClientScripts(doctype: string) {
  stale.add(doctype);
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

/** What the doctype's tier is still fetching or evaluating, or null once it is in. */
export function clientScriptWait(doctype: string): string | null {
  return waits.get(doctype) ?? null;
}

/** Resolves when the doctype's fresh tier has registered; one fetch per doctype until it goes stale. */
export function loadClientScripts(doctype: string): Promise<void> {
  const current = tiers.get(doctype);
  if (current && !stale.has(doctype)) return current;
  stale.delete(doctype);
  const loading = buildTier(doctype);
  tiers.set(doctype, loading);
  return loading;
}

/** True once a tier of the doctype has registered, stale or fresh. */
export function clientScriptsLoaded(doctype: string): boolean {
  return sources.has(doctype);
}

/** The sources of a registered tier that a build in flight will replace; a replay waiting for it skips them. */
export function replacedClientScripts(doctype: string): ReadonlySet<string> {
  return waits.has(doctype) ? new Set(sources.get(doctype)) : new Set();
}

/** Builds the tier again, keeping the registered one until it lands: a saved or deleted script. */
export function reloadClientScripts(doctype: string): Promise<void> {
  stale.add(doctype);
  return loadClientScripts(doctype);
}

export function resetClientScripts() {
  for (const doctype of sources.keys()) clearTier(doctype);
  sources.clear();
  stale.clear();
  tiers.clear();
  changes.clear();
  builds.clear();
  waits.clear();
  toasted.clear();
  notified.clear();
  resetCustomizationErrorReports();
  writable.value = false;
}

interface CompiledScript {
  row: ClientScriptRow;
  handlers: AuthoredHandlers;
}

// Every script compiles before any registers, so a replay meets the old tier or the new one, never a mix.
async function buildTier(doctype: string) {
  const build = (builds.get(doctype) ?? 0) + 1;
  builds.set(doctype, build);
  const current = () => builds.get(doctype) === build;

  waits.set(doctype, `the Client Script list for ${doctype}`);
  const response = await fetchScripts(doctype);
  if (!current()) return;
  if (!response && sources.has(doctype)) {
    // A failed re-read keeps the registered tier, and the next load tries again.
    stale.add(doctype);
    waits.delete(doctype);
    return;
  }
  // Only an answer the server actually gave: a failed fetch must not read as
  // "no permission" and retract the editor's entry point.
  if (response) writable.value = response.can_write;
  const compiled: CompiledScript[] = [];
  for (const row of response?.scripts ?? []) {
    if (!current()) return;
    waits.set(doctype, `${sourceName(row.name)} to load`);
    const handlers = await compileScript(doctype, row, response!.can_write);
    if (handlers) compiled.push({ row, handlers });
  }
  if (!current()) return;
  swapTier(doctype, compiled, response?.can_write ?? false);
  waits.delete(doctype);
}

/** Null when the tier could not be fetched — distinct from an empty tier. */
async function fetchScripts(
  doctype: string,
): Promise<ClientScriptsResponse | null> {
  try {
    const { data } = await runMethod<ClientScriptsResponse>(
      GET_CLIENT_SCRIPTS,
      { dt: doctype, view: "Record" },
      { http: "GET" },
    );
    return data;
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
async function compileScript(
  doctype: string,
  row: ClientScriptRow,
  canWrite: boolean,
): Promise<AuthoredHandlers | null> {
  try {
    return await evaluateClientScript(row);
  } catch (error) {
    reportFailure(doctype, row.name, error, canWrite);
    return null;
  }
}

/** The old tier's sources go and the new tier's register, in one synchronous step. */
function swapTier(doctype: string, compiled: CompiledScript[], canWrite: boolean) {
  clearTier(doctype);
  const registered: string[] = [];
  for (const { row, handlers } of compiled) {
    const source = sourceName(row.name);
    try {
      withRegisteringSource(source, () => registerRecordPage(doctype, handlers));
      registered.push(source);
    } catch (error) {
      unregisterSource(source);
      reportFailure(doctype, row.name, error, canWrite);
    }
  }
  sources.set(doctype, registered);
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
}

function sourceName(name: string) {
  return `client-script:${name}`;
}
