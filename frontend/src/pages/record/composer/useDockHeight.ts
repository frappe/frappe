// The docked card's height: dragged from its top edge, clamped to the window, kept per user.
import { ref } from "vue";
import { useEventListener, useLocalStorage } from "@vueuse/core";

export const DEFAULT_DOCK_HEIGHT = 320;
export const MIN_DOCK_HEIGHT = 180;
const MAX_WINDOW_SHARE = 0.72;

export function useDockHeight(user: string) {
	const height = useLocalStorage(`desk:composer-height:${user}`, DEFAULT_DOCK_HEIGHT);
	height.value = clampDockHeight(height.value);
	const dragging = ref(false);
	let start = { height: 0, y: 0 };

	function begin(event: PointerEvent, current: number) {
		start = { height: current, y: event.clientY };
		dragging.value = true;
		(event.currentTarget as HTMLElement | null)?.setPointerCapture?.(event.pointerId);
	}

	function move(event: PointerEvent) {
		if (dragging.value) height.value = clampDockHeight(start.height + start.y - event.clientY);
	}

	function end() {
		dragging.value = false;
	}

	useEventListener(window, "resize", () => (height.value = clampDockHeight(height.value)));
	return { height, dragging, begin, move, end };
}

/** Dragging up grows the card; it never outgrows most of the window, nor shrinks past the editor. */
export function clampDockHeight(height: number, windowHeight = window.innerHeight) {
	const ceiling = Math.max(Math.floor(windowHeight * MAX_WINDOW_SHARE), MIN_DOCK_HEIGHT);
	return Math.min(Math.max(Math.round(height), MIN_DOCK_HEIGHT), ceiling);
}
