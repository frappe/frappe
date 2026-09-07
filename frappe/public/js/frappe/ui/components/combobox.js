import { place, SIDES, ALIGNS } from "./position.js";
import { validated, is_thenable, is_group, icon_html } from "./utils.js";
import { normalize_options as normalize_menu_options } from "./menu.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ComboboxOption
 * @property {string} label Row text. Rendered as text, never HTML.
 * @property {string} value What get_value() returns when this row is picked.
 * @property {string} [description] Smaller muted second line under the label (the docname, search fields).
 * @property {string} [icon] Lucide icon name shown before the label.
 * @property {string} [image] Avatar image URL shown before the label (falls back to the label's initial).
 * @property {boolean} [avatar] Show an initial-letter avatar even without an image (keeps rows aligned when only some have pictures).
 * @property {{label: string, theme?: string}} [badge] Small badge after the label text.
 * @property {boolean} [disabled] Inert row, skipped by keyboard navigation.
 */

/**
 * @typedef {Object} ComboboxGroup
 * @property {string} group Heading text for the section.
 * @property {boolean} [hide_label] Keep the section border but hide the heading.
 * @property {ComboboxOption[]} options Rows in this section.
 */

/**
 * @typedef {Object} ComboboxCustomOption
 * @property {"custom"} type
 * @property {string} label Row text.
 * @property {string} [icon] Lucide icon name.
 * @property {function} onclick Called with { query, close, combobox }. The panel closes after unless keep_open is set.
 * @property {boolean} [keep_open]
 * @property {function} [condition] Called with { query }; return false to hide the row. Runs on every render, even when the query filtered everything else out.
 */

/**
 * @typedef {Object} ComboboxOpts
 * @property {Element|JQuery} [trigger] An existing element to use as the trigger. Omit to have one made.
 * @property {Array|function} options Rows: strings, ComboboxOption, ComboboxGroup or ComboboxCustomOption entries. A function is called with (query, { start }) on open and on every query change and may return the rows, a Promise of them, or `{ rows, has_more }` — the panel shows a loading state until it settles. With `filterable` on, a function is expected to be cheap (a preloaded list) and is called without debounce; returning the same array again skips re-processing it.
 * @property {number} [page_size] With a function `options`: when a call returns this many rows (or says `has_more`) there may be more, and scrolling near the end of the list calls it again with `start` advanced by `page_size` and appends the new rows (already-listed values are skipped; a page that adds nothing ends the paging).
 * @property {string} [value] Initial value.
 * @property {string} [placeholder="Select"] Trigger text when nothing is selected. With `value_input`, leave it out to keep the input's own placeholder attribute.
 * @property {string} [search_placeholder="Search..."] Placeholder of the search row.
 * @property {boolean} [filterable=true] Filter rows on the client as the user types. Turn off when `options` does the filtering (server search).
 * @property {boolean} [hide_search=false] No search row — for short lists that read like a plain select.
 * @property {boolean} [clearable=true] Show a clear (×) button on the trigger when a value is set; Backspace / Delete on the closed trigger clear too.
 * @property {boolean} [disabled=false]
 * @property {string} [empty_text="No results"] Shown when nothing matches.
 * @property {string[]|string|function} [filters] Filters the list is restricted by, shown as chips under the list ("Customer Group: Commercial"). A plain string is shown as one line of text. A function is called on every open and may return the value or a Promise of it. Rendered as text, never HTML.
 * @property {ComboboxCustomOption[]} [footer] Custom rows pinned under the list (Create new, app-specific actions).
 * @property {boolean} [match_trigger_width=true] Panel takes the trigger's width (never narrower than 240px, never wider than the viewport).
 * @property {"top"|"bottom"} [side="bottom"]
 * @property {"start"|"center"|"end"} [align="start"]
 * @property {number} [offset=4]
 * @property {string} [css_class] Extra classes on the trigger.
 * @property {boolean} [value_input=false] Render the trigger's value as an <input> (exposed as `input_el`) that refuses edits, instead of a span, so form code that reads, focuses or types into a real input keeps working.
 * @property {Array<{icon: string, title: string, href?: string, css_class?: string, onclick?: function}>} [actions] Extra ghost buttons on the trigger, after the clear button (e.g. "open record"). With `href` the action is a link. Elements are on `action_els` in the same order.
 * @property {function} [before_open] Called with the instance right before the panel is built — a chance to update `opts` (footer, placeholders, filters, hide_search, page_size) for this open.
 * @property {function} [on_change] Called with (value, option) after a pick or a clear.
 * @property {function} [on_open]
 * @property {function} [on_close] Called with the reason: "select" | "escape" | "outside" | "tab" | "owner".
 */

const EXIT_MS = 140; // keep in sync with es-menu-out in menu.css
const DEBOUNCE_MS = 300;
// the panel follows the trigger's width, but never narrower than this (a
// grid cell can be 80px wide) and never wider than the viewport
const MIN_PANEL_WIDTH = 240;
const VIEWPORT_PAD = 8;
// filter chips shown before the "+N more" chip
const MAX_FILTER_CHIPS = 4;
// how close to the end of the list (px) the next page starts loading
const LOAD_MORE_THRESHOLD = 48;
const BADGE_THEMES = ["gray", "blue", "green", "amber", "red", "violet", "orange"];
const COMPONENT = "Combobox";

let id_counter = 0;

function is_custom(entry) {
	return entry && typeof entry === "object" && entry.type === "custom";
}

// one row's canonical shape: strings become { label, value }
function normalize_option(entry) {
	if (entry == null) return null;
	if (typeof entry !== "object") {
		const text = String(entry);
		return { label: text, value: text };
	}
	const value = entry.value == null ? entry.label : entry.value;
	return { ...entry, label: entry.label == null ? String(value) : String(entry.label), value };
}

// { groups, custom }: the menu's group flattener does the layout work; this
// adds string rows and pulls the custom rows (Create new...) aside since
// they never take part in filtering
export function normalize_options(options) {
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

// a later page merged in place: unlabeled rows continue the previous
// unlabeled group, labeled groups stay separate sections; values already
// listed are dropped. Returns how many rows were new.
function merge_normalized(base, extra) {
	const seen = new Set(base.groups.flatMap((group) => group.options.map((o) => o.value)));
	let added = 0;
	for (const group of extra.groups) {
		const options = group.options.filter((o) => !seen.has(o.value));
		if (!options.length) continue;
		options.forEach((o) => seen.add(o.value));
		added += options.length;
		const last = base.groups[base.groups.length - 1];
		if (last && !last.group && !group.group) last.options.push(...options);
		else base.groups.push({ ...group, options });
	}
	base.custom.push(...extra.custom);
	return added;
}

// a source may answer with rows, or with { rows, has_more } when it knows
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

// label with the matched part wrapped in .es-combobox__match — text nodes
// and one span, never innerHTML
function fill_label(el, text, query) {
	const index = query ? text.toLowerCase().indexOf(query.toLowerCase()) : -1;
	if (index === -1) {
		el.textContent = text;
		return;
	}
	const mark = document.createElement("span");
	mark.className = "es-combobox__match";
	mark.textContent = text.slice(index, index + query.length);
	el.append(
		document.createTextNode(text.slice(0, index)),
		mark,
		document.createTextNode(text.slice(index + query.length))
	);
}

// the avatar / icon shown before a label, in rows and on the trigger
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
 * Pick one value from a searchable list: a trigger styled like a form
 * control, and a panel (an .es-menu with role=listbox) holding a search row,
 * the rows, and optional custom rows. Rows can carry an avatar or icon, a
 * muted description, and a badge. Enter / Space / ArrowDown open it; typing
 * on the focused trigger opens it with that text as the query.
 * @example
 * new frappe.ui.Combobox({
 *     trigger: this.$wrapper.find(".status-picker"),
 *     options: ["Open", "Working", "Closed"],
 *     on_change: (value) => this.set_status(value),
 * });
 */
frappe.ui.Combobox = class Combobox {
	/** @param {ComboboxOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.side = validated(opts.side, SIDES, "side", COMPONENT) || "bottom";
		this.align = validated(opts.align, ALIGNS, "align", COMPONENT) || "start";
		this.offset = opts.offset == null ? 4 : opts.offset;
		this.filterable = opts.filterable !== false;
		this.clearable = opts.clearable !== false;
		this.match_trigger_width = opts.match_trigger_width !== false;
		this.options = opts.options || [];
		this.value = opts.value == null ? null : opts.value;
		this.selected = null; // the option object behind this.value, when known
		this.normalized = null; // { groups, custom } of the last resolved options
		this.next_start = 0; // server offset of the next page for this query
		this.has_more = false;
		this.query = "";
		this.panel = null;
		this.rows = [];
		this.request_id = 0;
		this.id = `es-combobox-${++id_counter}`;

		this.make_trigger();
		this.set_display();
	}

	// ---- trigger ----

	make_trigger() {
		if (this.opts.trigger) {
			this.$trigger = $(this.opts.trigger);
			this.trigger_el = this.$trigger[0];
			this.trigger_el.classList.add("es-combobox");
		} else {
			this.trigger_el = document.createElement("div");
			this.trigger_el.className = "es-combobox";
			this.$trigger = $(this.trigger_el);
		}
		if (this.opts.css_class) this.trigger_el.classList.add(...this.opts.css_class.split(" "));
		const t = this.trigger_el;
		t.setAttribute("role", "combobox");
		t.setAttribute("aria-haspopup", "listbox");
		t.setAttribute("aria-expanded", "false");

		this.prefix_el = document.createElement("span");
		this.prefix_el.className = "es-combobox__prefix";
		this.prefix_el.hidden = true;

		if (this.opts.value_input) {
			// a real input for form controls. Not readonly (test drivers and
			// scripts refuse to type into those); instead every edit is
			// refused at beforeinput, so typing, paste and IME never land in
			// it — the keydown bubbles to the trigger and opens the panel,
			// where the search box takes over
			this.value_el = document.createElement("input");
			this.value_el.type = "text";
			this.value_el.setAttribute("autocomplete", "off");
			this.value_el.setAttribute("aria-readonly", "true");
			this.value_el.addEventListener("beforeinput", (e) => this.on_value_input(e));
			this.input_el = this.value_el;
		} else {
			this.value_el = document.createElement("span");
		}
		this.value_el.className = "es-combobox__value";

		// order, left to right: clear, then the owner's actions (open link...),
		// then the chevron — the more often a button is used, the closer it
		// sits to the text
		this.actions_el = document.createElement("span");
		this.actions_el.className = "es-combobox__actions";
		if (this.clearable) {
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
			icon_html("chevron-down", "es-combobox__chevron", COMPONENT)
		);

		this.set_disabled(!!this.opts.disabled);

		// a click right after a pointerdown is a mouse/touch open (animated);
		// anything else (Enter/Space) is a keyboard open (instant)
		this.last_pointerdown = 0;
		this.onpointerdown = () => (this.last_pointerdown = Date.now());
		this.onclick = (e) => {
			e.preventDefault();
			if (this.disabled) return;
			if (this.is_open) this.close("owner");
			else
				this.open({
					motion: Date.now() - this.last_pointerdown < 300 ? "animated" : "instant",
				});
		};
		this.onkeydown = (e) => {
			if (this.disabled || this.is_open) return;
			if (
				e.key === "Enter" ||
				e.key === " " ||
				e.key === "ArrowDown" ||
				e.key === "ArrowUp"
			) {
				e.preventDefault();
				this.open({ motion: "instant" });
			} else if (e.key === "Backspace" || e.key === "Delete") {
				// keyboard users clear here; the × button is out of the tab order
				if (!this.clearable || this.value == null) return;
				e.preventDefault();
				this.clear();
			} else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
				// type on the closed trigger: open and start the search with
				// that character, so tab-and-type data entry still works
				e.preventDefault();
				this.open({ motion: "instant", query: e.key });
			}
		};
		t.addEventListener("pointerdown", this.onpointerdown);
		t.addEventListener("click", this.onclick);
		t.addEventListener("keydown", this.onkeydown);
	}

	// an edit attempted on the value input: refused, and turned into the
	// same action a keydown would be — text opens the panel with it as the
	// query, a deletion clears. Covers input that never sends keydown
	// (virtual keyboards, IME composition, dictation, paste, test drivers).
	on_value_input(e) {
		e.preventDefault();
		if (this.disabled || this.is_open) return;
		if (e.inputType.startsWith("delete")) {
			if (this.clearable && this.value != null) this.clear();
		} else if (e.data && !this.opts.hide_search) {
			this.open({ motion: "instant", query: e.data });
		}
	}

	// one owner action: a ghost icon button, or a link when it has an href
	// (so middle-click / ctrl-click open a tab)
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

	update_clear_button() {
		if (!this.clear_btn) return;
		this.clear_btn.hidden = this.value == null || this.disabled;
	}

	// what the trigger shows: the selected option's label (and avatar/icon),
	// or the placeholder
	set_display() {
		const option = this.selected;
		const text = option ? option.label : this.value == null ? null : String(this.value);
		if (this.input_el) {
			this.input_el.value = text == null ? "" : text;
			// leave the input's own placeholder attribute alone unless one
			// was given here (form controls set theirs from the docfield)
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

	/**
	 * Set the value from code. Pass `label` (and `image` / `avatar`) when the
	 * option isn't in the current rows (a server-searched record), so the
	 * trigger can show it. Silent: no on_change.
	 */
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

	clear() {
		if (this.value == null) return;
		this.set_value(null, { silent: false });
	}

	find_option(value) {
		const groups = Array.isArray(this.options)
			? normalize_options(this.options).groups
			: this.normalized?.groups;
		return groups ? find_in(groups, value) : null;
	}

	// replace the rows (static lists); re-renders if open
	set_options(options) {
		this.options = options || [];
		if (this.selected == null && this.value != null)
			this.selected = this.find_option(this.value);
		this.set_display();
		if (this.is_open) this.load();
	}

	// ---- panel ----

	get is_open() {
		return !!this.panel;
	}

	// where keyboard focus lives while the panel is closed
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
		panel.className = "es-menu es-combobox__panel";
		panel.id = this.id;
		panel.setAttribute("role", "listbox");
		panel.setAttribute("tabindex", "-1");
		panel.setAttribute("data-motion", motion);
		if (this.trigger_el.id) panel.setAttribute("aria-labelledby", this.trigger_el.id);
		// "open" from here on: the async filters / options that start below
		// compare against this.panel to drop results for a panel that closed
		this.panel = panel;
		// a typed character seeds the search; without a search row there is
		// nowhere to see or clear it, so it is dropped
		this.query = this.opts.hide_search ? "" : query;
		this.stale = false;
		this.pending_activate = false;

		if (!this.opts.hide_search) {
			const search = document.createElement("div");
			search.className = "es-combobox__search";
			search.insertAdjacentHTML("beforeend", icon_html("search", "", COMPONENT));
			this.input = document.createElement("input");
			this.input.className = "es-combobox__input";
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
		this.list_el.className = "es-combobox__list";
		this.list_el.addEventListener("scroll", () => this.maybe_load_more(), { passive: true });
		panel.appendChild(this.list_el);

		// the filters the list is restricted by sit under the list, above
		// the custom rows, like the classic Link field's filter note
		this.filters_expanded = false;
		this.filters_el = document.createElement("div");
		this.filters_el.className = "es-combobox__filters";
		this.filters_el.hidden = true;
		panel.appendChild(this.filters_el);
		this.render_filters();

		this.footer_el = document.createElement("div");
		this.footer_el.className = "es-combobox__footer";
		this.footer_el.hidden = true;
		panel.appendChild(this.footer_el);

		// into <body> (no overflow: hidden ancestor can clip it), same as menus
		// and popovers; z-index puts it above dialogs
		document.body.appendChild(panel);
		this.trigger_el.setAttribute("aria-expanded", "true");
		this.trigger_el.setAttribute("aria-controls", panel.id);
		this.trigger_el.setAttribute("data-state", "open");

		this.onpanelkeydown = (e) => this.handle_keydown(e);
		this.onoutside = (e) => {
			if (panel.contains(e.target) || this.trigger_el.contains(e.target)) return;
			this.close("outside");
		};
		this.onreposition = () => this.reposition();
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
		const rect = this.trigger_el.getBoundingClientRect();
		// a fixed width (not min-width): long labels and filter chips must
		// truncate or wrap inside it, never widen the panel past the field
		const max_width = window.innerWidth - 2 * VIEWPORT_PAD;
		const width = this.match_trigger_width
			? Math.min(Math.max(Math.round(rect.width), MIN_PANEL_WIDTH), max_width)
			: null;
		this.panel.style.width = width ? `${width}px` : "";
		this.panel.style.minWidth = width ? "" : `${MIN_PANEL_WIDTH}px`;
		this.panel.style.maxWidth = `${max_width}px`;
		place(this.panel, rect, this.side, this.align, this.offset);
	}

	close(reason = "owner") {
		if (!this.panel) return;
		const panel = this.panel;
		this.panel = null;
		this.rows = [];
		this.highlighted = null;
		this.group_els = [];
		this.more_el = null;
		this.has_more = false;
		this.loading_more = null;
		this.source_rows = null;
		clearTimeout(this.debounce_timer);

		panel.removeEventListener("keydown", this.onpanelkeydown);
		document.removeEventListener("pointerdown", this.onoutside, { capture: true });
		window.removeEventListener("resize", this.onreposition);
		document.removeEventListener("scroll", this.onreposition, { capture: true });

		this.trigger_el.setAttribute("aria-expanded", "false");
		this.trigger_el.removeAttribute("aria-controls");
		this.trigger_el.removeAttribute("data-state");

		// keyboard closes return focus to the trigger; a click elsewhere
		// already moved focus and shouldn't have it stolen back
		if (reason === "escape" || reason === "tab" || reason === "select") {
			this.focus_el.focus({ preventScroll: true });
		}

		panel.setAttribute("data-state", "closed");
		setTimeout(() => panel.remove(), EXIT_MS + 50);
		this.opts.on_close && this.opts.on_close(reason);
	}

	toggle() {
		this.is_open ? this.close("owner") : this.open();
	}

	destroy() {
		this.close("owner");
		const t = this.trigger_el;
		if (!t) return;
		t.removeEventListener("pointerdown", this.onpointerdown);
		t.removeEventListener("click", this.onclick);
		t.removeEventListener("keydown", this.onkeydown);
	}

	// ---- rows ----

	on_query(query) {
		this.query = query;
		if (typeof this.options === "function" && !this.filterable) {
			// server-backed: debounce, then refetch. Until the new rows land
			// the old ones are stale — Enter must not commit one of them
			this.stale = true;
			this.highlight(null);
			clearTimeout(this.debounce_timer);
			this.debounce_timer = setTimeout(() => this.load(), DEBOUNCE_MS);
		} else if (typeof this.options === "function") {
			// a preloaded source: cheap, so refilter right away
			this.load();
		} else {
			this.render();
		}
	}

	// resolve the rows for the current query; async sources show a loading
	// state, and a response that isn't for the latest request is dropped
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

	// first page of rows for the current query
	set_rows(result) {
		const { rows, has_more } = unpack(result);
		// a preloaded source hands back the same array on every keystroke:
		// the normalized form is still good, only the filter changed
		if (rows !== this.source_rows) {
			this.source_rows = rows;
			this.normalized = normalize_options(rows);
		}
		this.next_start = this.opts.page_size || 0;
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

	// fetch the next page once the list is scrolled near its end; also right
	// after the "Loading more" row appears when the list isn't tall enough to
	// scroll at all
	maybe_load_more() {
		if (!this.has_more || !this.list_el) return;
		const list = this.list_el;
		const remaining = list.scrollHeight - list.scrollTop - list.clientHeight;
		if (remaining < LOAD_MORE_THRESHOLD) this.load_more();
	}

	// the next page for the current query, appended under the rows on screen
	load_more() {
		if (!this.panel || !this.has_more || this.loading_more) return;
		// one token per page request: a response for an earlier query, an
		// earlier open, or an earlier page is dropped
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
				const extra = normalize_options(rows);
				const added = merge_normalized(this.normalized, extra);
				this.source_rows = null;
				this.next_start += this.opts.page_size;
				// a page that adds nothing (a source ignoring `start`, a
				// translated doctype that returns everything at once) ends it
				this.has_more = added > 0 && this.page_allows_more(rows, has_more);
				this.append_rows(extra);
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

	// put a later page's rows on screen without rebuilding what's there (the
	// user's scroll position and highlight stay put)
	append_rows(extra) {
		const seen = new Set(this.rows.map((r) => r.option && r.option.value));
		for (const group of extra.groups) {
			const options = group.options.filter((o) => !seen.has(o.value));
			if (!options.length) continue;
			options.forEach((o) => seen.add(o.value));
			let group_el = this.group_els[this.group_els.length - 1];
			if (!group_el || group.group || group_el.dataset.group) {
				group_el = this.make_group_el({ ...group, options });
				this.list_el.appendChild(group_el);
			}
			const reserve = group_el.dataset.reserve === "1" || needs_icon_space(options);
			for (const option of options) {
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
		// when any row has an icon, iconless rows reserve the same space so
		// the labels line up (also for rows appended later)
		if (needs_icon_space(group.options)) group_el.dataset.reserve = "1";
		if (group.group && !group.hide_label) {
			const label = document.createElement("div");
			label.className = "es-menu__group-label";
			label.id = `${this.id}-g${this.group_els.length}`;
			label.textContent = group.group;
			group_el.setAttribute("aria-labelledby", label.id);
			group_el.appendChild(label);
		}
		this.group_els.push(group_el);
		return group_el;
	}

	// the "Loading more" row at the end of the list, present while there are
	// more pages; maybe_load_more() fetches when the list scrolls near it
	update_more_row() {
		if (!this.list_el) return;
		if (this.more_el) {
			this.more_el.remove();
			this.more_el = null;
		}
		if (!this.has_more || !this.rows.some((r) => r.option)) return;
		const more = document.createElement("div");
		more.className = "es-menu__loading";
		more.setAttribute("aria-hidden", "true");
		const spinner = document.createElement("span");
		spinner.className = "es-spinner";
		more.append(spinner, document.createTextNode(__("Loading more...")));
		this.list_el.appendChild(more);
		this.more_el = more;
		this.maybe_load_more();
	}

	set_loading(loading) {
		if (!this.panel) return;
		this.panel.setAttribute("aria-busy", loading ? "true" : "false");
		if (this.spinner) this.spinner.hidden = !loading;
		if (loading && !this.rows.length) {
			// first load: skeleton rows instead of an empty panel
			const rows = ["55%", "70%", "45%"]
				.map(
					(width) =>
						`<div class="es-combobox__skeleton">${frappe.ui.skeleton.html({
							css_class: "size-6 rounded-full",
						})}${frappe.ui.skeleton.html({ width, height: "12px" })}</div>`
				)
				.join("");
			this.list_el.innerHTML = `<div class="es-menu__group">${rows}</div>`;
		}
	}

	// the filters the list is restricted by: a row of chips (or one line of
	// text) under the list, so it's clear why a record isn't showing up
	render_filters() {
		if (!this.filters_el) return;
		let filters = this.opts.filters;
		if (typeof filters === "function") filters = filters(this);
		if (is_thenable(filters)) {
			const panel = this.panel;
			filters.then((value) => {
				if (this.panel !== panel) return;
				this.render_filters_value(value);
				this.reposition();
			});
			return;
		}
		this.render_filters_value(filters);
	}

	render_filters_value(filters) {
		const items = Array.isArray(filters) ? filters.filter(Boolean) : filters ? [filters] : [];
		this.filters_el.replaceChildren();
		this.filters_el.hidden = !items.length;
		if (!items.length) return;
		this.filters_el.insertAdjacentHTML("beforeend", icon_html("list-filter", "", COMPONENT));
		const label = document.createElement("span");
		label.className = "es-combobox__filters-label";
		label.textContent = __("Filtered by");
		this.filters_el.appendChild(label);
		if (!Array.isArray(filters)) {
			const text = document.createElement("span");
			text.className = "es-combobox__filters-text";
			text.textContent = filters;
			text.title = filters;
			this.filters_el.appendChild(text);
			return;
		}
		// past a handful, the rest hide behind "+N more" so the band stays
		// short; a click reveals them for this open
		const shown = this.filters_expanded ? items : items.slice(0, MAX_FILTER_CHIPS);
		for (const item of shown) {
			const chip = frappe.ui.badge({ label: String(item), size: "sm", title: String(item) });
			this.filters_el.appendChild(chip[0]);
		}
		const hidden = items.length - shown.length;
		if (hidden > 0) {
			const more = frappe.ui.badge({
				label: __("+{0} more", [hidden]),
				size: "sm",
				variant: "outline",
				title: items.slice(MAX_FILTER_CHIPS).join("\n"),
				css_class: "es-combobox__filters-more",
				attrs: { role: "button", tabindex: "-1" },
			});
			more.on("click", (e) => {
				e.stopPropagation();
				this.filters_expanded = true;
				this.render_filters_value(items);
				this.reposition();
			});
			// keep focus in the search input
			more.on("pointerdown", (e) => e.preventDefault());
			this.filters_el.appendChild(more[0]);
		}
	}

	/** Replace the filter chips (e.g. after a dependent field changed). */
	set_filters(filters) {
		this.opts.filters = filters;
		this.filters_expanded = false;
		if (!this.is_open) return;
		this.render_filters();
		this.reposition();
	}

	// (re)draw the list and footer from the resolved rows, applying the
	// client filter when enabled
	render(empty_text) {
		if (!this.panel) return;
		const { groups, custom } = this.normalized || { groups: [], custom: [] };
		const query = this.query;
		const filter = this.filterable ? (option) => matches(option, query) : () => true;

		this.rows = [];
		this.highlighted = null;
		this.group_els = [];
		this.more_el = null;
		this.list_el.replaceChildren();
		let visible = 0;
		for (const group of groups) {
			const options = group.options.filter(filter);
			if (!options.length) continue;
			const group_el = this.make_group_el({ ...group, options });
			const reserve = group_el.dataset.reserve === "1";
			for (const option of options) {
				group_el.appendChild(this.add_row({ option }, { reserve, query }));
			}
			this.list_el.appendChild(group_el);
			visible += options.length;
		}
		if (!visible) {
			const empty = document.createElement("div");
			empty.className = "es-menu__empty";
			const has_filters = this.filters_el && !this.filters_el.hidden;
			empty.textContent =
				empty_text ||
				(query && has_filters
					? __("No results for {0} within the current filters", [query])
					: query
					? __("No results for {0}", [query])
					: this.opts.empty_text || __("No results"));
			this.list_el.appendChild(empty);
		}

		// custom rows: shown when their condition allows (default: always)
		this.footer_el.replaceChildren();
		const shown = [...custom, ...(this.opts.footer || [])].filter((row) =>
			row.condition ? row.condition({ query }) : true
		);
		for (const row of shown) {
			this.footer_el.appendChild(this.add_row({ custom: row }, { query }));
		}
		this.footer_el.hidden = !shown.length;

		// keep the highlight on the current value if it's visible, else the
		// first row; with nothing matching, the first custom row (so Enter
		// creates)
		const current = this.rows.find((r) => r.option && r.option.value === this.value);
		this.highlight(current || this.rows.find((r) => !(r.option && r.option.disabled)) || null);
		this.stale = false;
		this.reposition();
		this.update_more_row();

		// Enter arrived while these rows were still loading (a scanner, a
		// fast typist): commit now, but only a real option, never a custom
		// row like "Create new" the user didn't see
		if (this.pending_activate) {
			this.pending_activate = false;
			if (this.highlighted && this.highlighted.option) this.activate(this.highlighted);
		}
	}

	// build one row element and register it in this.rows
	add_row(row, { reserve, query } = {}) {
		const option = row.option || { label: row.custom.label, icon: row.custom.icon };
		const el = document.createElement("button");
		el.type = "button";
		el.className = "es-menu__item";
		el.setAttribute("role", "option");
		el.setAttribute("tabindex", "-1");
		el.id = `${this.id}-r${this.rows.length}`;
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

		// title on top, name / search fields underneath — the same two lines
		// the classic Link dropdown shows, since a docname can be long. The
		// badge rides on the title line, right after the text, so it lines up
		// with its neighbours whether or not the row is the selected one.
		const label = document.createElement("span");
		label.className = "es-menu__label";
		fill_label(label, option.label || "", row.custom ? "" : query);
		if (option.badge && option.badge.label) {
			const theme = validated(option.badge.theme, BADGE_THEMES, "badge.theme", COMPONENT);
			label.insertAdjacentHTML(
				"beforeend",
				frappe.ui.badge.html({
					label: option.badge.label,
					theme: theme || "gray",
					size: "sm",
					css_class: "es-combobox__badge",
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
				icon_html("check", "es-combobox__check", COMPONENT)
			);
		}

		// pointer: hovering highlights, clicking picks. mousedown would blur
		// the search input before click fires, so keep focus where it is
		el.addEventListener("pointerdown", (e) => e.preventDefault());
		el.addEventListener("pointermove", () => this.highlight(row, { scroll: false }));
		el.addEventListener("click", () => this.activate(row));

		row.el = el;
		this.rows.push(row);
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
		// the pointer path never needs this: a hovered row is on screen
		if (scroll) row.el.scrollIntoView({ block: "nearest" });
	}

	step(direction, edge) {
		const rows = this.rows.filter((r) => !(r.option && r.option.disabled));
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
			const custom = row.custom;
			const close = () => this.close("select");
			custom.onclick && custom.onclick({ query: this.query, close, combobox: this });
			if (!custom.keep_open) close();
			return;
		}
		if (row.option.disabled) return;
		this.select(row.option);
	}

	select(option) {
		const changed = option.value !== this.value;
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
			case "PageDown":
				handled();
				this.step(1, true);
				break;
			case "PageUp":
				handled();
				this.step(-1, true);
				break;
			case "Enter":
				handled();
				// rows for the current query haven't arrived yet: hold the
				// Enter and commit when they do (see render)
				if (this.stale) this.pending_activate = true;
				else this.activate(this.highlighted);
				break;
			case "Escape":
				handled();
				this.close("escape");
				break;
			case "Tab":
				// don't trap focus: close and let the browser's own Tab move on
				// from the trigger. Typed text plus Tab picks the highlighted
				// match, the way the classic dropdown's tab-select did, so
				// tab-through data entry keeps working
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
					// behind the open panel; leave the browser default alone
					e.stopPropagation();
				}
		}
	}

	typeahead(char) {
		clearTimeout(this.typeahead_timer);
		this.typeahead_timer = setTimeout(() => (this.typeahead_buffer = ""), 1000);
		this.typeahead_buffer = (this.typeahead_buffer || "") + char.toLowerCase();
		const rows = this.rows.filter((r) => r.option && !r.option.disabled);
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
 * Convenience form: makes the trigger and wires the combobox in one call.
 * Returns the trigger element (append it wherever); the instance is on
 * `.data("es-combobox")` for get_value / set_value / open / close.
 * @param {ComboboxOpts} opts
 * @returns {JQuery}
 * @example toolbar.append(frappe.ui.combobox({
 *     placeholder: __("Status"),
 *     options: ["Open", "Closed"],
 *     on_change: (value) => this.filter(value),
 * }));
 */
frappe.ui.combobox = function (opts = {}) {
	const combobox = new frappe.ui.Combobox(opts);
	combobox.$trigger.data("es-combobox", combobox);
	return combobox.$trigger;
};

export default frappe.ui.combobox;
