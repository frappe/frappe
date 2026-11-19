// Which saved view has changes on show. The open list page writes it, and the crumb, the save bar
// and the DocType sidebar read it, so the three never disagree.
import { onScopeDispose, shallowRef, watchEffect } from "vue";
import type { View } from "./view";

interface Marked {
	doctype: string;
	key: string;
}

const marked = shallowRef<Marked | null>(null);

/** Whether the saved view `key` of `doctype` has changes the person has not saved or discarded. */
export function isViewModified(doctype: string, key: string): boolean {
	return marked.value?.doctype === doctype && marked.value.key === key;
}

/** Mirrors the open view's modified state into the store; a plain view never marks, and leaving clears it. */
export function markModifiedView(view: View): void {
	watchEffect(() => {
		marked.value = view.layer && view.modified.value ? { doctype: view.doctype, key: view.key } : null;
	});
	onScopeDispose(() => {
		if (isViewModified(view.doctype, view.key)) marked.value = null;
	});
}
