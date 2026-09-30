// A kept scroll offset put back once the content is tall enough, a scroll reported once it
// settles, and a view kept in the history entry.

const LANDING_FRAMES = 60;

/** Sets the offset now, or over the frames the content takes to grow; after 60 frames it sets what fits. */
export function landScroll(element: HTMLElement, top: number): Promise<void> {
	return new Promise((resolve) => {
		let frames = LANDING_FRAMES;
		const attempt = () => {
			const fits = element.scrollHeight - element.clientHeight >= top;
			if (!fits && frames-- > 0) return void requestAnimationFrame(attempt);
			element.scrollTop = top;
			resolve();
		};
		attempt();
	});
}

/** Writes one key of the history entry's state, over vue-router's keys; false when the browser refuses. */
export function keepInHistory(key: string, value: unknown): boolean {
	try {
		history.replaceState({ ...history.state, [key]: value }, "");
		return true;
	} catch (error) {
		console.warn(`[history] ${key} was not kept in the history entry`, error);
		return false;
	}
}

/**
 * Calls `settled` once per scroll gesture on the element or a box inside it; returns the stop.
 * A browser limits history writes, and a gesture ends far below that rate.
 */
export function onScrollSettled(element: HTMLElement, settled: () => void): () => void {
	// Capture: scroll events do not bubble.
	const options = { capture: true, passive: true };
	if ("onscrollend" in window) {
		element.addEventListener("scrollend", settled, options);
		return () => element.removeEventListener("scrollend", settled, options);
	}
	let frame = 0;
	const scrolled = () => {
		cancelAnimationFrame(frame);
		frame = requestAnimationFrame(settled);
	};
	element.addEventListener("scroll", scrolled, options);
	return () => {
		cancelAnimationFrame(frame);
		element.removeEventListener("scroll", scrolled, options);
	};
}
