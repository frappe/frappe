// The Client Script tier: the stored scripts of a doctype's record page, or of one app page,
// fetched once per tier, evaluated as modules and registered as sources after file scripts.
import { reactive, readonly, ref } from "vue";
import { toast } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import type { RealtimeSocket } from "@framework/ui/socket";
import { withRegisteringSource } from "@/pageEngine/context";
import { registerPageScript, unregisterPageSource } from "./pageScripts";
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
const APP_PAGE = "App Page";
const PAGE_SEPARATOR = "\u0000";

// Every map is keyed by tier: the doctype, or the doctype and an app page's name (see `tierKey`).
// The tier's latest build; when two saves overlap, only the build still held here registers.
const tiers = new Map<string, Promise<void>>();
// The sources each registered tier holds; a tier is absent until it first lands.
const sources = new Map<string, string[]>();
// Changed on the server: the registered tier stays until a fresh one replaces it.
const stale = new Set<string>();
const toasted = new Set<string>();
// The shared toast channel: one toast per key per session.
const notified = new Set<string>();
// Whether this session may write Client Scripts; the permission is on the doctype,
// so it is one answer for every doctype. Gates the failure toast and the editor.
const writable = ref(false);
// How often each doctype's stored scripts changed on the server since this tab opened.
const changes = reactive(new Map<string, number>());
const waits = new Map<string, string>();

export const canWriteClientScripts = readonly(writable);

/** A count that moves when the tier's stored scripts change; a page on screen watches its own. */
export function clientScriptChanges(doctype: string, page?: string): number {
  return changes.get(tierKey(doctype, page)) ?? 0;
}

/** Marks the tier stale so the next load re-reads, and moves its change count. */
export function invalidateClientScripts(doctype: string, page?: string) {
  const key = tierKey(doctype, page);
  stale.add(key);
  changes.set(key, clientScriptChanges(doctype, page) + 1);
}

/** A Client Script saved, reordered or deleted anywhere invalidates its tier; returns the stop. */
export function watchClientScripts(socket: RealtimeSocket | undefined) {
  const onChanged = (...args: unknown[]) => {
    const { dt, view, page } = (args[0] ?? {}) as { dt?: unknown; view?: unknown; page?: unknown };
    if (typeof dt !== "string" || !dt) return;
    if (view === "Record") invalidateClientScripts(dt);
    else if (view === APP_PAGE && typeof page === "string" && page) invalidateClientScripts(dt, page);
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

/** What the tier is still fetching or evaluating, or null once it is in. */
export function clientScriptWait(doctype: string, page?: string): string | null {
  return waits.get(tierKey(doctype, page)) ?? null;
}

/** Resolves when the fresh tier has registered; one fetch per tier until it goes stale. */
export function loadClientScripts(doctype: string, page?: string): Promise<void> {
  const key = tierKey(doctype, page);
  const current = tiers.get(key);
  if (current && !stale.has(key)) return current;
  stale.delete(key);
  const tier = { key, doctype, page };
  const loading: Promise<void> = buildTier(tier, () => tiers.get(key) === loading);
  tiers.set(key, loading);
  return loading;
}

/** True once the tier has registered, stale or fresh. */
export function clientScriptsLoaded(doctype: string, page?: string): boolean {
  return sources.has(tierKey(doctype, page));
}

/** The sources of a registered tier that a build in flight will replace; a replay waiting for it skips them. */
export function replacedClientScripts(doctype: string, page?: string): ReadonlySet<string> {
  const key = tierKey(doctype, page);
  return waits.has(key) ? new Set(sources.get(key)) : new Set();
}

export function resetClientScripts() {
  for (const key of sources.keys()) clearTier(key);
  sources.clear();
  stale.clear();
  tiers.clear();
  changes.clear();
  waits.clear();
  toasted.clear();
  notified.clear();
  resetCustomizationErrorReports();
  writable.value = false;
}

interface Tier {
  key: string;
  doctype: string;
  /** The app page's name; absent for the record page's tier. */
  page?: string;
}

interface CompiledScript {
  row: ClientScriptRow;
  handlers: AuthoredHandlers;
}

// Every script compiles before any registers, so a replay meets the old tier or the new one, never a mix.
async function buildTier(tier: Tier, current: () => boolean) {
  const { key, doctype } = tier;
  waits.set(key, `the Client Script list for ${tierLabel(tier)}`);
  const response = await fetchScripts(tier);
  if (!current()) return;
  if (!response && sources.has(key)) {
    // A failed re-read keeps the registered tier, and the next load tries again.
    stale.add(key);
    waits.delete(key);
    return;
  }
  // Only an answer the server actually gave: a failed fetch must not read as
  // "no permission" and retract the editor's entry point.
  if (response) writable.value = response.can_write;
  const compiled: CompiledScript[] = [];
  for (const row of response?.scripts ?? []) {
    if (!current()) return;
    waits.set(key, `${sourceName(row.name)} to load`);
    const handlers = await compileScript(doctype, row, response!.can_write);
    if (handlers) compiled.push({ row, handlers });
  }
  if (!current()) return;
  swapTier(tier, compiled, response?.can_write ?? false);
  waits.delete(key);
}

/** Null when the tier could not be fetched — distinct from an empty tier. */
async function fetchScripts(tier: Tier): Promise<ClientScriptsResponse | null> {
  const { doctype, page } = tier;
  const params = page ? { dt: doctype, view: APP_PAGE, page } : { dt: doctype, view: "Record" };
  try {
    const { data } = await runMethod<ClientScriptsResponse>(GET_CLIENT_SCRIPTS, params, {
      http: "GET",
    });
    return data;
  } catch (error) {
    console.error(`[client-script] could not load scripts for ${tierLabel(tier)}`, error);
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
  if (row.error) {
    reportFailure(doctype, row.name, new Error(row.error), canWrite);
    return null;
  }
  try {
    return await evaluateClientScript(row);
  } catch (error) {
    reportFailure(doctype, row.name, error, canWrite);
    return null;
  }
}

/** The old tier's sources go and the new tier's register, in one synchronous step. */
function swapTier(tier: Tier, compiled: CompiledScript[], canWrite: boolean) {
  const { key, doctype, page } = tier;
  clearTier(key);
  const registered: string[] = [];
  for (const { row, handlers } of compiled) {
    const source = sourceName(row.name);
    try {
      withRegisteringSource(source, () =>
        page
          ? registerPageScript(doctype, page, handlers)
          : registerRecordPage(doctype, handlers),
      );
      registered.push(source);
    } catch (error) {
      unregisterTierSource(tier, source);
      reportFailure(doctype, row.name, error, canWrite);
    }
  }
  sources.set(key, registered);
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

function clearTier(key: string) {
  const [doctype, page] = key.split(PAGE_SEPARATOR);
  for (const source of sources.get(key) ?? []) unregisterTierSource({ key, doctype, page }, source);
}

function unregisterTierSource({ doctype, page }: Tier, source: string) {
  if (page) unregisterPageSource(source, doctype, page);
  else unregisterSource(source);
}

function tierKey(doctype: string, page?: string) {
  return page ? `${doctype}${PAGE_SEPARATOR}${page}` : doctype;
}

function tierLabel({ doctype, page }: Tier) {
  return page ? `the ${page} page of ${doctype}` : doctype;
}

function sourceName(name: string) {
  return `client-script:${name}`;
}
