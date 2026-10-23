import { FloatingPanel } from "./floating.js";
import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ComboboxOption
 * @property {string|number} value What the combobox holds once it is picked.
 * @property {string} [label] Row text; defaults to the value. Rendered as text, never HTML.
 * @property {string} [description] Smaller second line under the label.
 * @property {string} [icon] Lucide icon name before the label, also shown in the trigger once picked.
 * @property {boolean} [disabled] Shown, but can't be highlighted or picked.
 *
 * @typedef {Object} ComboboxCustomRow
 * An action row, like "Invite new member": it runs instead of setting a value.
 * @property {"custom"} type
 * @property {string} label
 * @property {string} [icon]
 * @property {string} [description]
 * @property {(ctx:{query:string, combobox:Combobox})=>void} onclick
 * @property {(ctx:{query:string})=>boolean} [condition] Decides when the row shows; otherwise it is filtered by label.
 * @property {boolean} [keep_open] Leave the panel open after it runs.
 *
 * @typedef {Object} ComboboxGroup
 * @property {string} group Heading above its options.
 * @property {boolean} [hide_label]
 * @property {Array<ComboboxOption|ComboboxCustomRow|string>} options
 *
 * @typedef {Object} ComboboxOpts
 * @property {Array<ComboboxOption|ComboboxCustomRow|ComboboxGroup|string>|((query:string, combobox:Combobox)=>Array|Promise<Array>)} options
 *   A list, filtered as the user types, or a function of the typed text for a server search.
 *   A function runs on open with "", then after typing; slower replies to older text are dropped.
 * @property {string|number|null} [value] The current choice.
 * @property {string} [value_label] Label for a value that isn't in the options yet, as with a server search.
 * @property {(value:string|number|null, option:ComboboxOption|null, combobox:Combobox)=>void} [on_change]
 * @property {"input"|"button"|Element|JQuery} [trigger="input"] "input" types into the field itself;
 *   "button" renders a button and moves the search box into the panel; an element of your own works like "button".
 * @property {"xs"|"sm"|"md"|"lg"} [size="sm"]
 * @property {"subtle"|"outline"|"ghost"} [variant="subtle"]
 * @property {string} [placeholder]
 * @property {string} [search_placeholder] Placeholder of the search box in the panel.
 * @property {boolean} [disabled]
 * @property {boolean} [filterable] Client-side filtering; on for a list, off for a function.
 * @property {boolean} [hide_search] Button triggers only: no search box in the panel.
 * @property {boolean} [open_on_focus]
 * @property {string} [empty_text]
 * @property {number} [debounce=200] Wait, in ms, after typing before a function source runs.
 * @property {(option:ComboboxOption)=>Element|null} [item_prefix] Leading element of a row, such as an avatar.
 * @property {(combobox:Combobox)=>Element|null} [footer] Pinned below the list.
 * @property {"top"|"right"|"bottom"|"left"} [side="bottom"]
 * @property {"start"|"center"|"end"} [align="start"]
 * @property {number} [offset=4]
 * @property {string} [css_class] Extra classes on the trigger.
 * @property {string} [panel_class] Extra classes on the panel.
 */

const SIZES = ["xs", "sm", "md", "lg"];
const VARIANTS = ["subtle", "outline", "ghost"];

let id_counter = 0;

/**
 * A searchable list that picks one value - frappe-ui's Combobox for the desk.
 * Focus stays in the search text the whole time; the highlighted row is announced
 * through aria-activedescendant, the WAI-ARIA combobox pattern. Arrows move without
 * wrapping, Home/End jump to the ends, Enter picks, Escape closes, and leaving the
 * field closes without picking.
 * Styles are in espresso/components/combobox.css.
 *
 * @example
 * const assignee = new frappe.ui.Combobox({
 *   placeholder: __("Assign to"),
 *   options: [
 *     { value: "jane@example.com", label: "Jane Doe", description: "jane@example.com" },
 *     { type: "custom", label: __("Invite new member"), icon: "user-plus", onclick: ({ query }) => invite(query) },
 *   ],
 *   on_change: (user) => assign(user),
 * });
 * wrapper.append(assignee.$el);
 */
frappe.ui.Combobox = class Combobox {
	/** @param {ComboboxOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.size = validated(opts.size, SIZES, "size", "Combobox") || "sm";
		this.variant = validated(opts.variant, VARIANTS, "variant", "Combobox") || "subtle";
		this.id = `es-combobox-${++id_counter}`;
		this.is_server = typeof opts.options === "function";
		this.filterable = opts.filterable ?? !this.is_server;
		this.options = this.is_server ? [] : opts.options || [];
		this.value = opts.value ?? null;
		this.selected = null;
		this.query = "";
		this.has_typed = false;
		this.loading = false;
		this.request = 0;
		this.items = [];
		this.active = -1;

		const custom = opts.trigger instanceof Element || opts.trigger?.jquery;
		this.mode = custom ? "custom" : opts.trigger === "button" ? "button" : "input";
		this.make_trigger(custom ? $(opts.trigger)[0] : null);

		this.floating = new FloatingPanel({
			anchor: this.el,
			class_name: ["es-combobox-panel", opts.panel_class].filter(Boolean).join(" "),
			side: opts.side,
			align: opts.align,
			offset: opts.offset,
			match_width: this.mode === "input",
			on_close: () => this.after_close(),
		});
		this.search = frappe.utils.debounce(() => this.load(), opts.debounce ?? 200);

		this.$el = $(this.el);
		this.$el.data("es-combobox", this);
		this.resolve_selected();
		this.render_trigger();
		this.set_disabled(Boolean(opts.disabled));
	}

	get is_open() {
		return this.floating.is_open;
	}

	get_value() {
		return this.value;
	}

	/** Change the choice without calling on_change. */
	set_value(value, option = null) {
		this.value = value ?? null;
		this.selected = option ? normalize_option(option) : null;
		this.resolve_selected();
		this.render_trigger();
	}

	/** Replace the list; for a function source, the next search replaces it again. */
	set_options(options) {
		this.options = options || [];
		this.resolve_selected();
		this.render_trigger();
		if (this.is_open) this.render_list(false);
	}

	set_disabled(disabled) {
		this.disabled = disabled;
		this.el.toggleAttribute("data-disabled", disabled);
		const control = this.input || (this.mode === "button" ? this.el : null);
		if (control) control.disabled = disabled;
		if (disabled) this.close();
	}

	/** Clear the choice and tell on_change. */
	clear() {
		this.commit(null, null);
	}

	focus(options) {
		(this.input || this.el).focus(options);
	}

	open(from_typing = false) {
		if (this.is_open || this.disabled) return;
		this.has_typed = from_typing;
		if (this.mode !== "input" && !from_typing) this.query = "";
		this.floating.open(this.make_panel());
		this.set_expanded(true);
		if (this.search_input) this.search_input.focus({ preventScroll: true });
		else if (this.mode !== "input") this.panel_el.focus({ preventScroll: true });
		this.load(!from_typing);
	}

	close() {
		this.floating.close("owner");
	}

	toggle() {
		this.is_open ? this.close() : this.open();
	}

	make_trigger(custom_el) {
		if (custom_el) {
			this.el = custom_el;
			this.el.setAttribute("aria-haspopup", "listbox");
			this.el.setAttribute("aria-expanded", "false");
			this.el.addEventListener("click", () => this.toggle());
			this.el.addEventListener("keydown", (e) => this.handle_trigger_key(e));
			return;
		}

		const root = document.createElement(this.mode === "button" ? "button" : "div");
		root.className = ["es-combobox", this.opts.css_class].filter(Boolean).join(" ");
		root.setAttribute("data-size", this.size);
		root.setAttribute("data-variant", this.variant);
		root.setAttribute("data-state", "closed");
		const chevron = frappe.utils.icon(
			"chevron-down",
			"sm",
			"",
			"",
			"es-combobox__chevron-icon"
		);

		if (this.mode === "button") {
			root.type = "button";
			root.setAttribute("data-mode", "button");
			root.setAttribute("aria-haspopup", "listbox");
			root.setAttribute("aria-expanded", "false");
			root.innerHTML = `<span class="es-combobox__prefix"></span>
				<span class="es-combobox__value"></span>
				<span class="es-combobox__chevron">${chevron}</span>`;
			root.addEventListener("click", () => this.toggle());
			root.addEventListener("keydown", (e) => this.handle_trigger_key(e));
		} else {
			root.innerHTML = `<span class="es-combobox__prefix"></span>
				<input class="es-combobox__input" type="text" autocomplete="off" role="combobox"
					aria-autocomplete="list" aria-expanded="false">
				<button type="button" class="es-combobox__chevron" tabindex="-1">${chevron}</button>`;
			this.input = root.querySelector("input");
			this.input.id = `${this.id}-input`;
			this.input.setAttribute("aria-controls", `${this.id}-list`);
			this.bind_input(this.input);
			this.input.addEventListener("focus", () => this.opts.open_on_focus && this.open());
			root.addEventListener("click", (e) => {
				if (e.target.closest(".es-combobox__chevron")) return;
				this.open();
			});
			const toggle = root.querySelector(".es-combobox__chevron");
			toggle.setAttribute("aria-label", __("Show options"));
			toggle.addEventListener("pointerdown", (e) => e.preventDefault());
			toggle.addEventListener("click", () => {
				this.input.focus();
				this.toggle();
			});
		}
		this.el = root;
	}

	handle_trigger_key(e) {
		if (e.isComposing || this.is_open) return;
		if (e.key === "ArrowDown" || e.key === "ArrowUp") {
			e.preventDefault();
			this.open();
		}
	}

	bind_input(input) {
		input.addEventListener("input", () => {
			this.query = input.value;
			this.has_typed = true;
			if (this.mode === "input" && !this.query && this.value != null)
				this.commit(null, null, false);
			if (!this.is_open) return this.open(true);
			this.is_server ? this.search() : this.render_list(false);
		});
		input.addEventListener("keydown", (e) => this.handle_key(e));
	}

	handle_key(e) {
		if (e.isComposing) return;
		if (!this.is_open) {
			if (e.key === "ArrowDown" || e.key === "ArrowUp") {
				e.preventDefault();
				this.open();
			}
			return;
		}
		const keys = {
			ArrowDown: () => this.move(1),
			ArrowUp: () => this.move(-1),
			Home: () => this.highlight(this.first_enabled()),
			End: () => this.highlight(this.last_enabled()),
			Enter: () => !(e.ctrlKey || e.metaKey || e.altKey) && this.pick_highlighted(),
			Escape: () => {
				e.stopPropagation();
				this.close();
				if (this.mode !== "input") this.el.focus();
			},
		};
		if (!keys[e.key]) return;
		e.preventDefault();
		keys[e.key]();
	}

	make_panel() {
		const panel = document.createElement("div");
		panel.className = "es-combobox-panel__body";
		panel.tabIndex = -1;
		this.panel_el = panel;
		this.search_input = null;

		if (this.mode !== "input" && !this.opts.hide_search) {
			const search = document.createElement("div");
			search.className = "es-combobox-panel__search";
			search.innerHTML = `<input class="es-combobox-panel__search-input" type="text" autocomplete="off"
				role="combobox" aria-autocomplete="list" aria-expanded="true">`;
			this.search_input = search.querySelector("input");
			this.search_input.placeholder = this.opts.search_placeholder || __("Search");
			this.search_input.setAttribute("aria-label", this.search_input.placeholder);
			this.search_input.setAttribute("aria-controls", `${this.id}-list`);
			this.bind_input(this.search_input);
			panel.append(search);
		} else if (this.mode !== "input") {
			panel.addEventListener("keydown", (e) => this.handle_key(e));
		}

		const list = document.createElement("div");
		list.className = "es-combobox-panel__list";
		list.id = `${this.id}-list`;
		list.setAttribute("role", "listbox");
		list.setAttribute("aria-orientation", "vertical");
		list.addEventListener("pointerdown", (e) => e.preventDefault());
		list.addEventListener("pointermove", (e) => {
			const row = e.target.closest(".es-combobox-panel__option");
			if (row && !row.hasAttribute("data-disabled"))
				this.highlight(this.items.indexOf(row), false);
		});
		list.addEventListener("pointerleave", () => this.highlight(-1));
		this.list = list;
		panel.append(list);

		const footer = this.opts.footer?.(this);
		if (footer) {
			const wrap = document.createElement("div");
			wrap.className = "es-combobox-panel__footer";
			wrap.append(footer);
			panel.append(wrap);
		}
		return panel;
	}

	load(initial = false) {
		if (!this.is_server) return this.render_list(initial);
		const request = ++this.request;
		this.loading = true;
		this.render_list(initial);
		Promise.resolve(this.opts.options(this.has_typed ? this.query : "", this)).then(
			(options) => {
				if (request !== this.request || !this.is_open) return;
				this.loading = false;
				this.options = options || [];
				this.resolve_selected();
				this.render_list(initial);
			},
			() => {
				if (request !== this.request || !this.is_open) return;
				this.loading = false;
				this.options = [];
				this.render_list(initial);
			}
		);
	}

	render_list(initial) {
		if (!this.list) return;
		const groups = this.get_visible_groups();
		const children = [];
		this.items = [];
		this.item_options = [];

		if (this.loading && !groups.length) {
			children.push(make_note("es-combobox-panel__loading", __("Loading..."), true));
		} else if (!groups.length) {
			children.push(
				make_note("es-combobox-panel__empty", this.opts.empty_text || __("No results"))
			);
		}
		groups.forEach((group, index) => children.push(this.make_group(group, index)));
		this.list.replaceChildren(...children);
		this.floating.reposition();

		const selected = initial ? this.item_options.findIndex((o) => this.is_selected(o)) : -1;
		this.highlight(
			selected !== -1 && !this.item_options[selected].disabled
				? selected
				: this.first_enabled()
		);
	}

	get_visible_groups() {
		const query = this.has_typed ? this.query.trim().toLowerCase() : "";
		return normalize_groups(this.options)
			.map((group) => {
				let options = group.options.filter((option) =>
					matches(option, query, this.filterable)
				);
				if (query && this.filterable) options = rank(options, query);
				return { ...group, options };
			})
			.filter((group) => group.options.length);
	}

	make_group(group, index) {
		const el = document.createElement("div");
		el.className = "es-combobox-panel__group";
		el.setAttribute("role", "group");
		if (group.group && !group.hide_label) {
			const label = document.createElement("div");
			label.className = "es-combobox-panel__group-label";
			label.id = `${this.id}-group-${index}`;
			label.textContent = group.group;
			el.setAttribute("aria-labelledby", label.id);
			el.append(label);
		}
		group.options.forEach((option) => el.append(this.make_option(option)));
		return el;
	}

	make_option(option) {
		const row = document.createElement("div");
		const index = this.items.length;
		row.className = "es-combobox-panel__option";
		row.id = `${this.id}-option-${index}`;
		row.setAttribute("role", "option");
		const selected = this.is_selected(option);
		row.setAttribute("aria-selected", String(selected));
		row.setAttribute("data-state", selected ? "checked" : "unchecked");
		row.setAttribute("data-size", this.size);
		if (option.type === "custom") row.setAttribute("data-custom", "");
		if (option.disabled) {
			row.setAttribute("data-disabled", "");
			row.setAttribute("aria-disabled", "true");
		}

		const prefix = this.make_item_prefix(option);
		if (prefix) {
			const wrap = document.createElement("span");
			wrap.className = "es-combobox-panel__option-prefix";
			wrap.append(prefix);
			row.append(wrap);
		}
		const text = document.createElement("span");
		text.className = "es-combobox-panel__option-text";
		text.innerHTML = `<span class="es-combobox-panel__option-label"></span>`;
		text.firstChild.textContent = option.label;
		if (option.description) {
			const description = document.createElement("span");
			description.className = "es-combobox-panel__option-description";
			description.textContent = option.description;
			text.append(description);
		}
		row.append(text);
		if (selected) {
			row.insertAdjacentHTML(
				"beforeend",
				`<span class="es-combobox-panel__check">${frappe.utils.icon("check", "sm")}</span>`
			);
		}

		row.addEventListener("click", () => !option.disabled && this.pick(option));
		this.items.push(row);
		this.item_options.push(option);
		return row;
	}

	make_item_prefix(option) {
		if (option.icon) return $(frappe.utils.icon(option.icon, "sm"))[0];
		if (option.type === "custom") return null;
		const prefix = this.opts.item_prefix?.(option);
		return prefix?.jquery ? prefix[0] : prefix || null;
	}

	highlight(index, scroll = true) {
		this.items.forEach((row, i) => row.toggleAttribute("data-highlighted", i === index));
		this.active = index;
		const field = this.search_input || this.input;
		const row = this.items[index];
		if (row) {
			field?.setAttribute("aria-activedescendant", row.id);
			if (scroll) row.scrollIntoView({ block: "nearest" });
		} else {
			field?.removeAttribute("aria-activedescendant");
		}
	}

	move(step) {
		if (this.active === -1) {
			return this.highlight(step > 0 ? this.first_enabled() : this.last_enabled());
		}
		for (let i = this.active + step; i >= 0 && i < this.items.length; i += step) {
			if (!this.item_options[i].disabled) return this.highlight(i);
		}
	}

	first_enabled() {
		return this.item_options.findIndex((option) => !option.disabled);
	}

	last_enabled() {
		for (let i = this.item_options.length - 1; i >= 0; i--) {
			if (!this.item_options[i].disabled) return i;
		}
		return -1;
	}

	pick_highlighted() {
		const option = this.item_options[this.active];
		if (option && !option.disabled) this.pick(option);
	}

	pick(option) {
		if (option.type === "custom") {
			const query = this.has_typed ? this.query : "";
			if (!option.keep_open) this.close();
			option.onclick?.({ query, combobox: this });
			return;
		}
		this.commit(option.value, option);
		this.close();
		if (this.mode !== "input") this.el.focus();
	}

	commit(value, option, render = true) {
		const changed = value !== this.value;
		this.value = value;
		this.selected = option;
		if (render) this.render_trigger();
		if (changed) this.opts.on_change?.(value, option, this);
	}

	after_close() {
		this.set_expanded(false);
		this.list = null;
		this.items = [];
		this.has_typed = false;
		this.loading = false;
		this.request++;
		this.query = "";
		this.render_trigger();
	}

	set_expanded(open) {
		this.el.setAttribute("data-state", open ? "open" : "closed");
		(this.input || this.el).setAttribute("aria-expanded", String(open));
	}

	resolve_selected() {
		if (this.value == null) return (this.selected = null);
		const found = normalize_groups(this.options)
			.flatMap((group) => group.options)
			.find((option) => option.type !== "custom" && option.value === this.value);
		if (found) this.selected = found;
		else if (this.selected?.value !== this.value) {
			this.selected = {
				value: this.value,
				label: this.opts.value_label || String(this.value),
			};
		}
	}

	is_selected(option) {
		return option.type !== "custom" && this.value != null && option.value === this.value;
	}

	render_trigger() {
		if (this.mode === "custom") return;
		const label = this.selected?.label ?? "";
		const prefix = this.el.querySelector(".es-combobox__prefix");
		prefix.replaceChildren(
			...(this.selected?.icon ? [$(frappe.utils.icon(this.selected.icon, "sm"))[0]] : [])
		);

		if (this.mode === "input") {
			this.input.placeholder = this.opts.placeholder || __("Select option");
			if (!this.is_open) this.input.value = label;
			return;
		}
		const value = this.el.querySelector(".es-combobox__value");
		value.textContent = label || this.opts.placeholder || __("Select option");
		value.toggleAttribute("data-placeholder", !label);
	}
};

function normalize_option(option) {
	if (option == null) return null;
	if (typeof option !== "object") return { value: option, label: String(option) };
	if (option.type === "custom") return { ...option, label: option.label || "" };
	if (option.value == null) return null;
	return { ...option, label: option.label ?? String(option.value) };
}

// Loose options between groups become groups without a heading, in source order.
function normalize_groups(options) {
	const groups = [];
	let loose = null;
	for (const entry of options || []) {
		if (
			entry &&
			typeof entry === "object" &&
			"group" in entry &&
			Array.isArray(entry.options)
		) {
			loose = null;
			groups.push({
				group: entry.group,
				hide_label: entry.hide_label,
				options: entry.options.map(normalize_option).filter(Boolean),
			});
			continue;
		}
		const option = normalize_option(entry);
		if (!option) continue;
		if (!loose) groups.push((loose = { group: "", hide_label: true, options: [] }));
		loose.options.push(option);
	}
	return groups.filter((group) => group.options.length);
}

function matches(option, query, filterable) {
	if (option.type === "custom") {
		if (option.condition) return Boolean(option.condition({ query }));
		return !query || option.label.toLowerCase().includes(query);
	}
	if (!query || !filterable) return true;
	return (
		option.label.toLowerCase().includes(query) ||
		String(option.value).toLowerCase().includes(query)
	);
}

// Exact, then starts with, then a word starts with, then anywhere; custom rows keep their place.
function rank(options, query) {
	const score = (option) => {
		const label = option.label.toLowerCase();
		if (label === query) return 0;
		if (label.startsWith(query)) return 1;
		if (label.split(/[^\p{L}\p{N}]+/u).some((word) => word.startsWith(query))) return 2;
		return 3;
	};
	const ranked = options
		.map((option, index) => ({
			option,
			index,
			score: option.type === "custom" ? null : score(option),
		}))
		.filter((entry) => entry.score !== null)
		.sort((a, b) => a.score - b.score || a.index - b.index)
		.map((entry) => entry.option);
	const result = [];
	options.forEach((option) => result.push(option.type === "custom" ? option : ranked.shift()));
	return result;
}

function make_note(class_name, text, spinner = false) {
	const note = document.createElement("div");
	note.className = class_name;
	if (spinner) {
		const icon = document.createElement("span");
		icon.className = "es-spinner";
		icon.setAttribute("aria-hidden", "true");
		note.append(icon);
		note.setAttribute("role", "status");
	}
	note.append(document.createTextNode(text));
	return note;
}

/**
 * Returns the trigger element; the instance is on `.data("es-combobox")`.
 * @param {ComboboxOpts} opts
 * @returns {JQuery}
 */
frappe.ui.combobox = (opts) => new frappe.ui.Combobox(opts).$el;

export default frappe.ui.combobox;
