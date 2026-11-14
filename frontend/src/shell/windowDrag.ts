// Drags a standing window out of the row. The position is the window's left and its distance
// from the viewport bottom, so a taller body grows upward as it does in the row.
import { onUnmounted } from "vue";
import { navInsetRight } from "./navigationInset";
import type { StandingWindow } from "./standingWindows";

export const MARGIN = 24;
const THRESHOLD = 4;

export interface Placement {
	left: number;
	bottom: number;
}

/** Keeps `placed` inside the shell's margin and clear of a right-hand navigation, for a window `width` wide, at least `minHeight` tall. */
export function clampPlacement(
	placed: Placement,
	viewport: { width: number; height: number },
	width: number,
	minHeight = 0
): Placement {
	return {
		left: clamp(placed.left, viewport.width - navInsetRight.value - MARGIN - width),
		bottom: clamp(placed.bottom, viewport.height - MARGIN - minHeight),
	};
}

export function useWindowDrag(entry: StandingWindow) {
	let release: (() => void) | null = null;

	/** Starts a drag of `element` from a primary-button pointerdown; it takes hold past the threshold. */
	function start(event: PointerEvent, element: HTMLElement, width?: number) {
		if (event.button !== 0) return;
		release?.();
		const box = element.getBoundingClientRect();
		let moved = false;

		function onMove(move: PointerEvent) {
			if (move.pointerId !== event.pointerId) return;
			const deltaX = move.clientX - event.clientX;
			const deltaY = move.clientY - event.clientY;
			if (!moved && Math.hypot(deltaX, deltaY) < THRESHOLD) return;
			moved = true;
			entry.placed = clampPlacement(
				{ left: box.left + deltaX, bottom: innerHeight - box.bottom - deltaY },
				{ width: innerWidth, height: innerHeight },
				width ?? box.width,
				box.height
			);
		}

		function onEnd(end: PointerEvent) {
			if (end.pointerId !== event.pointerId) return;
			release?.();
			if (moved) swallowClick();
		}

		window.addEventListener("pointermove", onMove);
		window.addEventListener("pointerup", onEnd);
		window.addEventListener("pointercancel", onEnd);
		release = () => {
			window.removeEventListener("pointermove", onMove);
			window.removeEventListener("pointerup", onEnd);
			window.removeEventListener("pointercancel", onEnd);
			release = null;
		};
	}

	function putBack() {
		entry.placed = null;
	}

	onUnmounted(() => release?.());

	return { start, putBack };
}

// The click that closes a drag must not restore a pill. A drag that ended elsewhere has none.
function swallowClick() {
	const stop = (event: Event) => event.stopPropagation();
	window.addEventListener("click", stop, { capture: true, once: true });
	setTimeout(() => window.removeEventListener("click", stop, { capture: true }));
}

function clamp(value: number, max: number) {
	return Math.max(MARGIN, Math.min(value, max));
}
