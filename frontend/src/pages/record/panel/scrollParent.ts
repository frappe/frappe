/** The nearest ancestor that scrolls vertically: the panel's column. */
export function scrollParent(node: HTMLElement | null): HTMLElement | null {
	let parent = node?.parentElement ?? null;
	while (parent && !/(auto|scroll)/.test(getComputedStyle(parent).overflowY))
		parent = parent.parentElement;
	return parent;
}
