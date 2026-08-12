// The Page Script tier: the doctype's stored scripts, fetched once per doctype,
// evaluated as modules and registered as sources in creation order — after the
// host's file scripts and app extensions, because this runs at page mount.
import { call, toast } from "frappe-ui";
import { withRegisteringSource } from "./context";
import { evaluatePageScript } from "./evaluatePageScript";
import { GET_PAGE_SCRIPTS } from "./pageScriptTypes";
import type { PageScriptRow, PageScriptsResponse } from "./pageScriptTypes";
import { registerRecordPage, unregisterSource } from "./registry";

const tiers = new Map<string, Promise<void>>();
const sources = new Map<string, string[]>();
const toasted = new Set<string>();

/** Resolves when the doctype's tier has registered; one fetch per doctype. */
export function loadPageScripts(doctype: string): Promise<void> {
	const loading = tiers.get(doctype) ?? buildTier(doctype);
	tiers.set(doctype, loading);
	return loading;
}

/** Drops the cached tier and builds it again — a saved or deleted script. */
export function reloadPageScripts(doctype: string): Promise<void> {
	tiers.delete(doctype);
	return loadPageScripts(doctype);
}

export function resetPageScripts() {
	for (const doctype of sources.keys()) clearTier(doctype);
	tiers.clear();
	toasted.clear();
}

async function buildTier(doctype: string) {
	clearTier(doctype);
	const response = await fetchScripts(doctype);
	for (const row of response.scripts) await addScript(doctype, row, response.can_write);
}

async function fetchScripts(doctype: string): Promise<PageScriptsResponse> {
	try {
		return await call(GET_PAGE_SCRIPTS, { dt: doctype, view: "Record" });
	} catch (error) {
		console.error(`[page-script] could not load scripts for ${doctype}`, error);
		return { scripts: [], can_write: false };
	}
}

// A script that fails to load is skipped whole; the rest of the tier still runs.
async function addScript(doctype: string, row: PageScriptRow, canWrite: boolean) {
	const source = sourceName(row.name);
	try {
		const handlers = await evaluatePageScript(row);
		await withRegisteringSource(source, async () =>
			registerRecordPage(doctype, handlers),
		);
		sources.get(doctype)?.push(source);
	} catch (error) {
		reportFailure(row.name, error, canWrite);
	}
}

function reportFailure(name: string, error: unknown, canWrite: boolean) {
	console.error(`[page-script] ${name} failed to load, skipped`, error);
	if (!canWrite || toasted.has(name)) return;
	toasted.add(name);
	toast.error(`Page Script '${name}' failed to load`);
}

function clearTier(doctype: string) {
	for (const source of sources.get(doctype) ?? []) unregisterSource(source);
	sources.set(doctype, []);
}

function sourceName(name: string) {
	return `page-script:${name}`;
}
