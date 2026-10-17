frappe.provide("frappe.ui");

/**
 * @typedef {Object} ComboboxOption
 * @property {string} label Row text. Rendered as text, never HTML.
 * @property {*} [value] What on_select receives. Defaults to the label.
 * @property {string} [icon] Lucide icon name shown before the label.
 */

/**
 * @typedef {Object} ComboboxOpts
 * @property {Element|JQuery} trigger The element that opens it.
 * @property {function} options Called with the typed text; returns ComboboxOption[] (or strings),
 *     or a Promise of them. Filtering is its job, so it can ask the server.
 * @property {function} on_select Called with (value, { created }) when a row is picked.
 * @property {boolean|function} [allow_create=false] Offer the typed text as a new value when nothing matches it exactly. A function gets the typed text and returns whether it may be created.
 * @property {function} [create_label] Row text for that offer, from the typed text. Default: Create "{0}".
 * @property {string} [placeholder]
 * @property {string} [empty_text] Shown when there are no rows.
 * @property {"top"|"right"|"bottom"|"left"} [side="bottom"]
 * @property {"start"|"center"|"end"} [align="start"]
 * @property {string} [css_class] Extra classes on the panel.
 */

/**
 * A searchable list on a trigger: type to filter, pick a row, or (with
 * allow_create) add what you typed. The panel is a frappe.ui.Popover (placement,
 * Escape, click-outside, focus return) and its rows wear the menu's styles, so it
 * reads like a Dropdown with a search field on top. Keyboard: the input keeps
 * focus; ↑/↓ move the active row (aria-activedescendant), Enter picks it.
 * @example
 * new frappe.ui.Combobox({
 *     trigger: $tag_button,
 *     placeholder: __("Add a tag"),
 *     allow_create: true,
 *     options: (txt) => frappe.xcall("frappe.desk.doctype.tag.tag.get_tags", { doctype, txt }),
 *     on_select: (tag) => add_tag(tag),
 * });
 */
frappe.ui.Combobox = class Combobox {
	/** @param {ComboboxOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.id = `es-combobox-${++frappe.ui.Combobox.counter}`;
		this.popover = new frappe.ui.Popover({
			trigger: opts.trigger,
			side: opts.side,
			align: opts.align,
			css_class: ["es-combobox", opts.css_class].filter(Boolean).join(" "),
			content: () => this.make(),
			// unlike Popover, focus the input
			on_open: () => this.$input.trigger("focus"),
		});
	}

	make() {
		this.rows = [];
		this.active = -1;
		const $root = $(`<div>
			<input type="text" class="form-control es-combobox__input" role="combobox"
				aria-autocomplete="list" aria-expanded="true" aria-controls="${this.id}"
				autocomplete="off">
			<div class="es-combobox__list" role="listbox" id="${this.id}"></div>
		</div>`);
		const placeholder = this.opts.placeholder || __("Search");
		this.$input = $root
			.find("input")
			.attr({ placeholder, "aria-label": placeholder })
			.on(
				"input",
				frappe.utils.debounce(() => this.load(), 150)
			)
			.on("keydown", (e) => this.handle_keydown(e));
		this.$list = $root.find(".es-combobox__list");
		this.load();
		return $root[0];
	}

	async load() {
		const txt = this.$input.val().trim();
		const request = (this.request = {});
		let options = await this.opts.options(txt);
		if (request !== this.request) return;
		this.loaded_txt = txt;
		options = (options || []).map((o) => (typeof o === "string" ? { label: o } : o));

		const rows = options.map((o) => ({ ...o, value: o.value ?? o.label }));
		const exact = rows.some((r) => r.label.toLowerCase() === txt.toLowerCase());
		const allow_create =
			typeof this.opts.allow_create === "function"
				? this.opts.allow_create(txt)
				: this.opts.allow_create;
		if (allow_create && txt && !exact) {
			rows.push({
				label: this.opts.create_label
					? this.opts.create_label(txt)
					: __('Create "{0}"', [txt]),
				value: txt,
				icon: "plus",
				created: true,
			});
		}
		this.render(rows);
	}

	render(rows) {
		this.rows = rows;
		this.$list.empty();
		if (!rows.length) {
			$('<div class="es-menu__empty" role="presentation"></div>')
				.text(this.opts.empty_text || __("No results"))
				.appendTo(this.$list);
		}
		rows.forEach((row, i) => {
			const $row = $(`<div class="es-menu__item" role="option" id="${this.id}-${i}">
				${row.icon ? frappe.utils.icon(row.icon, "sm") : ""}
				<span class="es-menu__label"></span>
			</div>`);
			$row.find(".es-menu__label").text(row.label);
			$row.on("pointerenter", () => this.set_active(i));
			// keep focus in the input
			$row.on("mousedown", (e) => e.preventDefault());
			$row.on("click", () => this.select(i));
			this.$list.append($row);
		});
		this.set_active(rows.length ? 0 : -1);
	}

	set_active(index) {
		this.active = index;
		this.$list.children(".es-menu__item").each((i, el) => {
			el.toggleAttribute("data-highlighted", i === index);
			el.setAttribute("aria-selected", String(i === index));
			if (i === index) el.scrollIntoView({ block: "nearest" });
		});
		this.$input.attr("aria-activedescendant", index >= 0 ? `${this.id}-${index}` : null);
	}

	async handle_keydown(e) {
		const count = this.rows.length;
		if (e.key === "ArrowDown" || e.key === "ArrowUp") {
			e.preventDefault();
			if (!count) return;
			const step = e.key === "ArrowDown" ? 1 : -1;
			this.set_active((this.active + step + count) % count);
		} else if (e.key === "Enter") {
			e.preventDefault();
			// the rows can still be for earlier text (debounce, server round trip)
			if (this.$input.val().trim() !== this.loaded_txt) await this.load();
			if (this.active >= 0) this.select(this.active);
		}
	}

	select(index) {
		const row = this.rows[index];
		if (!row) return;
		this.popover.close("owner");
		const trigger = this.popover.trigger_el;
		if (!trigger.disabled) trigger.focus({ preventScroll: true });
		this.opts.on_select && this.opts.on_select(row.value, { created: Boolean(row.created) });
	}
};

frappe.ui.Combobox.counter = 0;
