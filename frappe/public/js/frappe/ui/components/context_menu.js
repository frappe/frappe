import { MenuTree } from "./menu.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ContextMenuOpts
 * @property {Element|JQuery} target Right-clicking anywhere in this element opens the menu at the cursor.
 * @property {Array|function} options Same menu items/groups as frappe.ui.Dropdown. A function is called fresh on every open — handy for menus that depend on which row was clicked — and may return a Promise of the items (the menu opens with a loading row and fills in when it settles).
 * @property {string} [empty_text] Shown when no items are visible.
 * @property {function} [on_open] Called with the contextmenu event, before the menu renders — set per-row options here.
 * @property {function} [on_close] Called with the reason: "activate" | "escape" | "outside" | "tab" | "owner".
 */

/**
 * Right-click menu for a surface (a list row, a card, a canvas). Same
 * options as frappe.ui.Dropdown; the page can't scroll while it's open,
 * same as native context menus. While open, the target carries
 * data-state="open" — style that to highlight the card/row being acted on.
 * @example
 * new frappe.ui.ContextMenu({
 *     target: row_el,
 *     options: () => this.get_row_actions(),
 * });
 */
frappe.ui.ContextMenu = class ContextMenu {
	/** @param {ContextMenuOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.options = opts.options || [];
		this.menu = null;

		// resolve first, then check — a selector that matches nothing or an
		// empty jQuery set is truthy but has no [0], so guarding opts.target
		// alone would still crash on the addEventListener below
		this.target_el = opts.target ? $(opts.target)[0] : null;
		if (!this.target_el) {
			console.warn("frappe.ui.ContextMenu: a target element is required");
			return;
		}
		this.oncontextmenu = (e) => {
			e.preventDefault();
			this.opts.on_open && this.opts.on_open(e);
			this.open_at(e.clientX, e.clientY);
		};
		this.target_el.addEventListener("contextmenu", this.oncontextmenu);
	}

	get is_open() {
		return !!this.menu;
	}

	/** Open at a viewport point — the contextmenu handler calls this with the cursor. */
	open_at(x, y) {
		if (!this.target_el) return;
		this.close("owner");

		// mark the surface while its menu is open — apps style this to
		// highlight the card/row being acted on (same data-state="open" a
		// radix/reka trigger gets). Whatever value was there before comes
		// back when the menu closes.
		this.previous_state = this.target_el.getAttribute("data-state");
		this.target_el.setAttribute("data-state", "open");

		// remember where focus was so a keyboard close can put it back — a
		// context menu has no trigger button to return to
		const return_focus = document.activeElement;

		// a zero-size anchor: the menu hangs off the pointer position
		const anchor = { top: y, bottom: y, left: x, right: x, width: 0, height: 0 };
		this.menu = new MenuTree({
			options: this.options,
			empty_text: this.opts.empty_text,
			component: "ContextMenu",
			anchor: () => anchor,
			lock_scroll: true,
			on_close: (reason) => {
				if (this.previous_state == null) {
					this.target_el.removeAttribute("data-state");
				} else {
					this.target_el.setAttribute("data-state", this.previous_state);
				}
				// don't leave focus stranded on the removed panel — send it
				// back where it was (Escape/activate), and for Tab this runs
				// before the browser's Tab so it continues from there
				if (
					(reason === "escape" || reason === "activate" || reason === "tab") &&
					return_focus &&
					return_focus.isConnected
				) {
					return_focus.focus({ preventScroll: true });
				}
				this.menu = null;
				this.opts.on_close && this.opts.on_close(reason);
			},
		});
		this.menu.open({ side: "bottom", align: "start", motion: "animated", focus: null });
	}

	close(reason = "owner") {
		this.menu && this.menu.close(reason);
	}

	/** Swap the menu contents; takes effect on the next open. */
	set_options(options) {
		this.options = options || [];
	}

	destroy() {
		this.close("owner");
		if (this.target_el) {
			this.target_el.removeEventListener("contextmenu", this.oncontextmenu);
		}
	}
};

export default frappe.ui.ContextMenu;
