/** A keypress inside a dialog, a popover or a dropdown belongs to it: the overlay it came from, or none. */
export function overlayOf(target: EventTarget | null): Element | null {
	return target instanceof Element
		? target.closest('[role="dialog"],[role="listbox"],[role="menu"]')
		: null;
}
