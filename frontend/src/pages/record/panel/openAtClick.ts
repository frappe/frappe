function caretAt(x: number, y: number): { node: Node; offset: number } | null {
	const doc = document as Document & {
		caretRangeFromPoint?: (x: number, y: number) => Range | null;
	};
	const hit = document.caretPositionFromPoint?.(x, y);
	const node = hit?.offsetNode ?? doc.caretRangeFromPoint?.(x, y)?.startContainer;
	const offset = hit?.offset ?? doc.caretRangeFromPoint?.(x, y)?.startOffset;
	if (!node || offset === undefined || node.nodeType !== Node.TEXT_NODE) return null;
	return { node, offset };
}

/** The offset into `host`'s text under a click, or null when the click missed the text. */
export function textOffsetAt(host: HTMLElement, x: number, y: number): number | null {
	const at = caretAt(x, y);
	return at && host.contains(at.node) ? at.offset : null;
}

/** Puts the caret of a focused rich-text body under a click, at the top of its lines; the body lays its text out as the row did at rest. */
export function placeCaretAtPoint(host: HTMLElement, x: number, y: number) {
	const at = caretAt(x, y);
	if (!at || !host.contains(at.node)) return;
	document.getSelection()?.collapse(at.node, at.offset);
	for (let el = at.node.parentElement; el && el !== host; el = el.parentElement) el.scrollTop = 0;
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
