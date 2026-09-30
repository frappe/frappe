// A kept scroll offset put back once the content is tall enough, and a scroll watched once per frame.

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

/** Calls `saw` once per frame while the element, or a box inside it, scrolls; returns the stop. */
export function onScrollFrames(element: HTMLElement, saw: () => void): () => void {
	let frame = 0;
	const scrolled = () => {
		cancelAnimationFrame(frame);
		frame = requestAnimationFrame(saw);
	};
	// Capture: a scroll event does not bubble.
	element.addEventListener("scroll", scrolled, { capture: true, passive: true });
	return () => {
		cancelAnimationFrame(frame);
		element.removeEventListener("scroll", scrolled, { capture: true });
	};
}
