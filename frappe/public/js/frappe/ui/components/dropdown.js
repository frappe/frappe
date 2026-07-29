import { MenuTree } from "./menu.js";
import { SIDES, ALIGNS } from "./position.js";
import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} DropdownOpts
 * @property {Element|JQuery} [trigger] An existing element that opens the menu. Omit to have one made from `button`.
 * @property {Object} [button] Options for the generated frappe.ui.button trigger (ignored when `trigger` is passed).
 * @property {Array|function} options Menu items and { group, options } sections — see MenuItem in menu.js. A function is called fresh on every open, and may return a Promise of the items — the menu opens with a loading row and fills in when it settles. Individual items can lazy-load the same way via a function `submenu`.
 * @property {"top"|"right"|"bottom"|"left"} [side="bottom"] Which side of the trigger the menu opens on.
 * @property {"start"|"center"|"end"} [align="start"] How the menu lines up along that side.
 * @property {number} [offset=4] Gap between trigger and menu, in px.
 * @property {string} [empty_text] Shown when no items are visible.
 * @property {function} [on_open]
 * @property {function} [on_close] Called with the reason: "activate" | "escape" | "outside" | "tab" | "owner".
 */

// TODO: switch/checkbox rows (frappe-ui DropdownSwitchOption) — needs the
// es-switch control first; goes here + menu.js when a consumer needs it.

/**
 * Action menu on a trigger button — the espresso replacement for bootstrap's
 * data-toggle="dropdown". Follows the menu-button pattern: ArrowDown/Enter/
 * Space open it (keyboard opens skip the animation and focus the first row),
 * arrows navigate, ArrowRight/Left walk submenus, typing jumps to a matching
 * row, holding Alt underlines each row's letter (Alt+letter activates it),
 * and Escape returns to the trigger.
 * @example
 * new frappe.ui.Dropdown({
 *     trigger: this.$el.find(".menu-btn"),
 *     options: [
 *         { label: __("Edit"), icon: "pen", onclick: () => this.edit() },
 *         { label: __("Delete"), icon: "trash-2", theme: "red", onclick: () => this.delete() },
 *     ],
 * });
 */
frappe.ui.Dropdown = class Dropdown {
	/** @param {DropdownOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.options = opts.options || [];
		this.side = validated(opts.side, SIDES, "side", "Dropdown") || "bottom";
		this.align = validated(opts.align, ALIGNS, "align", "Dropdown") || "start";
		this.offset = opts.offset == null ? 4 : opts.offset;
		this.menu = null;

		// the trigger button owns the click that opens the menu, so its own
		// onclick would double up — drop it (the menu's action lives on the
		// item rows, not the trigger)
		const button_opts = { label: __("Options"), ...opts.button };
		if (button_opts.onclick) {
			console.warn(
				"frappe.ui.Dropdown: button.onclick is ignored — put actions on the items"
			);
			delete button_opts.onclick;
		}
		this.$trigger = opts.trigger ? $(opts.trigger) : frappe.ui.button(button_opts);
		this.trigger_el = this.$trigger[0];

		if (!this.trigger_el) {
			console.warn("frappe.ui.Dropdown: trigger element not found");
			return;
		}

		this.trigger_el.setAttribute("aria-haspopup", "menu");
		this.trigger_el.setAttribute("aria-expanded", "false");

		// a click right after a pointerdown is a mouse/touch open (animated);
		// anything else (Enter/Space) is a keyboard open (instant, per the
		// frappe-ui motion spec)
		this.last_pointerdown = 0;
		this.onpointerdown = () => (this.last_pointerdown = Date.now());
		this.onclick = (e) => {
			e.preventDefault();
			if (this.is_open) {
				this.close("owner");
			} else if (Date.now() - this.last_pointerdown < 300) {
				this.open({ motion: "animated", focus: null });
			} else {
				// no recent pointerdown means this "click" came from Enter
				// or Space on the focused trigger
				this.open({ motion: "instant", focus: "first" });
			}
		};
		// the menu-button pattern: ArrowDown opens onto the first row,
		// ArrowUp opens onto the last (Enter/Space arrive as clicks above)
		this.onkeydown = (e) => {
			if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
			e.preventDefault();
			if (!this.is_open) {
				this.open({ motion: "instant", focus: e.key === "ArrowDown" ? "first" : "last" });
			}
		};
		this.trigger_el.addEventListener("pointerdown", this.onpointerdown);
		this.trigger_el.addEventListener("click", this.onclick);
		this.trigger_el.addEventListener("keydown", this.onkeydown);
	}

	get is_open() {
		return !!this.menu;
	}

	open({ motion = "animated", focus = null } = {}) {
		if (this.menu || !this.trigger_el) return;
		this.menu = new MenuTree({
			options: this.options,
			empty_text: this.opts.empty_text,
			component: "Dropdown",
			anchor: () => this.trigger_el.getBoundingClientRect(),
			// clicks on the trigger must not count as "clicked outside" —
			// the toggle above owns them (otherwise a click on the open
			// trigger would close the menu and instantly reopen it)
			ignore: [this.trigger_el],
			on_close: (reason) => {
				this.menu = null;
				this.trigger_el.setAttribute("aria-expanded", "false");
				// bring focus back to the trigger on every keyboard close —
				// Escape/activate land on it, and for Tab this runs before the
				// browser's own Tab, so focus moves on from the trigger (its
				// real place in the page) instead of jumping to the body-level
				// panel's neighbours. A click elsewhere already moved focus.
				if (reason === "escape" || reason === "activate" || reason === "tab") {
					this.trigger_el.focus({ preventScroll: true });
				}
				this.opts.on_close && this.opts.on_close(reason);
			},
		});
		this.menu.open({ side: this.side, align: this.align, offset: this.offset, motion, focus });
		this.trigger_el.setAttribute("aria-expanded", "true");
		this.opts.on_open && this.opts.on_open();
	}

	close(reason = "owner") {
		this.menu && this.menu.close(reason);
	}

	toggle() {
		this.is_open ? this.close("owner") : this.open();
	}

	/** Swap the menu contents; takes effect on the next open. */
	set_options(options) {
		this.options = options || [];
	}

	destroy() {
		this.close("owner");
		if (!this.trigger_el) return;
		this.trigger_el.removeEventListener("pointerdown", this.onpointerdown);
		this.trigger_el.removeEventListener("click", this.onclick);
		this.trigger_el.removeEventListener("keydown", this.onkeydown);
	}
};

/**
 * Convenience form: makes the trigger button and wires the dropdown in one
 * call. Returns the trigger element (append it wherever); the instance is
 * on `.data("es-dropdown")` when you need open/close/set_options.
 * @param {DropdownOpts} opts
 * @returns {JQuery}
 * @example page_actions.append(frappe.ui.dropdown({
 *     button: { label: __("Actions") },
 *     options: [{ label: __("Duplicate"), onclick: () => {} }],
 * }));
 */
frappe.ui.dropdown = function (opts = {}) {
	const dropdown = new frappe.ui.Dropdown(opts);
	dropdown.$trigger.data("es-dropdown", dropdown);
	return dropdown.$trigger;
};

export default frappe.ui.dropdown;
