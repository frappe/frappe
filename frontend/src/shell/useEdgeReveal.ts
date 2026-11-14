// When the floating rail shows: the pointer at the window's edge on the navigation's side, held
// open while it stays near, over the rail, or while focus or a menu is in it. v1's dock numbers.
import { onBeforeUnmount, onMounted, ref, type Ref } from "vue";
import type { PhysicalSide } from "./navigationSide";

/** The pointer within this many px of the edge opens the rail. */
export const EDGE_BAND = 1;
/** Once open, the rail stays while the pointer is within this many px of the edge. */
export const STAY_BAND = 90;
/** On the page scrollbar's side, how long the pointer rests in the edge band before the rail opens. */
export const END_WAIT = 200;

const THUMB = "[data-slot=scroll-area-thumb]";

interface EdgeReveal {
	/** The rail on screen. */
	open: Ref<boolean>;
	close: () => void;
}

/**
 * `side` is the window edge the rail is on. `scrollbarSide` is true when the page scrollbar is on
 * that edge, so a pointer on its way to the thumb must not open the rail at once. `rail` is the
 * rail's own element: pointer, focus and open menus inside it keep it open.
 */
export function useEdgeReveal(options: {
	side: () => PhysicalSide;
	scrollbarSide: () => boolean;
	rail: Ref<HTMLElement | null>;
}): EdgeReveal {
	const open = ref(false);
	let wait: ReturnType<typeof setTimeout> | undefined;
	// Where the pointer last was, for the moment focus leaves a rail the pointer has long left.
	let lastAway = Infinity;

	function distance(event: PointerEvent) {
		return options.side() === "left"
			? event.clientX
			: document.documentElement.clientWidth - 1 - event.clientX;
	}

	function cancelWait() {
		clearTimeout(wait);
		wait = undefined;
	}

	function holds(target: EventTarget | null) {
		const rail = options.rail.value;
		if (!rail) return false;
		return (
			(target instanceof Node && rail.contains(target)) ||
			rail.contains(document.activeElement) ||
			// A menu opened from the rail draws in a portal, so its trigger is what says it shows.
			!!rail.querySelector('[aria-expanded="true"]')
		);
	}

	function onMove(event: PointerEvent) {
		const away = (lastAway = distance(event));

		if (open.value) {
			if (away > STAY_BAND && !holds(event.target)) close();
			return;
		}

		if (away >= EDGE_BAND) return cancelWait();
		if (!options.scrollbarSide()) return void (open.value = true);

		// The scrollbar's side: a press or the thumb under the pointer is a scroll, not a reveal.
		const overThumb = event.target instanceof Element && !!event.target.closest(THUMB);
		if (event.buttons !== 0 || overThumb) return cancelWait();
		wait ??= setTimeout(() => {
			wait = undefined;
			open.value = true;
		}, END_WAIT);
	}

	function onKey(event: KeyboardEvent) {
		if (event.key !== "Escape" || !open.value || event.defaultPrevented) return;
		const inside = options.rail.value?.contains(document.activeElement);
		close();
		if (inside) document.querySelector<HTMLElement>("main")?.focus();
	}

	function close() {
		cancelWait();
		open.value = false;
	}

	function onFocusIn(event: FocusEvent) {
		if (options.rail.value?.contains(event.target as Node)) open.value = true;
	}

	// A menu's focus moves to its portal first, so the check waits for its trigger to say it shows.
	function onFocusOut(event: FocusEvent) {
		if (!options.rail.value?.contains(event.target as Node)) return;
		setTimeout(() => {
			if (open.value && lastAway > STAY_BAND && !holds(null)) close();
		});
	}

	onMounted(() => {
		document.addEventListener("pointermove", onMove);
		document.addEventListener("pointerdown", cancelWait, true);
		document.addEventListener("keydown", onKey);
		document.addEventListener("focusin", onFocusIn);
		document.addEventListener("focusout", onFocusOut);
	});

	onBeforeUnmount(() => {
		cancelWait();
		document.removeEventListener("pointermove", onMove);
		document.removeEventListener("pointerdown", cancelWait, true);
		document.removeEventListener("keydown", onKey);
		document.removeEventListener("focusin", onFocusIn);
		document.removeEventListener("focusout", onFocusOut);
	});

	return { open, close };
}
