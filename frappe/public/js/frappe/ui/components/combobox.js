import { place } from "./position.js";
import { is_thenable, is_group, icon_html } from "./utils.js";
import { normalize_options as normalize_menu_options } from "./menu.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ComboboxOption
 * @property {string} label Row text, never HTML.
 * @property {string} value Returned by get_value().
 * @property {string} [description] Muted second line.
 * @property {string} [icon] Lucide icon name.
 * @property {string} [image] Avatar image URL.
 * @property {boolean} [avatar] Initial-letter avatar without an image.
 * @property {{label: string, theme?: string}} [badge] Badge after the label.
 * @property {boolean} [disabled] Inert row.
 */

/**
 * @typedef {Object} ComboboxGroup
 * @property {string} group Section heading.
 * @property {ComboboxOption[]} options Rows in the section.
 */

/**
 * @typedef {Object} ComboboxCustomOption
 * @property {"custom"} type
 * @property {string|function} label Row text, or a function of { query }.
 * @property {string} [icon] Lucide icon name.
 * @property {function} onclick Called with { query, combobox }; closes the panel.
 * @property {function} [condition] Called with { query }; false hides the row.
 */

/**
 * @typedef {Object} ComboboxOpts
 * @property {Array|function} options Rows, or a function of (query, { start }) returning rows, a Promise, or { rows, has_more }.
 * @property {number} [page_size] Rows per page for a function `options`.
 * @property {string} [value] Initial value.
 * @property {string} [placeholder="Select"] Trigger text when empty.
 * @property {string} [search_placeholder="Search..."] Search row placeholder.
 * @property {boolean} [filterable=true] Filter rows on the client.
 * @property {boolean} [hide_search=false] No search row.
 * @property {boolean} [clearable=true] Clearing allowed (Backspace / Delete, and the × button).
 * @property {boolean} [clear_button=true] Show the × button.
 * @property {boolean} [disabled=false]
 * @property {string[]|string|function} [filters] Filter chips under the list.
 * @property {ComboboxCustomOption[]} [footer] Custom rows under the list.
 * @property {boolean} [chevron=true] Show the trigger chevron.
 * @property {boolean} [value_input=false] Render the value as an <input> (`input_el`).
 * @property {boolean} [open_on_focus=false] With `value_input`: focus opens the panel.
 * @property {boolean} [arrow_keys_open=true] Arrow keys open the closed trigger.
 * @property {Array<{icon: string, title: string, href?: string, css_class?: string, onclick?: function, shortcut?: "ctrl+enter"}>} [actions] Extra trigger buttons (`action_els`).
 * @property {function} [before_open] Called with the instance before the panel is built.
 * @property {function} [on_change] Called with (value, option).
 * @property {function} [on_open]
 * @property {function} [on_close] Called with "select" | "escape" | "outside" | "tab" | "owner".
 */

const EXIT_MS = 140; // keep in sync with es-menu-out in menu.css
const DEBOUNCE_MS = 300;
const PANEL_OFFSET = 4;
// floor for the panel width: a grid cell can be 80px wide
const MIN_PANEL_WIDTH = 240;
const MIN_PANEL_HEIGHT = 160; // below this the panel may overlap the trigger
const NARROW_PANEL_WIDTH = 320; // below this the filter band drops its label
const VIEWPORT_PAD = 8;
const LOAD_MORE_THRESHOLD = 48;
// pages in a row that add no new row before paging stops (a source ignoring
// `start`); a map hook may legitimately empty a page or two
const MAX_EMPTY_PAGES = 3;
// focus this soon after a pointer press came from that press
const POINTER_FOCUS_MS = 500;
// a click this soon after pointerdown is a mouse open; later, a keyboard one
const CLICK_AFTER_PRESS_MS = 300;
let last_pointerdown_at = 0;
document.addEventListener(
	"pointerdown",
	(e) => {
		// a press inside a panel picks a row; it isn't a press on a field
		if (e.target.closest && e.target.closest(".es-combobox__panel")) return;
		last_pointerdown_at = Date.now();
	},
	{ capture: true, passive: true }
);
// a key press means the next focus is the keyboard's
document.addEventListener("keydown", () => (last_pointerdown_at = 0), {
	capture: true,
	passive: true,
});
const COMPONENT = "Combobox";

let id_counter = 0;

function is_custom(entry) {
	return entry && typeof entry === "object" && entry.type === "custom";
}

function normalize_option(entry) {
	if (entry == null) return null;
	if (typeof entry !== "object") {
		const text = String(entry);
		return { label: text, value: text };
	}
	const value = entry.value == null ? entry.label : entry.value;
	return { ...entry, label: entry.label == null ? String(value) : String(entry.label), value };
}

// custom rows are set aside: they never take part in filtering
function normalize_options(options) {
	const entries = (options || []).filter((entry) => entry != null);
	const rows = entries
		.filter((entry) => !is_custom(entry))
		.map((entry) =>
			is_group(entry)
				? { ...entry, options: entry.options.map(normalize_option).filter(Boolean) }
				: normalize_option(entry)
		);
	return { groups: normalize_menu_options(rows), custom: entries.filter(is_custom) };
}

function merge_normalized(base, extra) {
	const seen = new Set(base.groups.flatMap((group) => group.options.map((o) => o.value)));
	const added = [];
	for (const group of extra.groups) {
		const options = group.options.filter((o) => !seen.has(o.value));
		if (!options.length) continue;
		options.forEach((o) => seen.add(o.value));
		added.push({ ...group, options });
		const last = base.groups[base.groups.length - 1];
		const target = group.group
			? base.groups.find((g) => g.group === group.group)
			: last && !last.group && last;
		if (target) target.options.push(...options);
		else base.groups.push({ ...group, options });
	}
	base.custom.push(...extra.custom);
	return added;
}

function unpack(value) {
	if (value && !Array.isArray(value) && typeof value === "object" && "rows" in value) {
		return { rows: value.rows || [], has_more: value.has_more };
	}
	return { rows: value || [], has_more: undefined };
}

function find_in(groups, value) {
	for (const group of groups) {
		const hit = group.options.find((o) => o.value === value);
		if (hit) return hit;
	}
	return null;
}

function matches(option, query) {
	if (!query) return true;
	const q = query.toLowerCase();
	return [option.label, option.description, option.value].some(
		(text) => text != null && String(text).toLowerCase().includes(q)
	);
}

// text nodes only, never innerHTML
function fill_label(el, text, query) {
	const index = query ? text.toLowerCase().indexOf(query.toLowerCase()) : -1;
	if (index === -1) {
		el.textContent = text;
		return;
	}
	const mark = document.createElement("span");
	mark.className = "es-combobox__match text-ink-gray-9";
	mark.textContent = text.slice(index, index + query.length);
	el.append(
		document.createTextNode(text.slice(0, index)),
		mark,
		document.createTextNode(text.slice(index + query.length))
	);
}

function prefix_html(option, size) {
	if (option.image || option.avatar) {
		return frappe.ui.avatar.html({ image: option.image, label: option.label, size });
	}
	if (option.icon) return icon_html(option.icon, "", COMPONENT);
	return "";
}

function needs_icon_space(options) {
	return options.some((o) => o.icon || o.image || o.avatar);
}

/**
 * Pick one value from a searchable list: a trigger plus an .es-menu panel.
 * @example
 * new frappe.ui.Combobox({
 *     options: ["Open", "Working", "Closed"],
 *     on_change: (value) => this.set_status(value),
 * });
 */
frappe.ui.Combobox = class Combobox {
	/** @param {ComboboxOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.filterable = opts.filterable !== false;
		this.clearable = opts.clearable !== false;
		this.options = opts.options || [];
		this.value = opts.value == null ? null : opts.value;
		this.selected = this.value == null ? null : this.find_option(this.value);
		this.normalized = null; // { groups, custom }
		this.next_start = 0;
		this.has_more = false;
		this.query = "";
		this.panel = null;
		this.rows = [];
		this.footer_rows = [];
		this.request_id = 0;
		this.id = `es-combobox-${++id_counter}`;

		this.make_trigger();
		// lets scripts and tests reach the instance from the DOM
		this.$trigger.data("es-combobox", this);
		this.set_display();
	}

	// ---- trigger ----

	make_trigger() {
		this.trigger_el = document.createElement("div");
		this.trigger_el.className = "es-combobox flex items-center gap-2 text-ink-gray-8";
		this.$trigger = $(this.trigger_el);
		const t = this.trigger_el;
		t.setAttribute("role", "combobox");
		t.setAttribute("aria-haspopup", "listbox");
		t.setAttribute("aria-expanded", "false");

		this.prefix_el = document.createElement("span");
		this.prefix_el.className = "inline-flex shrink-0 text-ink-gray-6";
		this.prefix_el.hidden = true;

		if (this.opts.value_input) {
			// not readonly: test drivers refuse to type into readonly inputs;
			// edits are refused at beforeinput instead
			this.value_el = document.createElement("input");
			this.value_el.type = "text";
			this.value_el.setAttribute("autocomplete", "off");
			this.value_el.setAttribute("aria-readonly", "true");
			this.value_el.addEventListener("beforeinput", (e) => this.on_value_input(e));
			if (this.opts.open_on_focus) {
				this.value_el.addEventListener("focus", () => {
					// not for the press about to click, nor focus returned on close
					if (this.pointer_active || this.returning_focus || this.disabled) return;
					// focus while open belongs in the panel
					if (this.is_open) {
						(this.input || this.panel).focus({ preventScroll: true });
						return;
					}
					// keyboard focus on a filled value stays put; a pointer press opens
					const by_pointer = Date.now() - last_pointerdown_at < POINTER_FOCUS_MS;
					if (!by_pointer && this.value != null) return;
					this.open({ motion: "instant" });
				});
			}
			this.input_el = this.value_el;
		} else {
			this.value_el = document.createElement("span");
		}
		this.value_el.className = "es-combobox__value flex-1 min-w-0 truncate";

		this.actions_el = document.createElement("span");
		this.actions_el.className = "es-combobox__actions flex items-center gap-0.5 shrink-0";
		if (this.clearable && this.opts.clear_button !== false) {
			this.clear_btn = frappe.ui.button({
				icon: "x",
				variant: "ghost",
				size: "xs",
				title: __("Clear"),
				attrs: { "data-role": "clear", tabindex: "-1" },
				onclick: (e) => {
					e.stopPropagation();
					this.clear();
					this.focus();
				},
			})[0];
		}
		this.action_els = (this.opts.actions || []).map((action) => this.make_action(action));
		for (const el of [this.clear_btn, ...this.action_els].filter(Boolean)) {
			// pointerdown would otherwise count as a trigger press
			el.addEventListener("pointerdown", (e) => e.stopPropagation());
			this.actions_el.appendChild(el);
		}

		t.append(this.prefix_el, this.value_el, this.actions_el);
		t.insertAdjacentHTML(
			"beforeend",
			icon_html("chevron-down", "es-combobox__chevron shrink-0 text-ink-gray-4", COMPONENT)
		);
		this.chevron_el = t.querySelector(".es-combobox__chevron");
		this.set_chevron(this.opts.chevron !== false);

		this.set_disabled(!!this.opts.disabled);

		this.last_pointerdown = 0;
		this.onpointerdown = () => {
			this.last_pointerdown = Date.now();
			// this focus must not open the panel: the click that follows decides
			this.pointer_active = true;
			clearTimeout(this.pointer_timer);
			this.pointer_timer = setTimeout(() => (this.pointer_active = false), POINTER_FOCUS_MS);
		};
		this.onclick = (e) => {
			e.preventDefault();
			this.pointer_active = false;
			if (this.disabled) return;
			if (this.is_open) this.close("owner");
			else
				this.open({
					motion:
						Date.now() - this.last_pointerdown < CLICK_AFTER_PRESS_MS
							? "animated"
							: "instant",
				});
		};
		this.onkeydown = (e) => {
			if (this.disabled) return;
			if (this.run_shortcut(e)) return;
			if (this.is_open) {
				// focus is on the trigger while open: hand navigation keys to the panel
				if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter") {
					e.preventDefault();
					(this.input || this.panel).focus({ preventScroll: true });
					if (e.key !== "Enter") this.step(e.key === "ArrowDown" ? 1 : -1);
				}
				return;
			}
			const arrow = e.key === "ArrowDown" || e.key === "ArrowUp";
			if (arrow && this.opts.arrow_keys_open === false) return; // left to the host
			if (e.key === "Backspace" || e.key === "Delete") {
				// Tab shows the value selected; deleting that text clears the value
				if (!this.clearable || this.value == null) return;
				e.preventDefault();
				this.clear();
			} else if (e.key === "Enter" && this.value != null) {
				// Enter on a picked value belongs to the host (dialog primary action)
				return;
			} else if (e.key === "Enter" || e.key === " " || arrow) {
				e.preventDefault();
				this.open({ motion: "instant" });
			} else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
				// tab-and-type data entry: open with the character as the query
				e.preventDefault();
				this.open({ motion: "instant", query: e.key });
			}
		};
		// capture phase and stopped here so the host's arrow handlers never see it
		this.onaltarrow = (e) => {
			if (!e.altKey || e.shiftKey || e.ctrlKey || e.metaKey) return;
			if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
			if (this.disabled || this.is_open) return;
			e.preventDefault();
			e.stopPropagation();
			this.open({ motion: "instant" });
		};
		t.addEventListener("pointerdown", this.onpointerdown);
		t.addEventListener("click", this.onclick);
		t.addEventListener("keydown", this.onaltarrow, true);
		t.addEventListener("keydown", this.onkeydown);
	}

	run_shortcut(e) {
		if (e.key !== "Enter" || !(e.ctrlKey || e.metaKey)) return false;
		const index = (this.opts.actions || []).findIndex((a) => a.shortcut === "ctrl+enter");
		const el = index >= 0 && this.action_els[index];
		if (!el || el.hidden) return false;
		e.preventDefault();
		el.click();
		return true;
	}

	// covers input with no keydown: virtual keyboards, IME, paste, test drivers
	on_value_input(e) {
		e.preventDefault();
		if (this.disabled || this.is_open) return;
		if (e.inputType.startsWith("delete")) {
			if (this.clearable && this.value != null) this.clear();
			return;
		}
		// a paste / drop carries its text in dataTransfer, not data
		const text = e.data ?? (e.dataTransfer ? e.dataTransfer.getData("text") : "");
		const query = (text || "").split("\n")[0].trim();
		if (query && !this.opts.hide_search) this.open({ motion: "instant", query });
	}

	// a link when it has an href, so middle-click / ctrl-click open a tab
	make_action(action) {
		return frappe.ui.button({
			icon: action.icon,
			variant: "ghost",
			size: "xs",
			title: action.title,
			href: action.href,
			css_class: action.css_class,
			attrs: { tabindex: "-1" },
			onclick: (e) => {
				e.stopPropagation();
				action.onclick && action.onclick(e, this);
			},
		})[0];
	}

	set_disabled(disabled) {
		this.disabled = !!disabled;
		const t = this.trigger_el;
		if (this.disabled) {
			t.setAttribute("aria-disabled", "true");
			t.setAttribute("data-disabled", "");
			t.setAttribute("tabindex", "-1");
			if (this.input_el) this.input_el.tabIndex = -1;
			this.close("owner");
		} else {
			t.removeAttribute("aria-disabled");
			t.removeAttribute("data-disabled");
			// with a value input, that input is the focusable part
			t.setAttribute("tabindex", this.input_el ? "-1" : "0");
			if (this.input_el) this.input_el.tabIndex = 0;
		}
		this.update_clear_button();
	}

	/** Show or hide the chevron. */
	set_chevron(show) {
		// SVG elements have no hidden attribute
		if (this.chevron_el) this.chevron_el.classList.toggle("hidden", !show);
	}

	update_clear_button() {
		if (!this.clear_btn) return;
		this.clear_btn.hidden = this.value == null || this.disabled;
	}

	set_display() {
		const option = this.selected;
		const text = option ? option.label : this.value == null ? null : String(this.value);
		if (this.input_el) {
			this.input_el.value = text == null ? "" : text;
			// keep the input's own placeholder unless one was given here
			if (this.opts.placeholder != null) this.input_el.placeholder = this.opts.placeholder;
		} else {
			this.value_el.textContent =
				text == null ? this.opts.placeholder ?? __("Select") : text;
		}
		this.value_el.toggleAttribute("data-placeholder", text == null);

		const html = option ? prefix_html(option, "xs") : "";
		this.prefix_el.innerHTML = html;
		this.prefix_el.hidden = !html;
		this.update_clear_button();
	}

	// ---- value ----

	get_value() {
		return this.value;
	}

	/** Set the value from code; pass `label` when the option isn't in the rows. */
	set_value(value, { label, image, avatar, silent = true } = {}) {
		const next = value == null || value === "" ? null : value;
		const changed = next !== this.value;
		this.value = next;
		if (next == null) this.selected = null;
		else if (label) this.selected = { label, value: next, image, avatar };
		else this.selected = this.find_option(next);
		this.set_display();
		if (changed && !silent)
			this.opts.on_change && this.opts.on_change(this.value, this.selected);
		return this;
	}

	// clearing opens the panel; on_change fires once: the pick, or null on close
	clear() {
		if (this.value == null) return;
		this.set_value(null, { silent: true });
		this.pending_clear = true;
		if (!this.is_open && !this.disabled) this.open({ motion: "instant" });
		if (!this.is_open) this.flush_clear();
	}

	flush_clear() {
		if (!this.pending_clear) return;
		this.pending_clear = false;
		this.opts.on_change && this.opts.on_change(null, null);
	}

	// a static list is scanned in place; a function source only knows its last rows
	find_option(value) {
		if (!Array.isArray(this.options)) {
			return this.normalized ? find_in(this.normalized.groups, value) : null;
		}
		for (const entry of this.options) {
			if (entry == null || is_custom(entry)) continue;
			for (const row of is_group(entry) ? entry.options : [entry]) {
				const option = normalize_option(row);
				if (option && option.value === value) return option;
			}
		}
		return null;
	}

	set_options(options) {
		this.options = options || [];
		if (this.selected == null && this.value != null)
			this.selected = this.find_option(this.value);
		this.set_display();
		if (this.is_open) this.load();
	}

	/** The listed option the text names (case-insensitive): by value, else by a label only one row has. */
	match_option(text) {
		if (!this.normalized || !text) return null;
		const wanted = text.toLowerCase();
		const options = this.normalized.groups.flatMap((group) => group.options);
		const by_value = options.find((o) => String(o.value).toLowerCase() === wanted);
		if (by_value) return by_value;
		const by_label = options.filter((o) => o.label.toLowerCase() === wanted);
		return by_label.length === 1 ? by_label[0] : null;
	}

	/** True while the rows on screen aren't the ones for the current query. */
	get rows_pending() {
		return !!(this.stale || this.loading);
	}

	// ---- panel ----

	get is_open() {
		return !!this.panel;
	}

	get focus_el() {
		return this.input_el || this.trigger_el;
	}

	focus() {
		this.focus_el.focus();
	}

	open({ motion = "animated", query = "" } = {}) {
		if (this.panel || this.disabled) return;
		this.opts.before_open && this.opts.before_open(this);

		const panel = document.createElement("div");
		panel.className = "es-menu es-combobox__panel flex flex-col overflow-hidden";
		panel.id = this.id;
		panel.setAttribute("role", "listbox");
		panel.setAttribute("tabindex", "-1");
		panel.setAttribute("data-motion", motion);
		if (this.trigger_el.id) panel.setAttribute("aria-labelledby", this.trigger_el.id);
		// set now so async results below can check this.panel and drop stale ones
		this.panel = panel;
		// without a search row there is nowhere to see or clear the query
		this.query = this.opts.hide_search ? "" : query;
		this.stale = false;
		this.pending_activate = false;

		if (!this.opts.hide_search) {
			const search = document.createElement("div");
			search.className =
				"es-combobox__search flex items-center gap-2 shrink-0 px-3 border-b border-outline-gray-1 text-ink-gray-5";
			search.insertAdjacentHTML("beforeend", icon_html("search", "shrink-0", COMPONENT));
			this.input = document.createElement("input");
			this.input.className = "es-combobox__input flex-1 min-w-0 py-2 text-ink-gray-8";
			this.input.type = "text";
			this.input.setAttribute("role", "searchbox");
			this.input.setAttribute("aria-autocomplete", "list");
			this.input.setAttribute("aria-controls", this.id);
			this.input.setAttribute("autocomplete", "off");
			this.input.setAttribute("spellcheck", "false");
			this.input.placeholder = this.opts.search_placeholder || __("Search...");
			this.input.value = this.query;
			this.spinner = document.createElement("span");
			this.spinner.className = "es-spinner";
			this.spinner.setAttribute("aria-hidden", "true");
			this.spinner.hidden = true;
			search.append(this.input, this.spinner);
			panel.appendChild(search);
			this.input.addEventListener("input", () => this.on_query(this.input.value));
		} else {
			this.input = null;
		}

		this.list_el = document.createElement("div");
		// py-1 ps-1, not p-1: the scrollbar gutter is the right inset
		this.list_el.className = "es-combobox__list flex-1 py-1 ps-1";
		this.list_el.addEventListener(
			"scroll",
			() => {
				this.maybe_load_more();
				this.update_scroll_cue();
			},
			{ passive: true }
		);
		// overlay scrollbars (macOS) give no hint that the list goes on
		this.scroll_observer = new ResizeObserver(() => this.update_scroll_cue());
		this.scroll_observer.observe(this.list_el);
		panel.appendChild(this.list_el);

		this.filters_el = document.createElement("div");
		this.filters_el.className =
			"es-combobox__filters flex items-start gap-1 shrink-0 min-w-0 px-3 py-1 border-t border-outline-gray-1 bg-surface-gray-1 text-ink-gray-5 cursor-pointer";
		this.filters_el.hidden = true;
		this.filters_el.setAttribute("role", "button");
		this.filters_el.title = __("Show all filters");
		// a click expands the band without moving focus from the search input
		this.filters_expanded = false;
		this.filters_el.addEventListener("pointerdown", (e) => e.preventDefault());
		this.filters_el.addEventListener("click", () => {
			this.filters_expanded = !this.filters_expanded;
			this.render_filters_value(this.filters_items);
			this.reposition();
		});
		panel.appendChild(this.filters_el);
		this.render_filters();

		this.footer_el = document.createElement("div");
		this.footer_el.className =
			"es-combobox__footer flex flex-col shrink-0 p-1 border-t border-outline-gray-1";
		this.footer_el.hidden = true;
		panel.appendChild(this.footer_el);

		// in <body> so no overflow: hidden ancestor clips it
		document.body.appendChild(panel);
		this.trigger_el.setAttribute("aria-expanded", "true");
		this.trigger_el.setAttribute("aria-controls", panel.id);
		this.trigger_el.setAttribute("data-state", "open");

		this.onpanelkeydown = (e) => this.handle_keydown(e);
		this.onoutside = (e) => {
			if (panel.contains(e.target) || this.trigger_el.contains(e.target)) return;
			// a press on the list's scrollbar has <html> as target: judge by position
			const r = panel.getBoundingClientRect();
			const inside =
				e.clientX >= r.left &&
				e.clientX <= r.right &&
				e.clientY >= r.top &&
				e.clientY <= r.bottom;
			if (inside) return;
			this.close("outside");
		};
		this.onreposition = (e) => {
			// the list's own scroll doesn't move the trigger
			if (e && e.target instanceof Node && panel.contains(e.target)) return;
			if (this.reposition_frame) return;
			this.reposition_frame = requestAnimationFrame(() => {
				this.reposition_frame = null;
				this.reposition();
			});
		};
		panel.addEventListener("keydown", this.onpanelkeydown);
		document.addEventListener("pointerdown", this.onoutside, { capture: true });
		window.addEventListener("resize", this.onreposition);
		document.addEventListener("scroll", this.onreposition, { capture: true, passive: true });

		this.load();
		this.reposition();
		panel.setAttribute("data-state", "open");

		if (this.input) {
			this.input.focus({ preventScroll: true });
			// caret at the end so the seeded character isn't overwritten
			this.input.setSelectionRange(this.input.value.length, this.input.value.length);
		} else {
			panel.focus({ preventScroll: true });
		}
		this.opts.on_open && this.opts.on_open(this);
	}

	reposition() {
		if (!this.panel) return;
		// place() measures the panel as rendered: wait out the enter animation
		const running = (this.panel.getAnimations?.() || []).filter(
			(a) => a.playState === "running"
		);
		if (running.length) {
			if (!this.reposition_pending) {
				this.reposition_pending = Promise.all(running.map((a) => a.finished))
					.catch(() => {})
					.then(() => {
						this.reposition_pending = null;
						this.reposition();
					});
			}
			return;
		}
		const rect = this.trigger_el.getBoundingClientRect();
		// trigger scrolled out of view: hide the panel, it returns with the trigger
		const off_screen =
			rect.bottom <= VIEWPORT_PAD ||
			rect.top >= window.innerHeight - VIEWPORT_PAD ||
			rect.right <= VIEWPORT_PAD ||
			rect.left >= window.innerWidth - VIEWPORT_PAD;
		this.panel.style.visibility = off_screen ? "hidden" : "";
		if (off_screen) return;
		// fixed width, not min-width: long labels must not widen the panel
		const max_width = window.innerWidth - 2 * VIEWPORT_PAD;
		const width = Math.min(Math.max(Math.round(rect.width), MIN_PANEL_WIDTH), max_width);
		this.panel.style.width = `${width}px`;
		this.panel.classList.toggle("es-combobox__panel--narrow", width < NARROW_PANEL_WIDTH);

		// place() would slide a panel over the trigger: cap the height instead
		this.panel.style.maxHeight = "";
		const natural = this.panel.getBoundingClientRect().height;
		const room = {
			bottom: window.innerHeight - rect.bottom - VIEWPORT_PAD - PANEL_OFFSET,
			top: rect.top - VIEWPORT_PAD - PANEL_OFFSET,
		};
		const side = natural > room.bottom && room.top > room.bottom ? "top" : "bottom";
		if (natural > room[side]) {
			this.panel.style.maxHeight = `${Math.max(Math.round(room[side]), MIN_PANEL_HEIGHT)}px`;
		}
		place(this.panel, rect, side, "start", PANEL_OFFSET);
	}

	close(reason = "owner") {
		if (!this.panel) return;
		const panel = this.panel;
		this.panel = null;
		this.rows = [];
		this.footer_rows = [];
		this.highlighted = null;
		this.group_els = [];
		this.more_el = null;
		this.has_more = false;
		this.loading_more = null;
		this.source_rows = null;
		clearTimeout(this.debounce_timer);
		cancelAnimationFrame(this.reposition_frame);
		this.reposition_frame = null;
		this.scroll_observer && this.scroll_observer.disconnect();
		this.scroll_observer = null;

		panel.removeEventListener("keydown", this.onpanelkeydown);
		document.removeEventListener("pointerdown", this.onoutside, { capture: true });
		window.removeEventListener("resize", this.onreposition);
		document.removeEventListener("scroll", this.onreposition, { capture: true });

		this.trigger_el.setAttribute("aria-expanded", "false");
		this.trigger_el.removeAttribute("aria-controls");
		this.trigger_el.removeAttribute("data-state");

		// a click elsewhere already moved focus; don't steal it back
		if (reason === "escape" || reason === "tab" || reason === "select") {
			this.returning_focus = true;
			this.focus_el.focus({ preventScroll: true });
			this.returning_focus = false;
		}

		panel.setAttribute("data-state", "closed");
		setTimeout(() => panel.remove(), EXIT_MS + 50);
		// a clear that opened the panel settles now: nothing was picked
		if (reason !== "select") this.flush_clear();
		this.opts.on_close && this.opts.on_close(reason);
	}

	// ---- rows ----

	on_query(query) {
		this.query = query;
		if (typeof this.options === "function" && !this.filterable) {
			// stale rows must not be committed by Enter until the new ones land
			this.stale = true;
			this.highlight(null);
			clearTimeout(this.debounce_timer);
			this.debounce_timer = setTimeout(() => this.load(), DEBOUNCE_MS);
		} else if (typeof this.options === "function") {
			// a preloaded source is cheap: refilter right away
			this.load();
		} else {
			this.render();
		}
	}

	load() {
		if (!this.panel) return;
		const request_id = ++this.request_id;
		let value = this.options;
		if (typeof value === "function") {
			try {
				value = value(this.query, { start: 0 });
			} catch (error) {
				console.error(error);
				value = [];
			}
		}
		if (is_thenable(value)) {
			this.set_loading(true);
			value.then(
				(result) => {
					if (request_id !== this.request_id || !this.panel) return;
					this.set_loading(false);
					this.set_rows(result);
				},
				(error) => {
					if (request_id !== this.request_id || !this.panel) return;
					console.error(error);
					this.set_loading(false);
					this.set_rows([]);
					this.render(__("Could not load options"));
				}
			);
			return;
		}
		this.set_rows(value);
	}

	set_rows(result) {
		const { rows, has_more } = unpack(result);
		// the same array again means only the filter changed
		if (rows !== this.source_rows) {
			this.source_rows = rows;
			this.normalized = normalize_options(rows);
		}
		this.next_start = this.opts.page_size || 0;
		this.empty_pages = 0;
		this.has_more = this.page_allows_more(rows, has_more);
		// a page load for the previous rows is void now
		this.loading_more = null;
		this.render();
	}

	page_allows_more(rows, has_more) {
		const page_size = this.opts.page_size;
		if (!page_size || typeof this.options !== "function") return false;
		return has_more == null ? rows.length >= page_size : !!has_more;
	}

	update_scroll_cue() {
		const list = this.list_el;
		if (!list) return;
		const below = list.scrollHeight - list.scrollTop - list.clientHeight > 2;
		list.toggleAttribute("data-more-below", below);
	}

	maybe_load_more() {
		if (!this.has_more || !this.list_el) return;
		const list = this.list_el;
		const remaining = list.scrollHeight - list.scrollTop - list.clientHeight;
		if (remaining < LOAD_MORE_THRESHOLD) this.load_more();
	}

	load_more() {
		if (!this.panel || !this.has_more || this.loading_more) return;
		const token = { request_id: this.request_id, query: this.query };
		this.loading_more = token;
		let value;
		try {
			value = this.options(this.query, { start: this.next_start });
		} catch (error) {
			console.error(error);
			value = [];
		}
		const current = () =>
			this.panel && this.loading_more === token && token.request_id === this.request_id;
		Promise.resolve(value).then(
			(result) => {
				if (!current()) return;
				this.loading_more = null;
				const { rows, has_more } = unpack(result);
				const added = merge_normalized(this.normalized, normalize_options(rows));
				this.source_rows = null;
				this.next_start += this.opts.page_size;
				this.empty_pages = added.length ? 0 : this.empty_pages + 1;
				this.has_more =
					this.empty_pages < MAX_EMPTY_PAGES && this.page_allows_more(rows, has_more);
				this.append_rows(added);
			},
			(error) => {
				if (!current()) return;
				this.loading_more = null;
				console.error(error);
				this.has_more = false;
				this.update_more_row();
			}
		);
	}

	// append without rebuilding: scroll position and highlight stay put
	append_rows(groups) {
		for (const group of groups) {
			const last = this.group_els[this.group_els.length - 1];
			let group_el = group.group
				? this.group_els.find((el) => el.dataset.group === group.group)
				: last && !last.dataset.group && last;
			if (!group_el) {
				group_el = this.make_group_el(group);
				this.list_el.appendChild(group_el);
			}
			const reserve = group_el.dataset.reserve === "1" || needs_icon_space(group.options);
			for (const option of group.options) {
				group_el.appendChild(this.add_row({ option }, { reserve, query: this.query }));
			}
		}
		this.update_more_row();
	}

	make_group_el(group) {
		const group_el = document.createElement("div");
		group_el.className = "es-menu__group";
		group_el.setAttribute("role", "group");
		if (group.group) group_el.dataset.group = group.group;
		// iconless rows reserve the icon space so labels line up
		if (needs_icon_space(group.options)) group_el.dataset.reserve = "1";
		if (group.group) {
			const label = document.createElement("div");
			label.className = "es-menu__group-label px-2";
			label.id = `${this.id}-g${this.group_els.length}`;
			label.textContent = group.group;
			group_el.setAttribute("aria-labelledby", label.id);
			group_el.appendChild(label);
		}
		this.group_els.push(group_el);
		return group_el;
	}

	update_more_row() {
		if (!this.list_el) return;
		if (this.more_el) {
			this.more_el.remove();
			this.more_el = null;
		}
		if (!this.has_more || !this.rows.length) return;
		const more = document.createElement("div");
		more.className = "es-menu__loading";
		more.setAttribute("aria-hidden", "true");
		const spinner = document.createElement("span");
		spinner.className = "es-spinner";
		more.append(spinner, document.createTextNode(__("Loading more...")));
		this.list_el.appendChild(more);
		this.more_el = more;
		this.update_scroll_cue();
		this.maybe_load_more();
	}

	set_loading(loading) {
		if (!this.panel) return;
		this.loading = loading;
		this.panel.setAttribute("aria-busy", loading ? "true" : "false");
		if (this.spinner) this.spinner.hidden = !loading;
		if (loading && !this.rows.length) {
			const rows = ["55%", "70%", "45%"]
				.map(
					(width) =>
						`<div class="flex items-center gap-2 px-2 py-1.5">${frappe.ui.skeleton.html(
							{
								css_class: "size-6 rounded-full",
							}
						)}${frappe.ui.skeleton.html({ width, height: "12px" })}</div>`
				)
				.join("");
			this.list_el.innerHTML = `<div class="es-menu__group">${rows}</div>`;
		}
	}

	render_filters() {
		if (!this.filters_el) return;
		let filters = this.opts.filters;
		if (typeof filters === "function") filters = filters(this);
		if (is_thenable(filters)) {
			const panel = this.panel;
			filters.then((value) => {
				if (this.panel !== panel) return;
				this.render_filters_value(value);
				// the empty-state text on screen mentions the filters: redraw it
				if (this.normalized && !this.rows.length) this.render();
				else this.reposition();
			});
			return;
		}
		this.render_filters_value(filters);
	}

	render_filters_value(filters) {
		const items = Array.isArray(filters) ? filters.filter(Boolean) : filters ? [filters] : [];
		this.filters_items = filters;
		this.has_filters = items.length > 0;
		this.filters_el.replaceChildren();
		this.filters_el.hidden = !this.has_filters;
		if (!this.has_filters) return;
		const expanded = this.filters_expanded;
		this.filters_el.toggleAttribute("data-expanded", expanded);
		this.filters_el.setAttribute("aria-expanded", String(expanded));
		this.filters_el.title = expanded ? __("Show less") : __("Show all filters");
		const body = document.createElement("div");
		body.className = "es-combobox__filters-body flex items-center gap-1 flex-1 min-w-0";
		this.filters_el.appendChild(body);
		body.insertAdjacentHTML("beforeend", icon_html("list-filter", "", COMPONENT));
		const label = document.createElement("span");
		label.className = "es-combobox__filters-label shrink-0 me-0.5";
		label.textContent = __("Filtered by");
		body.appendChild(label);

		if (!Array.isArray(filters)) {
			const text = document.createElement("span");
			text.className = "es-combobox__filters-text flex-1 min-w-0 truncate text-ink-gray-7";
			text.textContent = filters;
			body.appendChild(text);
		} else {
			const shown = expanded ? items : items.slice(0, 1);
			for (const item of shown) {
				// collapsed, a chip may truncate: the title shows it whole
				const chip = frappe.ui.badge({
					label: String(item),
					size: "sm",
					title: expanded ? undefined : String(item),
				});
				body.appendChild(chip[0]);
			}
			if (!expanded && items.length > 1) {
				const more = frappe.ui.badge({
					label: `+${items.length - 1}`,
					size: "sm",
					variant: "outline",
					css_class: "es-combobox__filters-more",
				});
				body.appendChild(more[0]);
			}
		}
	}

	render(empty_text) {
		if (!this.panel) return;
		const { groups, custom } = this.normalized || { groups: [], custom: [] };
		const query = this.query;
		const filter = this.filterable ? (option) => matches(option, query) : () => true;

		this.rows = [];
		this.footer_rows = [];
		this.row_seq = 0;
		this.highlighted = null;
		this.group_els = [];
		this.more_el = null;
		this.list_el.replaceChildren();
		for (const group of groups) {
			const options = group.options.filter(filter);
			if (!options.length) continue;
			const group_el = this.make_group_el({ ...group, options });
			const reserve = needs_icon_space(options);
			for (const option of options) {
				group_el.appendChild(this.add_row({ option }, { reserve, query }));
			}
			this.list_el.appendChild(group_el);
		}
		if (!this.rows.length) {
			const empty = document.createElement("div");
			empty.className = "es-menu__empty";
			empty.textContent =
				empty_text ||
				(query && this.has_filters
					? __("No results for {0} within the current filters", [query])
					: query
					? __("No results for {0}", [query])
					: __("No results"));
			this.list_el.appendChild(empty);
		}

		this.footer_el.replaceChildren();
		const shown = [...custom, ...(this.opts.footer || [])].filter((row) =>
			row.condition ? row.condition({ query }) : true
		);
		for (const row of shown) {
			this.footer_el.appendChild(this.add_row({ custom: row }, { query }));
		}
		this.footer_el.hidden = !shown.length;

		// with nothing matching, the first custom row so Enter creates
		const current = this.rows.find((r) => r.option.value === this.value);
		this.highlight(
			current || this.nav_rows.find((r) => !(r.option && r.option.disabled)) || null
		);
		this.stale = false;
		this.reposition();
		this.update_scroll_cue();
		this.update_more_row();

		// Enter arrived while rows were loading: commit an option, never a custom row
		if (this.pending_activate) {
			this.pending_activate = false;
			if (this.highlighted && this.highlighted.option) this.activate(this.highlighted);
		}
	}

	get nav_rows() {
		return [...this.rows, ...this.footer_rows];
	}

	// list and footer rows kept apart, so a later page still sits before the footer
	add_row(row, { reserve, query } = {}) {
		const option = row.option || {
			label:
				typeof row.custom.label === "function"
					? row.custom.label({ query: query || "" })
					: row.custom.label,
			icon: row.custom.icon,
		};
		const el = document.createElement("button");
		el.type = "button";
		el.className = "es-menu__item";
		el.setAttribute("role", "option");
		el.setAttribute("tabindex", "-1");
		el.id = `${this.id}-r${this.row_seq++}`;
		if (option.disabled) {
			el.setAttribute("data-disabled", "");
			el.setAttribute("aria-disabled", "true");
			el.disabled = true;
		}
		const selected = !!row.option && option.value === this.value;
		el.setAttribute("aria-selected", selected ? "true" : "false");

		const prefix = prefix_html(option, "sm");
		if (prefix) {
			el.insertAdjacentHTML("beforeend", prefix);
		} else if (reserve) {
			const space = document.createElement("span");
			space.className = "es-menu__icon-space";
			space.setAttribute("aria-hidden", "true");
			el.appendChild(space);
		}

		const label = document.createElement("span");
		label.className = "es-menu__label";
		fill_label(label, option.label || "", row.custom ? "" : query);
		if (option.badge && option.badge.label) {
			// the badge validates the theme itself
			label.insertAdjacentHTML(
				"beforeend",
				frappe.ui.badge.html({
					label: option.badge.label,
					theme: option.badge.theme,
					size: "sm",
					css_class: "es-combobox__badge ms-2",
				})
			);
		}
		if (option.description) {
			const description = document.createElement("span");
			description.className = "es-menu__description";
			description.textContent = option.description;
			label.appendChild(description);
		}
		el.appendChild(label);
		if (selected) {
			el.insertAdjacentHTML(
				"beforeend",
				icon_html("check", "ms-auto shrink-0 text-ink-gray-6", COMPONENT)
			);
		}

		// mousedown would blur the search input before click fires
		el.addEventListener("pointerdown", (e) => e.preventDefault());
		el.addEventListener("pointermove", () => this.highlight(row, { scroll: false }));
		el.addEventListener("click", () => this.activate(row));

		row.el = el;
		(row.option ? this.rows : this.footer_rows).push(row);
		return el;
	}

	highlight(row, { scroll = true } = {}) {
		row = row || null;
		if (row === this.highlighted) return;
		if (this.highlighted) this.highlighted.el.removeAttribute("data-highlighted");
		this.highlighted = row;
		const owner = this.input || this.panel;
		if (!row) {
			owner && owner.removeAttribute("aria-activedescendant");
			return;
		}
		row.el.setAttribute("data-highlighted", "");
		owner && owner.setAttribute("aria-activedescendant", row.el.id);
		// a hovered row is already on screen
		if (scroll) row.el.scrollIntoView({ block: "nearest" });
	}

	step(direction, edge) {
		const rows = this.nav_rows.filter((r) => !(r.option && r.option.disabled));
		if (!rows.length) return;
		let index;
		if (edge) {
			index = direction > 0 ? 0 : rows.length - 1;
		} else {
			const current = rows.indexOf(this.highlighted);
			index =
				current >= 0
					? (current + direction + rows.length) % rows.length
					: direction > 0
					? 0
					: rows.length - 1;
		}
		this.highlight(rows[index]);
	}

	activate(row) {
		if (!row) return;
		if (row.custom) {
			row.custom.onclick && row.custom.onclick({ query: this.query, combobox: this });
			this.close("select");
			return;
		}
		if (row.option.disabled) return;
		this.select(row.option);
	}

	select(option) {
		// after a clear the value is null, so any pick counts as a change
		const changed = option.value !== this.value || this.pending_clear;
		this.pending_clear = false;
		this.value = option.value;
		this.selected = option;
		this.set_display();
		this.close("select");
		if (changed) this.opts.on_change && this.opts.on_change(this.value, option);
	}

	handle_keydown(e) {
		const handled = () => {
			e.preventDefault();
			e.stopPropagation();
		};
		if (this.run_shortcut(e)) {
			handled();
			return;
		}
		switch (e.key) {
			case "ArrowDown":
				handled();
				this.step(1);
				break;
			case "ArrowUp":
				handled();
				this.step(-1);
				break;
			case "Home":
				if (this.input && this.input.value) break; // let the caret move
				handled();
				this.step(1, true);
				break;
			case "End":
				if (this.input && this.input.value) break;
				handled();
				this.step(-1, true);
				break;
			case "Enter":
				handled();
				// rows for the query haven't arrived: commit when they do (see render)
				if (this.stale) this.pending_activate = true;
				else this.activate(this.highlighted);
				break;
			case "Escape":
				handled();
				this.close("escape");
				break;
			case "Tab":
				// don't trap focus; typed text plus Tab picks the highlighted match
				if (this.query && !this.stale && this.highlighted && this.highlighted.option) {
					this.select(this.highlighted.option);
				} else {
					this.close("tab");
				}
				break;
			default:
				if (!this.input && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
					// no search row: type-to-jump on the rows
					handled();
					this.typeahead(e.key);
				} else if (e.ctrlKey || e.metaKey || e.altKey) {
					// keep Ctrl+S etc. from reaching frappe's global handler
					e.stopPropagation();
				}
		}
	}

	typeahead(char) {
		clearTimeout(this.typeahead_timer);
		this.typeahead_timer = setTimeout(() => (this.typeahead_buffer = ""), 1000);
		this.typeahead_buffer = (this.typeahead_buffer || "") + char.toLowerCase();
		const rows = this.rows.filter((r) => !r.option.disabled);
		const current = rows.indexOf(this.highlighted);
		const start = current === -1 ? 0 : current + (this.typeahead_buffer.length === 1 ? 1 : 0);
		for (let i = 0; i < rows.length; i++) {
			const row = rows[(start + i) % rows.length];
			if (row.option.label.toLowerCase().startsWith(this.typeahead_buffer)) {
				this.highlight(row);
				return;
			}
		}
	}
};

/**
 * Makes the trigger and wires the combobox in one call. The instance is on
 * `.data("es-combobox")`.
 * @param {ComboboxOpts} opts
 * @returns {JQuery}
 * @example toolbar.append(frappe.ui.combobox({
 *     options: ["Open", "Closed"],
 *     on_change: (value) => this.filter(value),
 * }));
 */
frappe.ui.combobox = function (opts = {}) {
	return new frappe.ui.Combobox(opts).$trigger;
};

export default frappe.ui.combobox;
