import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} TabOpts
 * @property {string} label Tab text. Rendered as text, never HTML.
 * @property {string} [icon] Lucide icon name shown before the label.
 * @property {Element|JQuery|function|string} [content] The panel body. An element (or a function returning one — called once, on first activation) is the rich channel; a plain string renders as text, never HTML.
 * @property {boolean} [disabled] Inert tab, skipped by keyboard navigation.
 */

/**
 * @typedef {Object} TabsOpts
 * @property {TabOpts[]} tabs
 * @property {number} [active=0] Index of the initially active tab.
 * @property {boolean} [vertical=false] Tab bar on the side instead of on top.
 * @property {function} [on_change] Called with (index, tab) when the active tab changes. Not called for the initial tab.
 * @property {string} [css_class] Extra classes on the root.
 */

// TODO: subtle/outline pill-look variants (Raven has them) — skipped until a
// consumer needs them; that look is Pills' job today.

let id_counter = 0;

/**
 * Underline tab bar with panels — for switching between views of the same
 * thing (a value picker wants frappe.ui.Pills instead). Follows the
 * standard tabs pattern: one tab stop for the bar, ArrowLeft/Right (Up/
 * Down when vertical) move between tabs and activate as they go, Home/End
 * jump. A tab's content function runs once, on first activation, so heavy
 * panels don't render until someone looks at them.
 * @example
 * const tabs = new frappe.ui.Tabs({
 *     tabs: [
 *         { label: __("Details"), content: () => this.render_details() },
 *         { label: __("Activity"), icon: "history", content: () => this.render_activity() },
 *     ],
 *     on_change: (i) => this.save_last_tab(i),
 * });
 * body.append(tabs.$el);
 */
frappe.ui.Tabs = class Tabs {
	/** @param {TabsOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.vertical = !!opts.vertical;
		this.active = null;

		const uid = ++id_counter;
		this.el = document.createElement("div");
		this.el.className = ["es-tabs", opts.css_class].filter(Boolean).join(" ");
		this.el.setAttribute("data-orientation", this.vertical ? "vertical" : "horizontal");

		this.list = document.createElement("div");
		this.list.className = "es-tabs__list";
		this.list.setAttribute("role", "tablist");
		this.list.setAttribute("aria-orientation", this.vertical ? "vertical" : "horizontal");
		this.el.appendChild(this.list);

		this.tabs = (opts.tabs || []).map((tab, i) => {
			const button = document.createElement("button");
			button.type = "button";
			button.className = "es-tabs__tab";
			button.id = `es-tab-${uid}-${i}`;
			button.setAttribute("role", "tab");
			if (tab.disabled) button.disabled = true;
			if (tab.icon) {
				button.insertAdjacentHTML("beforeend", frappe.utils.icon(tab.icon, "sm"));
			}
			button.appendChild(document.createTextNode(tab.label || ""));
			this.list.appendChild(button);

			const panel = document.createElement("div");
			panel.className = "es-tabs__panel";
			panel.id = `es-tabpanel-${uid}-${i}`;
			panel.setAttribute("role", "tabpanel");
			panel.setAttribute("aria-labelledby", button.id);
			// panels are in the tab order so keyboard users can get from
			// the bar into the content without hunting for a focusable
			panel.tabIndex = 0;
			button.setAttribute("aria-controls", panel.id);
			this.el.appendChild(panel);

			const entry = { tab, button, panel, rendered: false };
			button.addEventListener("click", () => this.set_active(i));
			return entry;
		});

		// the moving bar under the active tab
		this.indicator = document.createElement("span");
		this.indicator.className = "es-tabs__indicator";
		this.indicator.setAttribute("aria-hidden", "true");
		this.list.appendChild(this.indicator);

		// the tabs keyboard pattern: arrows move focus AND activate
		// (automatic activation, same as radix), wrapping and skipping
		// disabled tabs; Home/End jump to the ends
		this.list.addEventListener("keydown", (e) => {
			// horizontal arrows follow the reading direction (flip in RTL)
			const rtl = !this.vertical && frappe.utils.is_rtl();
			const forward = this.vertical ? "ArrowDown" : rtl ? "ArrowLeft" : "ArrowRight";
			const backward = this.vertical ? "ArrowUp" : rtl ? "ArrowRight" : "ArrowLeft";
			const enabled = this.tabs.filter((entry) => !entry.tab.disabled);
			if (!enabled.length) return;

			let target = null;
			if (e.key === forward || e.key === backward) {
				const step = e.key === forward ? 1 : -1;
				const current = Math.max(
					enabled.findIndex((entry) => entry === this.tabs[this.active]),
					0
				);
				target = enabled[(current + step + enabled.length) % enabled.length];
			} else if (e.key === "Home") {
				target = enabled[0];
			} else if (e.key === "End") {
				target = enabled[enabled.length - 1];
			}
			if (!target) return;
			e.preventDefault();
			this.set_active(this.tabs.indexOf(target));
			target.button.focus();
		});

		// the indicator's position depends on layout: it can't be measured
		// until the element is actually in the page, and it moves when text
		// or the container changes size. A ResizeObserver on the list
		// covers all of that (first layout after append included).
		if (window.ResizeObserver) {
			this.observer = new ResizeObserver(() => this.position_indicator());
			this.observer.observe(this.list);
		} else {
			this.onresize = () => this.position_indicator();
			window.addEventListener("resize", this.onresize);
		}

		// asked-for tab, unless it's disabled — then the first usable one
		const requested = this.tabs[opts.active || 0];
		const initial =
			requested && !requested.tab.disabled
				? requested
				: this.tabs.find((entry) => !entry.tab.disabled);
		initial && this.set_active(this.tabs.indexOf(initial), { silent: true });
		this.$el = $(this.el);
	}

	// The panel body. Elements and element-returning functions are the
	// rich channel; strings become text nodes, never markup. Functions run
	// once, on first activation.
	render_panel(entry) {
		if (entry.rendered) return;
		entry.rendered = true;
		let content = entry.tab.content;
		if (typeof content === "function") content = content(this);
		if (typeof content === "string") {
			entry.panel.textContent = content;
		} else if (content) {
			const el = $(content)[0];
			el && entry.panel.appendChild(el);
		}
	}

	set_active(index, { silent = false } = {}) {
		const entry = this.tabs[index];
		if (!entry || entry.tab.disabled || index === this.active) return;
		this.active = index;

		this.render_panel(entry);
		for (const other of this.tabs) {
			const active = other === entry;
			other.button.setAttribute("data-state", active ? "active" : "inactive");
			other.button.setAttribute("aria-selected", active ? "true" : "false");
			// one tab stop for the whole bar
			other.button.tabIndex = active ? 0 : -1;
			other.panel.setAttribute("data-state", active ? "active" : "inactive");
		}
		this.position_indicator();

		if (!silent) {
			this.opts.on_change && this.opts.on_change(index, entry.tab);
		}
	}

	get_active() {
		return this.active;
	}

	// Slide the bar under the active tab: measure where the tab sits in
	// the list and hand the numbers to CSS (which owns the animation).
	position_indicator() {
		const entry = this.tabs[this.active];
		if (!entry) return;
		const offset = this.vertical ? entry.button.offsetTop : entry.button.offsetLeft;
		const size = this.vertical ? entry.button.offsetHeight : entry.button.offsetWidth;
		if (!size) return; // not laid out yet — the observer will call again

		// the very first placement must not animate, or the bar visibly
		// slides in from the list's left edge on mount
		if (!this.indicator_placed) {
			this.indicator_placed = true;
			this.indicator.style.transition = "none";
			requestAnimationFrame(() => (this.indicator.style.transition = ""));
		}
		this.indicator.style.setProperty("--es-tabs-indicator-x", `${offset}px`);
		this.indicator.style.setProperty("--es-tabs-indicator-w", `${size}px`);
	}

	destroy() {
		this.observer && this.observer.disconnect();
		this.onresize && window.removeEventListener("resize", this.onresize);
		this.el.remove();
	}
};

/**
 * Convenience form: build the tabs and get the root element back, so it
 * chains inside append(...) calls. The instance is on `.data("es-tabs")`
 * when you need set_active/get_active.
 * @param {TabsOpts} opts
 * @returns {JQuery}
 * @example body.append(frappe.ui.tabs({ tabs: [...] }));
 */
frappe.ui.tabs = function (opts = {}) {
	const tabs = new frappe.ui.Tabs(opts);
	tabs.$el.data("es-tabs", tabs);
	return tabs.$el;
};

export default frappe.ui.tabs;
