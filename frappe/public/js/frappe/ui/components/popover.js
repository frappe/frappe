import { place, SIDES, ALIGNS } from "./position.js";
import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} PopoverOpts
 * @property {Element|JQuery} [trigger] An existing element that opens the panel. Omit to have one made from `button`.
 * @property {Object} [button] Options for the generated frappe.ui.button trigger (ignored when `trigger` is passed).
 * @property {Element|JQuery|function|string} content The panel body. An element (or a function returning one, called fresh on every open) is the rich channel; a plain string renders as text, never HTML.
 * @property {"top"|"right"|"bottom"|"left"} [side="bottom"] Which side of the trigger the panel opens on.
 * @property {"start"|"center"|"end"} [align="start"] How the panel lines up along that side.
 * @property {number} [offset=4] Gap between trigger and panel, in px.
 * @property {string} [css_class] Extra classes on the panel (e.g. to override the default width).
 * @property {function} [on_open] Called after the panel is placed and focused.
 * @property {function} [on_close] Called with the reason: "escape" | "outside" | "tab" | "blur" | "owner".
 */

// TODO: match_trigger_width (frappe-ui's matchTargetWidth) — panel min-width
// follows the trigger; add when an autocomplete-style consumer needs it.
// frappe-ui's hover-trigger mode is deliberately not here: that's the Hover
// Card component's job.

const EXIT_MS = 100; // keep in sync with es-popover-out in popover.css

// what Tab can land on, for the close-on-tab-out bookkeeping below
const TABBABLE =
	'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';

let id_counter = 0;

/**
 * A small non-modal panel anchored to a trigger — real interactive content
 * (inputs, buttons) without blocking the page. Follows the radix popover
 * pattern: click toggles, focus moves into the panel on open and back to
 * the trigger on close, Escape / clicking outside / tabbing out close it.
 * The rest of the page stays live the whole time — that's the difference
 * from a dialog.
 * @example
 * new frappe.ui.Popover({
 *     trigger: this.$el.find(".filter-btn"),
 *     content: () => this.build_filter_form(),
 *     on_close: () => this.apply_filters(),
 * });
 */
frappe.ui.Popover = class Popover {
	/** @param {PopoverOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.side = validated(opts.side, SIDES, "side", "Popover") || "bottom";
		this.align = validated(opts.align, ALIGNS, "align", "Popover") || "start";
		this.offset = opts.offset == null ? 4 : opts.offset;
		this.panel = null;

		// the trigger's click is the toggle, so its own onclick would double
		// up — drop it (same rule as Dropdown)
		const button_opts = { label: __("Open"), ...opts.button };
		if (button_opts.onclick) {
			console.warn(
				"frappe.ui.Popover: button.onclick is ignored — the trigger's click toggles the panel"
			);
			delete button_opts.onclick;
		}
		this.$trigger = opts.trigger ? $(opts.trigger) : frappe.ui.button(button_opts);
		this.trigger_el = this.$trigger[0];

		if (!this.trigger_el) {
			console.warn("frappe.ui.Popover: trigger element not found");
			return;
		}

		this.trigger_el.setAttribute("aria-haspopup", "dialog");
		this.trigger_el.setAttribute("aria-expanded", "false");

		this.ontriggerclick = (e) => {
			e.preventDefault();
			this.toggle();
		};
		this.trigger_el.addEventListener("click", this.ontriggerclick);
	}

	get is_open() {
		return !!this.panel;
	}

	// The panel body. Elements and element-returning functions are the rich
	// channel; strings become text nodes so they can never smuggle markup.
	resolve_content() {
		let content = this.opts.content;
		if (typeof content === "function") content = content(this);
		if (typeof content === "string") {
			const p = document.createElement("div");
			p.textContent = content;
			return p;
		}
		const el = content && $(content)[0];
		if (!el) {
			console.warn("frappe.ui.Popover: no content to show");
			return null;
		}
		return el;
	}

	open() {
		if (this.panel || !this.trigger_el) return;
		const content = this.resolve_content();
		if (!content) return;

		const panel = document.createElement("div");
		panel.className = ["es-popover", this.opts.css_class].filter(Boolean).join(" ");
		panel.setAttribute("role", "dialog");
		// tabindex -1 so the panel itself can hold focus: keyboard users
		// arrive inside it and Tab reaches its controls next, and clicks on
		// its empty areas keep focus inside instead of dropping it on <body>
		panel.setAttribute("tabindex", "-1");
		panel.id = `es-popover-${++id_counter}`;
		panel.appendChild(content);

		// same drill as menus: into <body> first (place() needs the real
		// size), position, then data-state starts the enter animation
		document.body.appendChild(panel);
		place(panel, this.trigger_el.getBoundingClientRect(), this.side, this.align, this.offset);
		panel.setAttribute("data-state", "open");

		this.trigger_el.setAttribute("aria-expanded", "true");
		this.trigger_el.setAttribute("aria-controls", panel.id);
		this.panel = panel;

		// focus the panel, not its first control — the radix default. A
		// screen reader announces the dialog, and Tab reaches the controls;
		// auto-focusing an input would start typing-mode unannounced.
		panel.focus({ preventScroll: true });

		// Escape and Tab bookkeeping live on the panel — focus is inside it
		// (tabindex -1 keeps it there), so there's no need for a global key
		// listener that could fight other components' handlers
		this.onkeydown = (e) => {
			if (e.key === "Escape") {
				e.stopPropagation();
				this.close("escape");
			} else if (e.key === "Tab") {
				this.handle_tab(e);
			}
		};
		// a click anywhere that isn't the panel or the trigger closes it
		// (capture: before the click can be swallowed by stopPropagation)
		this.onpointerdown = (e) => {
			if (panel.contains(e.target) || this.trigger_el.contains(e.target)) return;
			this.close("outside");
		};
		// focus escaping the panel by any other route (programmatic, a
		// screen reader jump) also closes it — the radix "focus outside" rule
		this.onfocusin = (e) => {
			if (panel.contains(e.target) || this.trigger_el.contains(e.target)) return;
			this.close("blur");
		};
		// the trigger can move (window resize, a scrolling container) — keep
		// the panel attached to it
		this.onreposition = () => {
			place(
				panel,
				this.trigger_el.getBoundingClientRect(),
				this.side,
				this.align,
				this.offset
			);
		};
		panel.addEventListener("keydown", this.onkeydown);
		document.addEventListener("pointerdown", this.onpointerdown, { capture: true });
		document.addEventListener("focusin", this.onfocusin);
		window.addEventListener("resize", this.onreposition);
		document.addEventListener("scroll", this.onreposition, { capture: true, passive: true });

		this.opts.on_open && this.opts.on_open(this);
	}

	// Tab is not trapped (this is not a modal): tabbing past the panel's
	// last control closes it and puts focus back on the trigger, so the
	// browser's own Tab continues from the trigger's real place in the page
	// instead of the body-level panel's neighbours. Shift+Tab from the
	// first control mirrors that.
	handle_tab(e) {
		const tabbables = [...this.panel.querySelectorAll(TABBABLE)];
		const first = tabbables[0];
		const last = tabbables[tabbables.length - 1];
		const active = document.activeElement;

		if (!tabbables.length || (!e.shiftKey && active === last)) {
			this.close("tab"); // close() refocuses the trigger; Tab moves on from there
		} else if (e.shiftKey && (active === first || active === this.panel)) {
			e.preventDefault(); // land exactly on the trigger, not past it
			this.close("tab");
		}
	}

	close(reason = "owner") {
		if (!this.panel) return;
		const panel = this.panel;
		this.panel = null;

		panel.removeEventListener("keydown", this.onkeydown);
		document.removeEventListener("pointerdown", this.onpointerdown, { capture: true });
		document.removeEventListener("focusin", this.onfocusin);
		window.removeEventListener("resize", this.onreposition);
		document.removeEventListener("scroll", this.onreposition, { capture: true });

		this.trigger_el.setAttribute("aria-expanded", "false");
		this.trigger_el.removeAttribute("aria-controls");

		// keyboard closes return focus to the trigger; a click elsewhere
		// already moved focus and shouldn't have it stolen back
		if (reason === "escape" || reason === "tab") {
			this.trigger_el.focus({ preventScroll: true });
		}

		// let the exit animation play, then drop the node
		panel.setAttribute("data-state", "closed");
		setTimeout(() => panel.remove(), EXIT_MS + 50);

		this.opts.on_close && this.opts.on_close(reason);
	}

	toggle() {
		this.is_open ? this.close("owner") : this.open();
	}

	destroy() {
		this.close("owner");
		if (!this.trigger_el) return;
		this.trigger_el.removeEventListener("click", this.ontriggerclick);
	}
};

/**
 * Convenience form: makes the trigger button and wires the popover in one
 * call. Returns the trigger element (append it wherever); the instance is
 * on `.data("es-popover")` when you need open/close.
 * @param {PopoverOpts} opts
 * @returns {JQuery}
 * @example toolbar.append(frappe.ui.popover({
 *     button: { label: __("Filter"), icon: "filter" },
 *     content: () => build_filter_form(),
 * }));
 */
frappe.ui.popover = function (opts = {}) {
	const popover = new frappe.ui.Popover(opts);
	popover.$trigger.data("es-popover", popover);
	return popover.$trigger;
};

export default frappe.ui.popover;
