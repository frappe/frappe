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
 * @property {boolean} [clear_button=true] Show the × button (Backspace / Delete always clear).
 * @property {boolean|function} [tab_selects=true] Tab after typing (or moving to a row) picks it; off, Tab only closes. A function is asked at Tab time with {navigated, query}.
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
 * @property {function} [on_close] Called with the reason: "select" | "escape" | "outside" | "tab" | "owner" (a click on the trigger, a host's close) | "disabled" | "hidden".
 */

const EXIT_MS = 140; // keep in sync with es-menu-out in menu.css
const DEBOUNCE_MS = 300;
const PANEL_OFFSET = 4;
// grid cells can be very narrow, so keep the panel at least this wide
const MIN_PANEL_WIDTH = 240;
const MIN_PANEL_HEIGHT = 160; // below this the panel may overlap the trigger
const NARROW_PANEL_WIDTH = 320; // below this the filter band drops its label
const VIEWPORT_PAD = 8;
const LOAD_MORE_THRESHOLD = 48;
// stop paging after this many pages in a row bring no new rows
const MAX_EMPTY_PAGES = 3;
// focus within this time after a mouse press came from the mouse
const POINTER_FOCUS_MS = 200;
// a click within this time after a press is a mouse click, not a keyboard one
const CLICK_AFTER_PRESS_MS = 300;
let last_pointerdown_at = 0;
// record both press and click so a long press still counts
for (const type of ["pointerdown", "click"]) {
	document.addEventListener(
		type,
		(e) => {
			// ignore presses inside the panel
			if (e.target.closest && e.target.closest(".es-combobox__panel")) return;
			last_pointerdown_at = Date.now();
		},
		{ capture: true, passive: true }
	);
}
// after a key press, the next focus is from the keyboard
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

// custom rows are not filtered
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
		this.settled_request_id = 0; // the request whose rows are on screen
		this.id = `es-combobox-${++id_counter}`;

		this.make_trigger();
		// so scripts and tests can get the instance from the element
		this.$trigger.data("es-combobox", this);
		this.set_display();
	}

	// ---- trigger ----

	make_trigger() {
		this.trigger_el = document.createElement("div");
		this.trigger_el.className =
			"es-combobox w-full flex items-center gap-2 ps-2 pe-1.5 cursor-pointer text-ink-gray-8";
		this.$trigger = $(this.trigger_el);
		const t = this.trigger_el;
		t.setAttribute("role", "combobox");
		t.setAttribute("aria-haspopup", "listbox");
		t.setAttribute("aria-expanded", "false");

		this.prefix_el = document.createElement("span");
		this.prefix_el.className = "inline-flex shrink-0 text-ink-gray-6";
		this.prefix_el.hidden = true;

		if (this.opts.value_input) {
			// not readonly, as tests can't type into readonly inputs; edits are blocked in beforeinput
			this.value_el = document.createElement("input");
			this.value_el.type = "text";
			this.value_el.setAttribute("autocomplete", "off");
			this.value_el.setAttribute("aria-readonly", "true");
			this.value_el.addEventListener("beforeinput", (e) => this.on_value_input(e));
			this.value_el.addEventListener("input", (e) => {
				// Firefox adds the IME text after compositionend
				if (e.inputType === "insertCompositionText" && !e.isComposing) this.set_display();
			});
			this.value_el.addEventListener("compositionend", (e) => {
				// use the IME text as the search and show the value again
				this.set_display();
				const query = (e.data || "").split("\n")[0].trim();
				if (query && !this.disabled && !this.is_open)
					this.open({ motion: "instant", query });
			});
			if (this.opts.open_on_focus) {
				this.value_el.addEventListener("focus", () => {
					// skip mouse focus and focus given back on close
					if (this.pointer_active || this.returning_focus || this.disabled) return;
					// when open, focus goes to the panel
					if (this.is_open) {
						(this.input || this.panel).focus({ preventScroll: true });
						return;
					}
					// keyboard focus on a filled field doesn't open; a mouse press does
					const by_pointer = Date.now() - last_pointerdown_at < POINTER_FOCUS_MS;
					if (!by_pointer && this.value != null) return;
					this.open({ motion: "instant" });
				});
			}
			this.input_el = this.value_el;
		} else {
			this.value_el = document.createElement("span");
		}
		this.value_el.className =
			"es-combobox__value flex-1 min-w-0 truncate border-0 cursor-pointer";

		this.actions_el = document.createElement("span");
		this.actions_el.className = "es-combobox__actions flex items-center gap-0.5 shrink-0";
		if (this.opts.clear_button !== false) {
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
			// don't count this press as a press on the field
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
			// don't open on this focus; the click decides
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
			if (this.disabled || e.isComposing || e.keyCode === 229) return;
			if (this.run_shortcut(e)) return;
			if (this.is_open) {
				// field has focus while open: send arrow keys to the panel
				if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter") {
					e.preventDefault();
					(this.input || this.panel).focus({ preventScroll: true });
					if (e.key !== "Enter") this.step(e.key === "ArrowDown" ? 1 : -1);
				} else if (e.key === "Escape") {
					e.preventDefault();
					e.stopPropagation();
					this.close("escape");
				} else if (e.key === "Tab") {
					this.close("tab");
				}
				return;
			}
			const arrow = e.key === "ArrowDown" || e.key === "ArrowUp";
			if (arrow && this.opts.arrow_keys_open === false) return; // left to the host
			if (e.key === "Backspace" || e.key === "Delete") {
				// value is selected after Tab; Backspace/Delete clears it
				if (this.value == null) return;
				e.preventDefault();
				this.clear();
			} else if (e.key === "Enter" && this.value != null) {
				// let Enter reach the dialog's primary action
				return;
			} else if (e.key === "Enter" || e.key === " " || arrow) {
				e.preventDefault();
				this.open({ motion: "instant" });
			} else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
				// typing on a focused field opens the panel with that character
				e.preventDefault();
				this.open({ motion: "instant", query: e.key });
			}
		};
		// stop here so the grid's arrow key handlers don't get it
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
		// the button may have been removed
		if (!el || el.hidden || !el.isConnected) return false;
		e.preventDefault();
		el.click();
		return true;
	}

	// input without keydown: mobile keyboards, IME, paste, tests
	on_value_input(e) {
		// IME still typing; compositionend handles it
		if (e.isComposing || e.inputType === "insertCompositionText") return;
		e.preventDefault();
		if (this.disabled || this.is_open) return;
		if (e.inputType.startsWith("delete")) {
			if (this.value != null) this.clear();
			return;
		}
		// paste and drop text is in dataTransfer
		const text = e.data ?? (e.dataTransfer ? e.dataTransfer.getData("text") : "");
		const query = (text || "").split("\n")[0].trim();
		if (query) this.open({ motion: "instant", query });
	}

	// use a link when there is an href, so it can open in a new tab
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
			this.close("disabled");
		} else {
			t.removeAttribute("aria-disabled");
			t.removeAttribute("data-disabled");
			// the value input takes focus
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
			// keep the existing placeholder if none is given
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
		// setting a new value cancels a pending clear
		if (next != null && this.pending_clear && next !== this.cleared_value) {
			this.pending_clear = false;
		}
		this.value = next;
		if (next == null) this.selected = null;
		else if (label) this.selected = { label, value: next, image, avatar };
		else this.selected = this.find_option(next);
		this.set_display();
		if (changed && !silent)
			this.opts.on_change && this.opts.on_change(this.value, this.selected);
		return this;
	}

	// clear opens the panel; on_change fires once, with the pick or null on close
	clear() {
		if (this.value == null) return;
		this.cleared_value = this.value;
		this.cleared_option = this.selected;
		this.set_value(null, { silent: true });
		this.pending_clear = true;
		this.clear_held = false;
		try {
			if (!this.is_open && !this.disabled) this.open({ motion: "instant" });
		} finally {
			// panel didn't open, so finish the clear now
			if (!this.is_open) this.flush_clear();
		}
	}

	// wait to finish the clear while the typed text is being looked up
	hold_clear() {
		this.clear_held = true;
	}

	release_clear() {
		this.clear_held = false;
	}

	flush_clear() {
		if (!this.pending_clear || this.clear_held) return;
		this.pending_clear = false;
		this.opts.on_change && this.opts.on_change(null, null);
	}

	// for a function source, only the last loaded rows are known
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
		if (this.value != null) this.selected = this.find_option(this.value) || this.selected;
		this.set_display();
		if (this.is_open) this.load();
	}

	/** The option the text names (case-insensitive): by value, else by a label only one row has. */
	static match_in(options, text) {
		if (!text) return null;
		const wanted = text.toLowerCase();
		const flat = (options || [])
			.flatMap((o) => (is_group(o) ? o.options : [o]))
			.filter(Boolean);
		const by_value = flat.find((o) => String(o.value).toLowerCase() === wanted);
		if (by_value) return by_value;
		const by_label = flat.filter((o) => String(o.label).toLowerCase() === wanted);
		return by_label.length === 1 ? by_label[0] : null;
	}

	/** match_in over the rows last resolved for this panel. */
	match_option(text) {
		return this.normalized ? Combobox.match_in(this.normalized.groups, text) : null;
	}

	/** True while the shown rows are not yet for the current search. */
	get rows_pending() {
		return this.request_id !== this.settled_request_id;
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
		// set early so late async results can tell they are stale
		this.panel = panel;
		// without a search box, typing jumps to a row
		this.query = this.opts.hide_search ? "" : query;
		this.pending_typeahead = this.opts.hide_search ? query : "";
		// reset rows and filters from the last open
		this.normalized = null;
		this.has_filters = false;
		this.filters_items = null;
		this.typeahead_buffer = "";
		this.pending_activate = false;

		if (!this.opts.hide_search) {
			const search = document.createElement("div");
			search.className =
				"es-combobox__search flex items-center gap-2 shrink-0 px-3 border-b border-outline-gray-1 text-ink-gray-5";
			search.insertAdjacentHTML("beforeend", icon_html("search", "shrink-0", COMPONENT));
			this.input = document.createElement("input");
			this.input.className =
				"es-combobox__input flex-1 min-w-0 py-2 border-0 text-ink-gray-8";
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
		// no right padding: the scrollbar gutter gives it
		this.list_el.className = "es-combobox__list flex-1 py-1 ps-1";
		this.list_el.addEventListener(
			"scroll",
			() => {
				this.maybe_load_more();
				this.update_scroll_cue();
			},
			{ passive: true }
		);
		// macOS hides scrollbars, so show a hint that the list scrolls
		this.scroll_observer = new ResizeObserver(() => this.update_scroll_cue());
		this.scroll_observer.observe(this.list_el);
		// close the panel when the field gets hidden
		this.trigger_observer = new ResizeObserver(() => this.onreposition());
		this.trigger_observer.observe(this.trigger_el);
		panel.appendChild(this.list_el);

		this.filters_el = document.createElement("div");
		this.filters_el.className =
			"es-combobox__filters flex items-start gap-1 shrink-0 min-w-0 px-3 py-1 border-t border-outline-gray-1 bg-surface-gray-1 text-ink-gray-5 cursor-pointer";
		this.filters_el.hidden = true;
		this.filters_el.setAttribute("role", "button");
		this.filters_el.title = __("Show all filters");
		// expand filters without taking focus from search
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

		// add to <body> so parents with overflow: hidden don't cut it
		document.body.appendChild(panel);
		this.trigger_el.setAttribute("aria-expanded", "true");
		this.trigger_el.setAttribute("aria-controls", panel.id);
		this.trigger_el.setAttribute("data-state", "open");

		this.onpanelkeydown = (e) => this.handle_keydown(e);
		this.onoutside = (e) => {
			if (panel.contains(e.target) || this.trigger_el.contains(e.target)) return;
			// a scrollbar press targets <html>, so check the position
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
			// scrolling the list itself doesn't move the field
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
		// it may have closed already (field hidden)
		if (this.panel !== panel) return;
		panel.setAttribute("data-state", "open");

		if (this.input) {
			this.input.focus({ preventScroll: true });
			// cursor at the end so the typed character stays
			this.input.setSelectionRange(this.input.value.length, this.input.value.length);
		} else {
			panel.focus({ preventScroll: true });
		}
		this.opts.on_open && this.opts.on_open(this);
	}

	reposition() {
		if (!this.panel) return;
		const t = this.trigger_el;
		const rect = t.getBoundingClientRect();
		// the field was hidden or removed
		if (!t.isConnected || (!rect.width && !rect.height)) {
			this.close("hidden");
			return;
		}
		// hide the panel while the field is scrolled out of view
		const off_screen =
			rect.bottom <= VIEWPORT_PAD ||
			rect.top >= window.innerHeight - VIEWPORT_PAD ||
			rect.right <= VIEWPORT_PAD ||
			rect.left >= window.innerWidth - VIEWPORT_PAD;
		this.panel.style.visibility = off_screen ? "hidden" : "";
		if (off_screen) return;
		// fixed width so long labels don't widen the panel
		const max_width = window.innerWidth - 2 * VIEWPORT_PAD;
		const width = Math.min(Math.max(Math.round(rect.width), MIN_PANEL_WIDTH), max_width);
		this.panel.style.width = `${width}px`;
		this.panel.classList.toggle("es-combobox__panel--narrow", width < NARROW_PANEL_WIDTH);

		// limit the height so the panel doesn't cover the field
		this.panel.style.maxHeight = "";
		const natural = this.panel.offsetHeight;
		const room = {
			bottom: window.innerHeight - rect.bottom - VIEWPORT_PAD - PANEL_OFFSET,
			top: rect.top - VIEWPORT_PAD - PANEL_OFFSET,
		};
		const side = natural > room.bottom && room.top > room.bottom ? "top" : "bottom";
		if (natural > room[side]) {
			this.panel.style.maxHeight = `${Math.max(Math.round(room[side]), MIN_PANEL_HEIGHT)}px`;
		}
		// position again after the open animation
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
		this.set_display();
		clearTimeout(this.debounce_timer);
		cancelAnimationFrame(this.reposition_frame);
		this.reposition_frame = null;
		this.reposition_pending = null;
		this.pending_typeahead = "";
		this.scroll_observer && this.scroll_observer.disconnect();
		this.trigger_observer && this.trigger_observer.disconnect();
		this.scroll_observer = this.trigger_observer = null;
		this.typeahead_buffer = "";

		panel.removeEventListener("keydown", this.onpanelkeydown);
		document.removeEventListener("pointerdown", this.onoutside, { capture: true });
		window.removeEventListener("resize", this.onreposition);
		document.removeEventListener("scroll", this.onreposition, { capture: true });

		this.trigger_el.setAttribute("aria-expanded", "false");
		this.trigger_el.removeAttribute("aria-controls");
		this.trigger_el.removeAttribute("data-state");

		// give focus back to the field, unless the user clicked somewhere else
		const held_focus = reason !== "outside" && panel.contains(document.activeElement);
		if (reason === "escape" || reason === "tab" || reason === "select" || held_focus) {
			this.returning_focus = true;
			this.focus_el.focus({ preventScroll: true });
			this.returning_focus = false;
		}

		panel.setAttribute("data-state", "closed");
		setTimeout(() => panel.remove(), EXIT_MS + 50);
		// the field may save typed text here; it may return a promise
		const committed = this.opts.on_close && this.opts.on_close(reason);
		if (reason === "disabled" || reason === "hidden") {
			// field hidden or disabled during a clear: undo the clear
			if (this.pending_clear) {
				this.pending_clear = false;
				const o = this.cleared_option;
				this.set_value(
					this.cleared_value,
					o ? { label: o.label, image: o.image, avatar: o.avatar } : {}
				);
			}
		} else if (reason !== "select") {
			this.flush_clear();
		}
		return committed;
	}

	// ---- rows ----

	on_query(query) {
		this.query = query;
		// a queued Enter was for the old rows
		this.pending_activate = false;
		if (typeof this.options === "function" && !this.filterable) {
			// shown rows are for the old search until the load ends
			this.request_id++;
			this.highlight(null);
			clearTimeout(this.debounce_timer);
			this.debounce_timer = setTimeout(() => this.load(), DEBOUNCE_MS);
		} else if (typeof this.options === "function") {
			// preloaded rows: filter right away
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
					this.settled_request_id = request_id;
					this.set_loading(false);
					this.set_rows(result);
				},
				(error) => {
					if (request_id !== this.request_id || !this.panel) return;
					// keep rows pending: typed text is looked up on close
					console.error(error);
					this.set_loading(false);
					this.set_rows([]);
					this.render(__("Could not load options"));
				}
			);
			return;
		}
		this.settled_request_id = request_id;
		this.set_rows(value);
	}

	set_rows(result) {
		const { rows, has_more } = unpack(result);
		// same array: only the filter changed
		if (rows !== this.source_rows) {
			this.source_rows = rows;
			this.normalized = normalize_options(rows);
		}
		this.next_start = this.opts.page_size || 0;
		this.empty_pages = 0;
		this.has_more = this.page_allows_more(rows, has_more);
		// ignore a page still loading for the old rows
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

	// append rows so scroll and highlight stay
	append_rows(groups) {
		// remove the empty message when later rows arrive
		if (groups.length) this.list_el.querySelector(".es-menu__empty")?.remove();
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
		// rows without icon keep the space so labels line up
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
		if (!this.has_more) return;
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
			filters
				.then((value) => {
					if (this.panel !== panel) return;
					this.render_filters_value(value);
					// the empty message mentions filters, so redraw it
					if (!this.rows_pending && this.normalized && !this.rows.length) this.render();
					else this.reposition();
				})
				.catch(() => {});
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
				// chip text can be cut; the title shows it in full
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

		// highlight the current value, or the first row when searching
		const current = query ? null : this.rows.find((r) => r.option.value === this.value);
		this.highlight(
			current || this.nav_rows.find((r) => !(r.option && r.option.disabled)) || null
		);
		this.navigated = false;
		this.pointer_highlight = false;
		if (this.pending_typeahead) {
			const text = this.pending_typeahead;
			this.pending_typeahead = "";
			this.typeahead(text);
		}
		this.reposition();
		this.update_scroll_cue();
		this.update_more_row();

		// Enter pressed while loading: pick a row, not a custom row
		if (this.pending_activate) {
			this.pending_activate = false;
			if (this.highlighted && this.highlighted.option) this.activate(this.highlighted);
		}
	}

	get nav_rows() {
		return [...this.rows, ...this.footer_rows];
	}

	// keep list and footer rows apart so new pages go above the footer
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
			// the badge checks the theme
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

		// keep focus in the search box on mousedown
		el.addEventListener("pointerdown", (e) => e.preventDefault());
		el.addEventListener("pointermove", () => {
			this.pointer_highlight = true;
			this.highlight(row, { scroll: false });
		});
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
		// hovered row is already visible
		if (scroll) row.el.scrollIntoView({ block: "nearest" });
	}

	step(direction, edge) {
		const rows = this.nav_rows.filter((r) => !(r.option && r.option.disabled));
		if (!rows.length) return;
		this.navigated = true;
		this.pointer_highlight = false;
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
			// the row set a value, so that is the pick
			if (this.value != null) this.pending_clear = false;
			this.close("select");
			// custom row picked nothing: finish the pending clear
			this.flush_clear();
			return;
		}
		if (row.option.disabled) return;
		this.select(row.option);
	}

	select(option) {
		// after a clear any pick is a change
		const changed = option.value !== this.value || this.pending_clear;
		this.pending_clear = false;
		this.value = option.value;
		this.selected = option;
		this.set_display();
		this.close("select");
		if (changed) this.opts.on_change && this.opts.on_change(this.value, option);
	}

	handle_keydown(e) {
		// leave keys to the IME while typing
		if (e.isComposing || e.keyCode === 229) return;
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
				// rows still loading: pick when they arrive (see render)
				if (this.rows_pending) this.pending_activate = true;
				else this.activate(this.highlighted);
				break;
			case "Escape":
				handled();
				this.close("escape");
				break;
			case "Tab": {
				// Tab moves on and picks the typed text or the chosen row
				const meant = this.navigated || !!this.query;
				// ignore a row only hovered by the mouse
				const chosen = this.pointer_highlight
					? this.rows.find((r) => !r.option.disabled)
					: this.highlighted;
				const row = chosen && chosen.option && !chosen.option.disabled && chosen.option;
				const selects =
					typeof this.opts.tab_selects === "function"
						? this.opts.tab_selects({ navigated: this.navigated, query: this.query })
						: this.opts.tab_selects !== false;
				if (selects && meant && !this.rows_pending && row) {
					this.select(row);
				} else {
					this.close("tab");
				}
				this.replay_key(e);
				break;
			}
			default:
				if (!this.input && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
					// no search box: typing jumps to a row
					handled();
					if (this.pending_typeahead || this.rows_pending) {
						this.pending_typeahead = (this.pending_typeahead || "") + e.key;
					} else {
						this.typeahead(e.key);
					}
				} else if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "s") {
					// Ctrl+S: save the typed text first, then let the form save
					const committed = this.close("owner");
					if (committed && typeof committed.then === "function") {
						handled();
						// send Ctrl+S again once done, unless the dialog closed
						const dialog = window.cur_dialog;
						const save = (result) => {
							// false: the user did something else meanwhile
							if (result === false || window.cur_dialog !== dialog) return;
							this.replay_key(e);
						};
						committed.then(save, () => save());
					}
				} else if (!this.input && (e.ctrlKey || e.metaKey || e.altKey)) {
					// block other shortcuts, like an input does
					e.stopPropagation();
				}
		}
	}

	// send a panel key to the field's own handlers (e.g. Tab adds a grid row)
	replay_key(e) {
		// field removed: send the key to body
		const el = this.input_el && this.input_el.isConnected ? this.input_el : document.body;
		const copy = new KeyboardEvent("keydown", {
			key: e.key,
			code: e.code,
			shiftKey: e.shiftKey,
			ctrlKey: e.ctrlKey,
			metaKey: e.metaKey,
			altKey: e.altKey,
			bubbles: true,
			cancelable: true,
		});
		// jQuery handlers read keyCode
		for (const p of ["keyCode", "which"]) Object.defineProperty(copy, p, { value: e.keyCode });
		el.dispatchEvent(copy);
		if (copy.defaultPrevented) e.preventDefault();
	}

	typeahead(text) {
		clearTimeout(this.typeahead_timer);
		this.typeahead_timer = setTimeout(() => (this.typeahead_buffer = ""), 1000);
		const fresh = !this.typeahead_buffer;
		this.typeahead_buffer = (this.typeahead_buffer || "") + text.toLowerCase();
		const rows = this.rows.filter((r) => !r.option.disabled);
		const current = rows.indexOf(this.highlighted);
		const start = current === -1 ? 0 : current + (fresh ? 1 : 0);
		for (let i = 0; i < rows.length; i++) {
			const row = rows[(start + i) % rows.length];
			if (row.option.label.toLowerCase().startsWith(this.typeahead_buffer)) {
				this.highlight(row);
				this.navigated = true;
				this.pointer_highlight = false;
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
