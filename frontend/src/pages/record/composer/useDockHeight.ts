// The docked card's height: dragged from its top edge, clamped to the window, kept per user.
import { ref } from "vue";
import { useEventListener } from "@vueuse/core";
import { browserMemory } from "@/browserMemory";

export const DEFAULT_DOCK_HEIGHT = 320;
export const MIN_DOCK_HEIGHT = 180;
const MAX_WINDOW_SHARE = 0.72;

export function useDockHeight(user: string) {
	const memory = browserMemory("composer-height", user, isHeight, `desk:composer-height:${user}`);
	const height = ref(clampDockHeight(memory.recall() ?? DEFAULT_DOCK_HEIGHT));
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
		if (!dragging.value) return;
		dragging.value = false;
		memory.remember(height.value);
	}

	useEventListener(window, "resize", () => (height.value = clampDockHeight(height.value)));
	return { height, dragging, begin, move, end };
}

/** Dragging up grows the card; it never outgrows most of the window, nor shrinks past the editor. */
export function clampDockHeight(height: number, windowHeight = window.innerHeight) {
	const ceiling = Math.max(Math.floor(windowHeight * MAX_WINDOW_SHARE), MIN_DOCK_HEIGHT);
	return Math.min(Math.max(Math.round(height), MIN_DOCK_HEIGHT), ceiling);
}

function isHeight(value: unknown): value is number {
	return typeof value === "number" && Number.isFinite(value);
}
