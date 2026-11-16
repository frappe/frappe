// The right-click on a section, column or field of the canvas: it selects the target as a click does and
// opens that target's menu where the pointer is. The menu itself is a lazy chunk, loaded on the first one.
import { defineAsyncComponent } from "vue";
import { canvasMenu, selectOn, type MenuItem } from "./canvasMenu";
import type { DesignCanvas } from "./designCanvas";

export interface ContextMenuAt {
	item: MenuItem;
	x: number;
	y: number;
	/** The element the right-click landed on, which takes the focus back when the menu closes. */
	target: HTMLElement | null;
}

export const CanvasContextMenu = defineAsyncComponent(() => import("./CanvasContextMenu.vue"));

/** The innermost target takes the event; a menu with nothing to do (read-only canvas), an input and a Shift-click keep the browser's menu. */
export function openContextMenu(canvas: DesignCanvas, event: MouseEvent, item: MenuItem) {
	if (keepsBrowserMenu(event) || canvasMenu(canvas, item).every((option) => option.disabled)) return;
	event.preventDefault();
	event.stopPropagation();
	selectOn(canvas, item);
	canvas.contextMenu.value = { item, x: event.clientX, y: event.clientY, target: event.currentTarget as HTMLElement | null };
}

function keepsBrowserMenu(event: MouseEvent) {
	if (event.shiftKey) return true;
	return Boolean((event.target as Element).closest("input, textarea, select, [contenteditable]"));
}

/** Closes the menu and puts the focus back on what it opened on, as the section's ⋯ menu does. */
export function closeContextMenu(canvas: DesignCanvas) {
	const target = canvas.contextMenu.value?.target;
	canvas.contextMenu.value = null;
	if (target) setTimeout(() => focusOnce(target), FOCUS_BACK_AFTER);
}

// The menu's focus scope hands the focus back to what held it before, within about 40 ms of the close
// (measured); the target takes it after that.
const FOCUS_BACK_AFTER = 100;

// The canvas items take no focus of their own: this one gets it for this one call. A click that
// dismissed the menu on a field or button has already put the focus there, and keeps it.
function focusOnce(target: HTMLElement) {
	if (!target.isConnected || document.activeElement?.closest(TAKES_FOCUS_ITSELF)) return;
	target.tabIndex = -1;
	target.classList.add("outline-none");
	target.focus({ preventScroll: true });
	target.addEventListener(
		"blur",
		() => {
			target.removeAttribute("tabindex");
			target.classList.remove("outline-none");
		},
		{ once: true }
	);
}

const TAKES_FOCUS_ITSELF = "input, textarea, select, button, [contenteditable]";
