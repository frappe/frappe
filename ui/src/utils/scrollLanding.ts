// A kept scroll offset put back once the content is tall enough, and a scroll reported once it settles.

const LANDING_FRAMES = 60;

// Not `scrollend`: the browser's scroll anchoring moves the offset with scroll events alone.
const SETTLE_MS = 150;

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

/** Calls `settled` once scrolling on the element, or a box inside it, has stopped; returns the stop. */
export function onScrollSettled(element: HTMLElement, settled: () => void): () => void {
	// Capture: scroll events do not bubble.
	const options = { capture: true, passive: true };
	let timer: ReturnType<typeof setTimeout> | undefined;
	const scrolled = () => {
		clearTimeout(timer);
		timer = setTimeout(settled, SETTLE_MS);
	};
	element.addEventListener("scroll", scrolled, options);
	return () => {
		clearTimeout(timer);
		element.removeEventListener("scroll", scrolled, options);
	};
}
