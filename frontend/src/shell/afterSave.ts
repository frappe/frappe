// The after-save registry: what the desk refreshes when a settings binding of a doctype saves.

export interface SavedBinding {
	doctype: string;
	name: string;
	/** The saved record, as the server sent it back. */
	doc: Record<string, any>;
	/** The fields the save sent. */
	changed: string[];
}

export type AfterSave = (saved: SavedBinding) => void;

const registry = new Map<string, AfterSave[]>();

/** Runs `run` after each save of a binding of `doctype`; the returned function removes it. */
export function registerAfterSave(doctype: string, run: AfterSave): () => void {
	registry.set(doctype, [...(registry.get(doctype) ?? []), run]);
	return () => registry.set(doctype, registry.get(doctype)?.filter((one) => one !== run) ?? []);
}

/** A handler that throws is logged and does not stop the others. */
export function runAfterSave(saved: SavedBinding) {
	for (const run of registry.get(saved.doctype) ?? []) {
		try {
			run(saved);
		} catch (error) {
			console.error(`[frappe] an after-save handler for ${saved.doctype} failed`, error);
		}
	}
}
