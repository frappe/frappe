import { icon_html } from "./utils.js";

frappe.provide("frappe.ui");

const COMPONENT = "MultiCombobox";

function to_option(entry) {
	if (entry && typeof entry === "object") {
		const value = entry.value == null ? entry.label : entry.value;
		return {
			...entry,
			value,
			label: entry.label == null ? String(value) : String(entry.label),
		};
	}
	return { value: entry, label: String(entry) };
}

/**
 * @typedef {Object} MultiComboboxOpts
 * Everything ComboboxOpts takes, with these changes:
 * @property {Array} [value] Initial values, as plain values or { value, label } options.
 * @property {boolean} [one_line=false] Keep the pills on one line; the rest show as +N.
 * @property {function} [pill_href] Called with a value; its pill links there.
 * @property {function} [on_change] Called with (values, option, { added }).
 */

/**
 * Pick several values: a pill per value in the field, a checkbox per row in the panel.
 * The panel stays open while picking; Esc, Tab or a click outside closes it.
 * @example
 * new frappe.ui.MultiCombobox({
 *     options: ["Open", "Working", "Closed"],
 *     on_change: (values) => this.set_statuses(values),
 * });
 */
frappe.ui.MultiCombobox = class MultiCombobox extends frappe.ui.Combobox {
	/** @param {MultiComboboxOpts} opts */
	constructor(opts = {}) {
		// Tab only leaves; the pills and Clear all replace the × button
		super({
			...opts,
			value: null,
			value_input: true,
			tab_selects: false,
			clear_button: false,
		});
		this.set_value(opts.value || []);
	}

	// ---- trigger ----

	make_trigger() {
		this.values = [];
		this.picked = new Map(); // value -> option shown on its pill
		this.pinned = []; // values listed under Selected while the panel is open
		super.make_trigger();
		const t = this.trigger_el;
		t.classList.add("es-combobox--multi");
		t.toggleAttribute("data-one-line", !!this.opts.one_line);

		this.pills_el = document.createElement("span");
		this.pills_el.className = "es-combobox__pills flex flex-1 min-w-0 items-center gap-1";
		this.value_el.replaceWith(this.pills_el);
		this.value_el.classList.remove("truncate");
		this.more_el_pill = frappe.ui.badge({
			variant: "outline",
			css_class: "es-combobox__more",
		})[0];
		this.more_el_pill.hidden = true;
		this.pills_el.append(this.more_el_pill, this.value_el);

		this.pills_el.addEventListener("pointerdown", (e) => {
			// keep focus where it is, and don't count it as a press on the field
			if (e.target.closest("[data-remove]")) e.preventDefault();
			if (e.target.closest("[data-remove], a")) e.stopPropagation();
		});
		this.pills_el.addEventListener("click", (e) => {
			const remove = e.target.closest("[data-remove]");
			if (remove) {
				e.preventDefault();
				e.stopPropagation();
				if (!this.disabled) this.remove_value(this.values[Number(remove.dataset.remove)]);
			} else if (e.target.closest("a")) {
				e.stopPropagation();
			}
		});
		// Backspace on the closed field removes the last pill
		t.addEventListener(
			"keydown",
			(e) => {
				if (this.is_open || this.disabled || e.isComposing || !this.values.length) return;
				if (e.key !== "Backspace" && e.key !== "Delete") return;
				e.preventDefault();
				e.stopPropagation();
				this.remove_last();
			},
			true
		);

		if (this.opts.one_line) {
			// a removed field stops being watched, so it can be freed
			this.fit_observer = new ResizeObserver(() => {
				if (t.isConnected) return this.fit_pills();
				this.fit_observer.disconnect();
				this.fit_watching = false;
			});
			this.watch_width();
		}
	}

	watch_width() {
		if (this.fit_watching) return;
		this.fit_observer.observe(this.trigger_el);
		this.fit_watching = true;
	}

	on_value_input(e) {
		const typing = e.isComposing || e.inputType === "insertCompositionText";
		if (!typing && e.inputType.startsWith("delete")) {
			e.preventDefault();
			if (!this.disabled && !this.is_open) this.remove_last();
			return;
		}
		super.on_value_input(e);
	}

	set_disabled(disabled) {
		super.set_disabled(disabled);
		// no × on the pills of a disabled field
		if (this.pills_el) this.set_display();
	}

	set_display() {
		if (!this.pills_el) return;
		for (const el of this.pills_el.querySelectorAll(".es-combobox__pill")) el.remove();
		this.more_el_pill.before(
			...this.values.map((value, index) => this.make_pill(value, index))
		);
		this.input_el.value = "";
		if (this.opts.placeholder != null) this.input_el.placeholder = this.opts.placeholder;
		this.value_el.toggleAttribute("data-placeholder", !this.values.length);
		this.trigger_el.toggleAttribute("data-has-values", !!this.values.length);
		this.prefix_el.hidden = true;
		this.fit_pills();
	}

	make_pill(value, index) {
		const option = this.picked.get(value) || to_option(value);
		const pill = frappe.ui.badge({ variant: "outline", css_class: "es-combobox__pill" })[0];
		pill.title = option.label;
		const href = this.opts.pill_href && this.opts.pill_href(value);
		const text = document.createElement(href ? "a" : "span");
		text.className = "truncate";
		text.textContent = option.label;
		if (href) {
			text.href = href;
			text.tabIndex = -1;
		}
		pill.appendChild(text);
		if (!this.disabled) {
			const remove = document.createElement("button");
			remove.type = "button";
			remove.className = "es-badge__affix es-combobox__pill-remove";
			remove.tabIndex = -1;
			remove.dataset.remove = String(index);
			remove.setAttribute("aria-label", __("Remove {0}", [option.label]));
			remove.innerHTML = icon_html("x", "", COMPONENT);
			pill.appendChild(remove);
		}
		return pill;
	}

	// one line: hide the pills that don't fit and count them on +N
	fit_pills() {
		if (!this.opts.one_line || !this.pills_el) return;
		// drawn again after being removed: watch it again
		if (this.trigger_el.isConnected) this.watch_width();
		const pills = [...this.pills_el.querySelectorAll(".es-combobox__pill")];
		pills.forEach((pill) => (pill.hidden = false));
		this.more_el_pill.hidden = true;
		const overflows = () => this.pills_el.scrollWidth > this.pills_el.clientWidth + 1;
		let hidden = 0;
		for (let i = pills.length - 1; i > 0 && overflows(); i--) {
			pills[i].hidden = true;
			this.more_el_pill.hidden = false;
			this.more_el_pill.textContent = `+${++hidden}`;
		}
	}

	// ---- value ----

	get_value() {
		return this.values.slice();
	}

	/** Set the values from code: plain values, or { value, label } options for labels not in the rows. */
	set_value(values) {
		const next = [];
		const picked = new Map();
		for (const entry of values || []) {
			if (entry == null || entry === "") continue;
			let option = to_option(entry);
			if (picked.has(option.value)) continue;
			// a plain value keeps the label already known for it
			if (typeof entry !== "object") {
				option = this.picked.get(option.value) || this.find_option(option.value) || option;
			}
			picked.set(option.value, option);
			next.push(option.value);
		}
		this.values = next;
		this.picked = picked;
		this.value = next.length ? next.slice() : null;
		this.set_display();
		this.sync_rows();
		return this;
	}

	add_value(entry) {
		const option = to_option(entry);
		if (this.picked.has(option.value)) return;
		this.values.push(option.value);
		this.picked.set(option.value, option);
		this.changed(option, true);
	}

	remove_value(value) {
		const option = this.picked.get(value);
		if (!option) return;
		this.values = this.values.filter((v) => v !== value);
		this.picked.delete(value);
		this.changed(option, false);
	}

	remove_last() {
		if (this.values.length) this.remove_value(this.values[this.values.length - 1]);
	}

	/** Remove every value. */
	clear() {
		if (!this.values.length) return;
		this.values = [];
		this.picked = new Map();
		this.changed(null, false);
	}

	changed(option, added) {
		this.value = this.values.length ? this.values.slice() : null;
		this.set_display();
		this.sync_rows();
		// the pills may have changed the field's height
		this.reposition();
		this.opts.on_change && this.opts.on_change(this.get_value(), option, { added });
	}

	// ---- panel ----

	open(opts) {
		if (this.panel) return;
		this.pinned = this.values.slice();
		super.open(opts);
		if (!this.panel) return;
		this.panel.setAttribute("aria-multiselectable", "true");

		this.status_el = document.createElement("div");
		this.status_el.className =
			"es-combobox__status flex items-center justify-between gap-2 shrink-0 ps-3 pe-1 py-1 border-t border-outline-gray-1 text-p-sm text-ink-gray-5";
		this.status_text = document.createElement("span");
		this.status_clear = frappe.ui.button({
			label: __("Clear all"),
			variant: "ghost",
			size: "xs",
			attrs: { tabindex: "-1" },
			onclick: () => this.clear(),
		})[0];
		// keep focus in the search box
		this.status_clear.addEventListener("pointerdown", (e) => e.preventDefault());
		this.status_el.append(this.status_text, this.status_clear);
		this.panel.appendChild(this.status_el);
		this.update_status();
		this.reposition();
	}

	close(reason) {
		const committed = super.close(reason);
		this.status_el = null;
		return committed;
	}

	on_query(query) {
		// back to no search: what's picked now moves under Selected
		if (!query) this.pinned = this.values.slice();
		super.on_query(query);
	}

	/** Replace the search text, e.g. after the typed text was added as a value. */
	set_query(query) {
		if (!this.input) return;
		this.input.value = query;
		this.on_query(query);
	}

	update_status() {
		if (!this.status_el) return;
		const count = this.values.length;
		this.status_text.textContent = count
			? __("{0} selected", [count])
			: __("Nothing selected");
		this.status_clear.hidden = !count || this.disabled;
	}

	// ---- rows ----

	is_picked(option) {
		return this.picked.has(option.value);
	}

	// a checkbox before every row; CSS ticks it from aria-selected
	mark_row(el) {
		const check = document.createElement("span");
		check.className = "es-combobox__check";
		check.setAttribute("aria-hidden", "true");
		check.innerHTML = icon_html("check", "", COMPONENT);
		el.prepend(check);
	}

	// tick the rows on screen without redrawing them, so nothing moves
	sync_rows() {
		for (const row of this.rows || []) {
			row.el.setAttribute("aria-selected", this.is_picked(row.option) ? "true" : "false");
		}
		this.update_status();
	}

	// without a search: Selected on top, the rest under All; a search keeps the list as it is
	view_groups(groups) {
		if (this.query || !this.pinned.length) return groups;
		// loaded rows carry the best label and image
		const loaded = new Map(groups.flatMap((group) => group.options).map((o) => [o.value, o]));
		const selected = this.pinned.map(
			(value) => loaded.get(value) || this.picked.get(value) || to_option(value)
		);
		return [{ group: __("Selected"), options: selected }, ...this.unpinned(groups)];
	}

	// highlight the first row to add: Enter on a Selected row would remove it
	render(empty_text) {
		// an Enter pressed while loading waits until the highlight has moved
		const pending_enter = this.pending_activate;
		this.pending_activate = false;
		super.render(empty_text);
		let target = this.highlighted;
		if (!this.query && this.pinned.length && !this.navigated) {
			const pinned = new Set(this.pinned);
			target = this.rows.find((r) => !pinned.has(r.option.value) && !r.option.disabled);
			if (target) this.highlight(target, { scroll: false });
		}
		// every row already picked: a queued Enter is dropped rather than removing one
		if (pending_enter && target && target.option) this.activate(target);
	}

	// a page loaded on scroll goes under All, without the values already under Selected
	append_rows(groups) {
		super.append_rows(this.query || !this.pinned.length ? groups : this.unpinned(groups));
	}

	// the groups without the Selected values; rows with no group go under All
	unpinned(groups) {
		const pinned = new Set(this.pinned);
		return groups
			.map((group) => ({
				...group,
				group: group.group || __("All"),
				options: group.options.filter((o) => !pinned.has(o.value)),
			}))
			.filter((group) => group.options.length);
	}

	// a tick or untick keeps the panel open
	select(option) {
		if (this.is_picked(option)) this.remove_value(option.value);
		else this.add_value(option);
	}

	// custom rows with keep_open (e.g. "Use …") leave the panel open
	activate(row) {
		if (row && row.custom && row.custom.keep_open) {
			row.custom.onclick && row.custom.onclick({ query: this.query, combobox: this });
			return;
		}
		super.activate(row);
	}

	handle_keydown(e) {
		// Backspace in an empty search removes the last pill
		const empty_search = this.input && !this.input.value;
		if (e.key === "Backspace" && empty_search && this.values.length && !e.isComposing) {
			e.preventDefault();
			e.stopPropagation();
			this.remove_last();
			return;
		}
		super.handle_keydown(e);
	}
};

/**
 * Makes the trigger and wires the multi combobox in one call. The instance is on
 * `.data("es-combobox")`.
 * @param {MultiComboboxOpts} opts
 * @returns {JQuery}
 */
frappe.ui.multi_combobox = function (opts = {}) {
	return new frappe.ui.MultiCombobox(opts).$trigger;
};

export default frappe.ui.multi_combobox;
