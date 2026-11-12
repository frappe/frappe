// The list.js files, from a generated module of their own: only the list page imports it, so the
// shell and the other pages do not grow with each app's list.js.
import listScripts from "virtual:frappe/list-scripts";
import { listScriptsInRunOrder } from "@/contributions/registry";
import type { ListScript } from "@/contributions/types";

// Doctype -> its list.js files in run order, indexed on the first read.
let byDoctype: Map<string, ListScript[]> | null = null;

function index(): Map<string, ListScript[]> {
	if (byDoctype) return byDoctype;
	byDoctype = new Map();
	for (const script of listScriptsInRunOrder(listScripts)) {
		addListScript(script.doctype, { app: script.app, load: script.load });
	}
	return byDoctype;
}

/** Adds an app's list.js behind the doctype's earlier ones. */
export function addListScript(doctype: string, script: ListScript) {
	const scripts = index();
	scripts.set(doctype, [...(scripts.get(doctype) ?? []), script]);
}

/** The doctype's list.js files, in run order. */
export function listScriptsFor(doctype: string): readonly ListScript[] {
	return index().get(doctype) ?? [];
}
