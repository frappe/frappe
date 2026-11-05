// What modal overlays (frappe.ui.Modal, frappe.ui.BottomSheet) share: the
// page behind is out of reach while one is open, Tab cycles inside it, and
// focus goes back to where it came from when it closes.

import { TABBABLE } from "./utils.js";

/** Page-level layers in <body> that may take focus from an open overlay. */
export const LAYERS =
	".es-bottom-sheet-root, .modal, .air-datepicker-global-container, .es-toast-container";

/** Width of the page's vertical scrollbar; 0 when it has none (or it overlays the page). */
export function scrollbar_width() {
	return Math.max(0, window.innerWidth - document.documentElement.clientWidth);
}

/** What is in <body> now: the page an overlay opens over. */
export function page_behind() {
	return new Set(document.body.children);
}

/**
 * Send focus that reaches the page behind back to `panel`. Layers and
 * anything added to <body> after `background` was taken (menus, pickers
 * the overlay opens) keep it.
 * @returns {function} Stops the guard.
 */
export function guard_focus(panel, background = page_behind()) {
	const onfocusin = (e) => {
		if (panel.contains(e.target)) return;
		let top = e.target;
		while (top && top.parentElement !== document.body) top = top.parentElement;
		if (!top || !background.has(top) || top.matches(LAYERS)) return;
		panel.focus({ preventScroll: true });
	};
	document.addEventListener("focusin", onfocusin);
	return () => document.removeEventListener("focusin", onfocusin);
}

/** Keep Tab and Shift+Tab cycling through the visible controls in `panel`. */
export function trap_tab(panel, e) {
	const tabbables = [...panel.querySelectorAll(TABBABLE)].filter(
		(el) => el.offsetParent !== null
	);
	if (!tabbables.length) {
		e.preventDefault();
		return;
	}
	const first = tabbables[0];
	const last = tabbables[tabbables.length - 1];
	const active = document.activeElement;
	if (e.shiftKey && (active === first || active === panel)) {
		e.preventDefault();
		last.focus();
	} else if (!e.shiftKey && active === last) {
		e.preventDefault();
		first.focus();
	}
}

/**
 * Focus `target` once `root` closes, unless what closed it already moved
 * focus somewhere else (another overlay, a field on the page).
 */
export function return_focus(target, root) {
	const active = document.activeElement;
	if (!active || active === document.body || root.contains(active)) {
		target?.focus?.({ preventScroll: true });
	}
}
