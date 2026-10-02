import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} TabButtonOption
 * @property {string} [label] Button text. Rendered as text, never HTML. With `icon` set, the label becomes the accessible name only.
 * @property {*} [value] What get_value()/on_change report. Defaults to the label.
 * @property {string} [icon] Icon-only button (square); pass `label` too so it has a name.
 * @property {string} [icon_left] Leading accent icon next to a visible label.
 * @property {string} [icon_right] Trailing accent icon next to a visible label.
 * @property {boolean} [active] Fallback selection when no option matches `value`.
 * @property {boolean} [disabled]
 * @property {string} [title] Native tooltip.
 * @property {function} [onclick] Called with the click event, alongside the selection change.
 * @property {Element|JQuery|function} [prefix] Rich content before the icon/label — element or fn(option) returning one. Keep it non-interactive: it sits INSIDE a radio button, and nested focusables confuse keyboards and screen readers.
 * @property {Element|JQuery|function} [suffix] Rich content after the label (a count badge, say) — element or fn(option) returning one. Same rule: non-interactive only.
 * @property {string} [css_class] Extra classes on this button.
 */

/**
 * @typedef {Object} TabButtonsOpts
 * @property {TabButtonOption[]} options The choices.
 * @property {string} [label] Accessible name for the group ("Page size", "View") — screen readers announce it when focus enters. Not visible.
 * @property {*} [value] Initially selected value. Falls back to the option marked `active`, then the first enabled one.
 * @property {"subtle"|"ghost"|"underline"|"browser-tab"} [type="subtle"] subtle = gray rail with a raised pill; ghost = no rail, tinted pill; underline = looks like tabs; browser-tab = browser-style tabs on a rail.
 * @property {"sm"|"md"} [size="sm"]
 * @property {boolean} [vertical=false]
 * @property {"left"|"right"} [direction="left"] Which edge vertical browser-tabs attach to.
 * @property {function} [on_change] Called with (value, option) when the selection changes. Not called for the initial value.
 * @property {string} [css_class] Extra classes on the group.
 */

const TYPES = ["subtle", "ghost", "underline", "browser-tab"];
const SIZES = ["sm", "md"];
const DIRECTIONS = ["left", "right"];

/**
 * A segmented single-select — a group of pills where exactly one is
 * pressed (frappe-ui's TabButtons; the unitary piece is the Pill,
 * es-pill). For choices, not navigation: page-size selectors, calendar
 * day/week/month, view toggles. Works like a radio group: click selects,
 * and with focus inside, arrow keys move the selection (wrapping,
 * skipping disabled buttons).
 * @example
 * const period = new frappe.ui.TabButtons({
 *     options: [{ label: __("Day") }, { label: __("Week") }, { label: __("Month") }],
 *     value: __("Week"),
 *     on_change: (value) => this.set_period(value),
 * });
 * toolbar.append(period.$el);
 */
frappe.ui.TabButtons = class TabButtons {
	/** @param {TabButtonsOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.options = opts.options || [];
		this.type = validated(opts.type, TYPES, "type", "TabButtons") || "subtle";
		this.size = validated(opts.size, SIZES, "size", "TabButtons") || "sm";
		this.direction =
			validated(opts.direction, DIRECTIONS, "direction", "TabButtons") || "left";
		this.vertical = !!opts.vertical;

		this.el = document.createElement("div");
		this.el.className = ["es-tab-buttons", opts.css_class].filter(Boolean).join(" ");
		this.el.setAttribute("role", "radiogroup");
		// a radio group without a name is announced as just "radio group"
		if (opts.label) this.el.setAttribute("aria-label", opts.label);
		if (this.type !== "subtle") this.el.setAttribute("data-type", this.type);
		if (this.size !== "sm") this.el.setAttribute("data-size", this.size);
		if (this.vertical) {
			this.el.setAttribute("data-orientation", "vertical");
			if (this.type === "browser-tab" && this.direction === "right") {
				this.el.setAttribute("data-direction", "right");
			}
		}

		this.pills = this.options.map((option) => this.build_pill(option));
		this.pills.forEach((pill) => this.el.appendChild(pill.el));

		// initial selection: the given value, else the option marked
		// active, else the first enabled one; silent — on_change is only
		// for the user changing it
		const initial =
			("value" in opts ? this.find_by_value(opts.value) : null) ||
			this.pills.find((pill) => pill.option.active && !pill.option.disabled) ||
			this.pills.find((pill) => !pill.option.disabled);
		this.select(initial, { silent: true });

		// the radio-group keyboard pattern: one tab stop for the whole
		// group, arrows move AND select (wrapping, skipping disabled).
		// Left/Right follow the reading direction, so they flip in RTL.
		this.el.addEventListener("keydown", (e) => {
			const rtl = frappe.utils.is_rtl();
			const forward = rtl ? "ArrowLeft" : "ArrowRight";
			const backward = rtl ? "ArrowRight" : "ArrowLeft";
			const step =
				e.key === forward || e.key === "ArrowDown"
					? 1
					: e.key === backward || e.key === "ArrowUp"
					? -1
					: 0;
			if (!step) return;
			e.preventDefault();
			const enabled = this.pills.filter((pill) => !pill.option.disabled);
			if (!enabled.length) return;
			const current = Math.max(enabled.indexOf(this.selected), 0);
			const next = enabled[(current + step + enabled.length) % enabled.length];
			this.select(next);
			next.el.focus();
		});

		this.$el = $(this.el);
	}

	// Rich channel for prefix/suffix: an element or a function returning
	// one — same policy as everywhere else, never an HTML string.
	resolve_extra(extra, option) {
		if (typeof extra === "function") extra = extra(option);
		return (extra && $(extra)[0]) || null;
	}

	build_pill(option) {
		// always a real button: this is a radio choice, and a radio that
		// navigates somewhere is two controls pretending to be one
		// (frappe-ui's href/route form deliberately not ported)
		const el = document.createElement("button");
		el.type = "button";
		if (option.disabled) el.disabled = true;
		el.className = ["es-pill", option.css_class].filter(Boolean).join(" ");
		el.setAttribute("role", "radio");
		// the pill reads its own look off these (see tab_buttons.css)
		if (this.type === "underline") el.setAttribute("data-variant", "underline");
		if (this.type === "browser-tab") {
			el.setAttribute("data-variant", "browser-tab");
			// horizontal tabs always sit on the rail; vertical ones only
			// take the edge shape while selected (set in select())
			if (!this.vertical) el.setAttribute("data-tab-base", "default");
		}
		if (this.type === "ghost") el.setAttribute("data-active-style", "subtle");
		if (this.size !== "sm") el.setAttribute("data-size", this.size);

		const prefix = this.resolve_extra(option.prefix, option);
		prefix && el.appendChild(prefix);

		const main_icon = option.icon || option.icon_left;
		if (main_icon) {
			el.insertAdjacentHTML("beforeend", frappe.utils.icon(main_icon, "sm"));
		}
		if (option.icon) {
			// icon-only: square shape, the label becomes the accessible name
			el.setAttribute("data-icon-only", "");
			if (option.label) el.setAttribute("aria-label", option.label);
		} else if (option.label) {
			el.appendChild(document.createTextNode(option.label));
		}
		if (option.icon_right && !option.icon) {
			el.insertAdjacentHTML("beforeend", frappe.utils.icon(option.icon_right, "sm"));
		}

		const suffix = this.resolve_extra(option.suffix, option);
		suffix && el.appendChild(suffix);

		if (option.title) el.title = option.title;
		if (option.icon && !option.label && !option.title) {
			console.warn(
				`frappe.ui.TabButtons: icon-only button ("${option.icon}") needs a label or title`
			);
		}

		const pill = { el, option };
		el.addEventListener("click", (e) => {
			this.select(pill);
			option.onclick && option.onclick(e);
		});
		return pill;
	}

	find_by_value(value) {
		return this.pills.find((pill) => Object.is(this.value_of(pill), value));
	}

	value_of(pill) {
		return "value" in pill.option ? pill.option.value : pill.option.label;
	}

	select(pill, { silent = false } = {}) {
		if (!pill || pill === this.selected) return;
		this.selected = pill;
		for (const entry of this.pills) {
			const active = entry === pill;
			// data-state active|inactive is the Pill contract
			entry.el.setAttribute("data-state", active ? "active" : "inactive");
			entry.el.setAttribute("aria-checked", active ? "true" : "false");
			// one tab stop: only the selected button is tabbable
			entry.el.tabIndex = active ? 0 : -1;
			// vertical browser-tabs only wear the attached-edge shape while
			// selected (frappe-ui's browserTabBase behavior)
			if (this.type === "browser-tab" && this.vertical) {
				if (active) {
					entry.el.setAttribute("data-tab-base", this.direction);
				} else {
					entry.el.removeAttribute("data-tab-base");
				}
			}
		}
		if (!silent) {
			this.opts.on_change && this.opts.on_change(this.value_of(pill), pill.option);
		}
	}

	get_value() {
		return this.selected ? this.value_of(this.selected) : null;
	}

	/** Change the selection from code. Fires on_change (pass silent to not). */
	set_value(value, { silent = false } = {}) {
		const pill = this.find_by_value(value);
		if (!pill) {
			console.warn(`frappe.ui.TabButtons: no option with value "${value}"`);
			return;
		}
		this.select(pill, { silent });
	}
};

/**
 * Convenience form: build the group and get the container element back, so
 * it chains inside append(...) calls. The instance is on
 * `.data("es-tab-buttons")` when you need get_value/set_value.
 * @param {TabButtonsOpts} opts
 * @returns {JQuery}
 * @example toolbar.append(frappe.ui.tab_buttons({
 *     options: [{ label: "20" }, { label: "100" }, { label: "500" }],
 *     on_change: (value) => this.set_page_length(value),
 * }));
 */
frappe.ui.tab_buttons = function (opts = {}) {
	const tab_buttons = new frappe.ui.TabButtons(opts);
	tab_buttons.$el.data("es-tab-buttons", tab_buttons);
	return tab_buttons.$el;
};

export default frappe.ui.tab_buttons;
