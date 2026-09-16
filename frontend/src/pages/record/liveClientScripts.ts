// Re-runs the page's scripts when a Client Script of its doctype changes on the server.
import { watch, type Ref } from "vue";
import { clientScriptChanges } from "@/recordPage";

interface Options {
	doctype: Ref<string | null>;
	/** Unsaved edits on screen: the page then keeps its scripts until its next load. */
	dirty: () => boolean;
	/** The page's own `refresh`; undefined while no page is built. */
	refresh: () => Promise<void> | undefined;
}

/** A clean page re-runs at once; a dirty one waits, and its own save or reload re-reads the tier. */
export function useLiveClientScripts({ doctype, dirty, refresh }: Options) {
	return watch(
		[doctype, () => (doctype.value ? clientScriptChanges(doctype.value) : 0)],
		([current, count], [previous]) => {
			if (current !== previous || !count || dirty()) return;
			refresh()?.catch((error) => {
				if (import.meta.env.DEV) console.warn("[record-page] script re-run failed", error);
			});
		}
	);
}
