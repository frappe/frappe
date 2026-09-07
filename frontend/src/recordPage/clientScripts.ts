// The Client Script tier: the doctype's stored scripts, fetched once per doctype,
// evaluated as modules and registered as sources after file scripts and extensions.
import { readonly, ref } from "vue";
import { call, toast } from "frappe-ui";
import { withRegisteringSource } from "./context";
import { evaluateClientScript } from "./evaluateClientScript";
import { GET_CLIENT_SCRIPTS } from "./clientScriptTypes";
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

export const canWriteClientScripts = readonly(writable);

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
