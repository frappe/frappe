/** The offset into `host`'s text under a click, or null when the click missed the text. */
export function textOffsetAt(host: HTMLElement, x: number, y: number): number | null {
	const doc = document as Document & {
		caretRangeFromPoint?: (x: number, y: number) => Range | null;
	};
	const hit = document.caretPositionFromPoint?.(x, y);
	const node = hit?.offsetNode ?? doc.caretRangeFromPoint?.(x, y)?.startContainer;
	const offset = hit?.offset ?? doc.caretRangeFromPoint?.(x, y)?.startOffset;
	if (!node || offset === undefined || node.nodeType !== Node.TEXT_NODE) return null;
	return host.contains(node) ? offset : null;
}

/**
 * An open multi-line row shows the lines it showed at rest: it never scrolls to the caret, which
 * sits where the click landed. Opened from the keyboard it takes the end when that is in view, else
 * the start.
 */
export function placeCaret(area: HTMLTextAreaElement, at: number | null) {
	const fits = area.scrollHeight <= area.clientHeight;
	const to = Math.min(at ?? (fits ? area.value.length : 0), area.value.length);
	area.setSelectionRange(to, to);
	area.scrollTop = 0;
}
