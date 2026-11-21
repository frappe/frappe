frappe.provide("frappe.ui");

export const fill = (template, values) =>
	template.replace(/\{(\d)\}/g, (all, i) => values[i] ?? all);
export const SETTLE = { duration: 200, easing: "cubic-bezier(0.23, 1, 0.32, 1)" };
export const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * @typedef {Object} FilterChipOpts
 * @property {string} label The field the chip filters on (pre-translated). HTML-escaped.
 * @property {string} [icon] Lucide icon name shown before the label.
 * @property {string} [value] What the filter keeps, as text ("Unpaid, Overdue"). Empty: the chip is
 *   empty — dashed, with a chevron — and has no remove button.
 * @property {string} [template] The chip's words, translated as one sentence: {0} is the label,
 *   {1} the value (`__("{0} is not {1}")`), so each language keeps its own word order. Without it
 *   the chip reads "Label: value".
 * @property {Element|JQuery|function} [content] The picker that opens under the chip; a function is
 *   called fresh on every open, as Popover content is.
 * @property {Object} [input] Makes the chip a box typed into directly, with no picker:
 *   `{ placeholder, debounce = 250, onchange(text, chip) }`.
 * @property {function} [onremove] Called with the chip when × is pressed. An input chip clears its
 *   box and calls `input.onchange("")` instead.
 * @property {function} [onclick] For a chip with no `content`: called with the chip on click.
 * @property {function} [onpress] Called with the chip when it is clicked, before its picker opens;
 *   returning false keeps the picker shut, for a host that shows it somewhere else.
 * @property {function} [onopen] Called with the chip after its picker opens.
 * @property {function} [onclose] Called with the chip and Popover's close reason.
 * @property {string} [popover_class] Extra classes on the picker's panel, e.g. its width.
 * @property {string} [css_class] Extra classes on the chip.
 */

const icon = (name) => frappe.utils.icon(name, "sm", "", "", "", true);
const is_touch = () => window.matchMedia("(pointer: coarse)").matches;

/**
 * One filter, as a chip: empty (dashed, "Status ⌄") until it holds a value, then filled
 * ("Status: Unpaid, Overdue ×"). Clicking it opens its picker in a Popover; × removes it.
 * The chip only shows a filter — the caller owns the filter and calls `set()` when it changes.
 * @example
 * const chip = new frappe.ui.FilterChip({
 *     label: __("Status"),
 *     icon: "circle-dot",
 *     value: __("Unpaid, Overdue"),
 *     content: () => build_status_picker(),
 *     onremove: (chip) => clear_status_filter(),
 * });
 * chip.set({ value: "" });
 */
frappe.ui.FilterChip = class FilterChip {
	/** @param {FilterChipOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.value = "";
		this.template = "";
		this.locked = false;
		this.$wrapper = $('<div class="es-filter-chip" role="group"></div>');
		if (opts.css_class) this.$wrapper.addClass(opts.css_class);
		this.$wrapper.attr("aria-label", opts.label);

		opts.input ? this.make_input() : this.make_button();

		this.$remove = $(
			`<button type="button" class="es-filter-chip__remove">${icon("x")}</button>`
		)
			.attr("aria-label", __("Remove {0} filter", [opts.label]))
			.on("click", (e) => {
				// a mouse click leaves focus where it was; a key press keeps it on the chip
				if (e.detail) e.currentTarget.blur();
				this.remove();
			})
			.appendTo(this.$wrapper);

		this.set({ value: opts.value, template: opts.template });
		this.$wrapper.data("es-filter-chip", this);
	}

	make_button() {
		this.$main = $('<button type="button" class="es-filter-chip__main"></button>').appendTo(
			this.$wrapper
		);
		const tip = frappe.ui.tooltip(this.$main, { text: "", align: "start" }).data("es-tooltip");
		const set_tip = () => {
			const cut = [...this.$main[0].children].some((el) => el.scrollWidth > el.clientWidth);
			tip.set_text(this.sentence && (cut || this.more) ? this.sentence : "");
		};
		// before the tooltip's own listeners decide whether to show
		this.$main[0].addEventListener("pointerenter", set_tip, true);
		this.$main[0].addEventListener("focus", set_tip, true);
		if (this.opts.content) {
			this.make_popover();
			const popover = this.popover;
			popover.trigger_el.removeEventListener("click", popover.ontriggerclick);
			popover.trigger_el.addEventListener("click", (e) => {
				if (this.opts.onpress?.(this) === false) e.preventDefault();
				else popover.ontriggerclick(e);
			});
		} else if (this.opts.onclick) {
			this.$main.on("click", (e) => {
				this.opts.onclick(this, e);
			});
		}
	}

	make_input() {
		const input = this.opts.input;
		this.$main = $('<label class="es-filter-chip__field"></label>').appendTo(this.$wrapper);
		this.$prefix = $('<span class="es-filter-chip__label truncate"></span>');
		this.show_whole_name();
		this.$input = $(
			'<input type="text" class="es-filter-chip__input" autocomplete="off">'
		).attr({
			placeholder: input.placeholder ?? __("Search"),
			"aria-label": __("Search {0}", [this.opts.label]),
		});
		// the colon stays outside the name, so a name cut short still reads "Cheque/Reference…:"
		this.$colon = $('<span class="es-filter-chip__colon" aria-hidden="true">:</span>');
		this.$main.append(
			icon(this.opts.icon || "search"),
			this.$prefix,
			this.$colon,
			this.$input
		);

		const changed = frappe.utils.debounce(() => {
			this.typing = false;
			input.onchange?.(this.$input.val().trim(), this);
		}, input.debounce ?? 250);
		this.$input.on("input", () => {
			this.typing = true;
			this.value = this.$input.val().trim();
			this.render();
			changed();
		});
		this.$input.on("keydown", (e) => {
			if (this.locked && ["Enter", " ", "ArrowDown"].includes(e.key) && this.popover) {
				e.preventDefault();
				this.popover.open();
			} else if (e.key === "Escape") {
				// focus stays in the box; a change still waiting applies now
				changed.flush();
			}
		});
		this.changed = changed;

		// a locked box opens its content (a note) on click or tap instead of taking typing
		if (this.opts.content) {
			this.make_popover();
			this.popover.trigger_el.removeEventListener("click", this.popover.ontriggerclick);
			this.$main.on("click", (e) => {
				if (!this.locked) return;
				e.preventDefault();
				if (this.opts.onpress?.(this) !== false) this.popover.toggle();
			});
		}
	}

	// a tap on a cut-short name shows its tooltip, without moving into the box and raising the keyboard
	show_whole_name() {
		const tip = frappe.ui
			.tooltip(this.$prefix, { text: this.opts.label, only_on_overflow: true })
			.data("es-tooltip");
		this.$prefix.on("click", (e) => {
			const name = this.$prefix[0];
			if (!is_touch() || name.scrollWidth <= name.clientWidth) return;
			e.preventDefault();
			tip.show();
			setTimeout(() => tip.hide(), 2000);
		});
	}

	make_popover() {
		this.popover = new frappe.ui.Popover({
			trigger: this.$main,
			anchor: this.$wrapper,
			content: this.opts.content,
			side: "bottom",
			align: "start",
			css_class: ["es-filter-chip__panel", this.opts.popover_class]
				.filter(Boolean)
				.join(" "),
			on_open: (popover) => {
				popover.panel.setAttribute("aria-label", this.opts.label);
				this.opts.onopen?.(this);
			},
			on_close: (reason) => {
				// a typed box's label can't hold focus: return it to the box, so Tab goes on from there
				if (this.$input && ["escape", "tab"].includes(reason))
					this.$input.trigger("focus");
				this.opts.onclose?.(this, reason);
			},
		});
	}

	/**
	 * Show the filter's current value; an empty value empties the chip. `locked` is for a filter
	 * a typed box can't hold: the box is read-only and a click opens `content` instead.
	 */
	set({ value, template, locked, more, full } = {}) {
		if (value !== undefined) this.value = value || "";
		if (template !== undefined) this.template = template || "";
		if (more !== undefined) this.more = more || "";
		if (full !== undefined) this.full = full || "";
		if (locked !== undefined) this.locked = Boolean(locked);
		// someone typing keeps what they typed (a change still on its way, or the same text with
		// spaces round it); a change made elsewhere replaces it
		const keep =
			this.$input?.is(":focus") && (this.typing || this.$input.val().trim() === this.value);
		if (this.$input && !keep) this.$input.val(this.value);
		this.render();
	}

	render() {
		const applied = Boolean(this.value);
		this.$wrapper.attr("data-state", applied ? "applied" : "empty");
		this.$wrapper.attr("data-locked", this.locked ? "" : null);
		this.$remove.prop("hidden", !applied || (!this.opts.onremove && !this.opts.input));
		this.opts.input ? this.render_input(applied) : this.render_button(applied);
	}

	words() {
		return this.template || __("{0}: {1}");
	}

	render_button(applied) {
		const escape = frappe.utils.escape_html;
		const { label } = this.opts;
		const label_html = (text) => `<span class="es-filter-chip__label truncate">${text}</span>`;
		const parts = [this.opts.icon ? icon(this.opts.icon) : ""];
		if (applied) {
			let name = null;
			for (const piece of this.words().split(/(\{0\}|\{1\})/)) {
				const words = piece.trim();
				if (piece === "{0}") {
					name = escape(label);
					parts.push(null);
				} else if (piece === "{1}") {
					parts.push(
						`<span class="es-filter-chip__value truncate">${escape(this.value)}</span>`
					);
					if (this.more)
						parts.push(
							`<span class="es-filter-chip__more">${escape(this.more)}</span>`
						);
				} else if (
					words &&
					name !== null &&
					parts.at(-1) === null &&
					/^\p{P}+$/u.test(words)
				) {
					// a colon right after the name stays with it: "Status:"
					name += escape(words);
				} else if (words) {
					parts.push(`<span class="es-filter-chip__operator">${escape(words)}</span>`);
				}
			}
			parts[parts.indexOf(null)] = label_html(name ?? "");
		} else {
			parts.push(label_html(escape(label)), icon("chevron-down"));
		}
		// redrawn only when it changed: a chip redrawn between a press and its click loses the click
		const html = parts.join("");
		if (html !== this.drawn_html) this.$main.html((this.drawn_html = html));
		this.sentence = applied ? fill(this.words(), [label, this.full || this.value]) : "";
	}

	render_input() {
		this.$prefix.text(this.opts.label);
		this.$colon.prop("hidden", this.locked);
		this.$input
			.prop("readOnly", this.locked)
			.attr("aria-haspopup", this.locked ? "dialog" : null);
		// `size` for browsers without CSS field-sizing; it runs short for capitals, hence * 1.2
		const length = this.$input.val().length;
		this.$input.attr("size", Math.min(Math.max(Math.ceil(length * 1.2), 1), 30));
	}

	remove() {
		if (this.opts.input) {
			this.changed.cancel();
			this.typing = false;
			this.close();
			this.$input.val("");
			this.value = "";
			this.render();
			this.opts.input.onchange?.("", this);
			// a phone's keyboard would come up over the list
			if (!is_touch()) this.$input.trigger("focus");
			return;
		}
		const had_focus = this.$wrapper[0].contains(document.activeElement);
		this.close();
		this.opts.onremove?.(this);
		// its × hides once the chip is empty: focus stays on the chip
		if (had_focus && this.$wrapper[0].isConnected) this.focus();
	}

	/** Move focus to the chip: its box when typed into, else its button. Not on touch screens. */
	focus() {
		if (is_touch()) return;
		(this.$input || this.$main).trigger("focus");
	}

	open() {
		this.popover?.open();
	}

	/** Keep the chip at least as wide as it is now, so a shorter value moves nothing after it. */
	hold_width() {
		const width = this.$wrapper[0].getBoundingClientRect().width;
		if (width > parseFloat(this.$wrapper[0].style.minWidth || 0))
			this.$wrapper.css("min-width", width);
	}

	/** Let go of a held width; the chip eases to its own size. */
	release_width() {
		const el = this.$wrapper[0];
		if (!el.style.minWidth) return;
		const from = el.getBoundingClientRect().width;
		el.style.minWidth = "";
		const to = el.getBoundingClientRect().width;
		if (Math.abs(from - to) < 1 || still()) return;
		el.animate([{ minWidth: `${from}px` }, { minWidth: `${to}px` }], SETTLE);
	}

	close() {
		this.popover?.close("owner");
	}

	destroy() {
		this.popover?.destroy();
		this.$wrapper.remove();
	}
};

export default frappe.ui.FilterChip;
