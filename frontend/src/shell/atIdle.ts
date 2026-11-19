/** Runs `work` once the browser is idle after the next paint. */
export function atIdle(work: () => unknown) {
	requestAnimationFrame(() => {
		// Safari has no `requestIdleCallback`.
		if (typeof requestIdleCallback === "function") requestIdleCallback(() => void work());
		else setTimeout(() => void work());
	});
}
