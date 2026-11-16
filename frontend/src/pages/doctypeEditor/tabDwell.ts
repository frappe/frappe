// A held field or section opens the tab whose name it rests on, so the user can drop it inside that tab.
import type { DesignCanvas } from "./designCanvas";

/** Long enough that a pass across the strip does not flip tabs. */
export const TAB_DWELL_MS = 500;

/** Follows the pointer while a drag is in flight; returns the stop. */
export function openTabsOnDwell(canvas: DesignCanvas): () => void {
	let timer: ReturnType<typeof setTimeout> | undefined;
	let resting: string | null = null;

	function rest(name: string | null) {
		clearTimeout(timer);
		resting = name;
		if (!name || name === canvas.openTab.value?.name) return;
		timer = setTimeout(() => {
			canvas.openTabName.value = name;
			resting = null;
		}, TAB_DWELL_MS);
	}

	// Sortable's ghost takes no pointer events, so the point reads what lies under it.
	function move(event: PointerEvent) {
		const tab = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>("[data-canvas-tab]");
		const name = tab?.dataset.canvasTab ?? null;
		if (name !== resting) rest(name);
	}

	window.addEventListener("pointermove", move, true);
	return () => {
		clearTimeout(timer);
		window.removeEventListener("pointermove", move, true);
	};
}
