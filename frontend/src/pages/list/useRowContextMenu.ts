// The right-click on a row: which clicks keep the browser's menu, and what ours needs to open. The menu itself
// is a lazy chunk, so a list that is never right-clicked does not load it.
import { toast } from "frappe-ui";
import { defineAsyncComponent, shallowRef, type Ref } from "vue";
import { __ } from "@/i18n";

export interface ContextMenuAt {
	row: string;
	x: number;
	y: number;
}

// One retry for a chunk that failed to load; the click already held back the browser's menu, so say why nothing opened.
export const RowContextMenu = defineAsyncComponent({
	loader: () => import("./RowContextMenu.vue"),
	onError: (_error, retry, fail, attempts) => {
		if (attempts <= 1) return retry();
		toast.error(__("Could not open the menu"));
		fail();
	},
});

export function useRowContextMenu(selection: Ref<string[]>) {
	const at = shallowRef<ContextMenuAt | null>(null);
	// Kept once loaded, so the next right-click opens at once.
	const loaded = shallowRef(false);

	function open(row: string, event: MouseEvent) {
		if (keepsBrowserMenu(event)) return;
		event.preventDefault();
		if (!selection.value.includes(row)) selection.value = [row];
		loaded.value = true;
		at.value = { row, x: event.clientX, y: event.clientY };
	}

	function close() {
		at.value = null;
	}

	return { at, loaded, open, close };
}

// A Shift-held click is the user asking for the browser's menu; the context-menu key and Shift+F10 arrive with button 0.
function keepsBrowserMenu(event: MouseEvent) {
	const target = event.target as Element;
	if (event.shiftKey && event.button === 2) return true;
	if (target.closest("input, textarea, select, [contenteditable]")) return true;
	const selected = window.getSelection();
	return !!selected?.toString() && selected.containsNode(target, true);
}
