import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} DatePickerAction
 * A shortcut in the panel's sidebar, such as "Tomorrow".
 * @property {string} label
 * @property {(picker:DatePicker)=>void} onclick Call picker.set_date() or picker.clear().
 *
 * @typedef {Object} DatePickerOpts
 * @property {string} [value] The date, as YYYY-MM-DD, or "".
 * @property {(value:string, picker:DatePicker)=>void|Promise} [on_change] Runs when the date changes; "" when cleared.
 * @property {Element|JQuery} [trigger] An element of your own that opens the calendar, in place of the text field.
 * @property {"xs"|"sm"|"md"|"lg"} [size="sm"]
 * @property {"subtle"|"outline"|"ghost"} [variant="subtle"]
 * @property {string} [placeholder]
 * @property {string} [format] Moment format for the text field; the user's date format by default.
 * @property {boolean} [typeable=true] Dates can be typed as well as picked.
 * @property {boolean} [clearable=true] Emptying the field clears the date; otherwise it falls back to today.
 * @property {boolean} [keep_open] Stay open after a date is picked.
 * @property {boolean} [disabled]
 * @property {boolean} [open_on_focus]
 * @property {string} [min] Earliest date that can be picked, as YYYY-MM-DD.
 * @property {string} [max] Latest date that can be picked, as YYYY-MM-DD.
 * @property {(date:string)=>boolean} [is_date_unavailable] Return true to block a date (YYYY-MM-DD).
 * @property {DatePickerAction[]|((picker:DatePicker)=>DatePickerAction[])} [actions] Shortcuts beside the calendar.
 * @property {"top"|"right"|"bottom"|"left"} [side="bottom"]
 * @property {"start"|"center"|"end"} [align="start"]
 * @property {number} [offset=4]
 * @property {string} [css_class] Extra classes on the text field's wrapper.
 */

const SIZES = ["xs", "sm", "md", "lg"];
const VARIANTS = ["subtle", "outline", "ghost"];
const VALUE_FORMAT = "YYYY-MM-DD";

/**
 * A text field that opens a month calendar - frappe-ui's DatePicker for the desk.
 * Dates show and parse in the user's date format and weeks start on the system's
 * first day; the value is always YYYY-MM-DD. Typed text is committed on Enter or
 * blur, and text that isn't a date goes back to the last value.
 * In the calendar: arrows move by day and week, PageUp/PageDown by month (with
 * Shift, by year), Home/End to the week's ends, Enter picks, Escape closes.
 * Styles are in espresso/components/date_picker.css.
 *
 * @example
 * const due = new frappe.ui.DatePicker({
 *   value: "2026-10-22",
 *   min: frappe.datetime.get_today(),
 *   on_change: (date) => save_due_date(date),
 * });
 * wrapper.append(due.$el);
 */
frappe.ui.DatePicker = class DatePicker {
	/** @param {DatePickerOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.size = validated(opts.size, SIZES, "size", "DatePicker") || "sm";
		this.variant = validated(opts.variant, VARIANTS, "variant", "DatePicker") || "subtle";
		this.value = opts.value || "";
		this.view = "date";

		const custom = opts.trigger instanceof Element || opts.trigger?.jquery;
		custom ? this.use_trigger($(opts.trigger)[0]) : this.make_field();

		this.popover = new frappe.ui.Popover({
			trigger: this.el,
			content: () => this.make_panel(),
			css_class: "es-date-picker-panel",
			keep_focus: true,
			side: opts.side,
			align: opts.align,
			offset: opts.offset,
			on_open: () => this.after_open(),
			on_close: (reason) => this.after_close(reason),
		});
		this.$el = $(this.el);
		this.$el.data("es-date-picker", this);
		this.render_field();
		this.set_disabled(Boolean(opts.disabled));
	}

	get is_open() {
		return this.popover.is_open;
	}

	get_value() {
		return this.value;
	}

	/** Change the date without calling on_change. */
	set_value(value) {
		this.value = value || "";
		this.render_field();
		if (this.is_open) {
			this.view = "date";
			this.view_month = this.get_start_month();
			this.render_calendar();
		}
	}

	/** Pick a date, as a click on it would. */
	set_date(value) {
		this.commit(value || "");
		if (!this.opts.keep_open) this.close(true);
	}

	clear() {
		this.set_date("");
	}

	set_disabled(disabled) {
		this.disabled = disabled;
		if (this.input) this.input.disabled = disabled;
		this.el.toggleAttribute("data-disabled", disabled);
		if (disabled) this.close();
	}

	focus(options) {
		(this.input || this.el).focus(options);
	}

	open(focus_grid = !this.input) {
		if (this.is_open || this.disabled) return;
		this.focus_grid = focus_grid;
		this.popover.open();
	}

	after_open() {
		this.set_expanded(true);
		if (this.focus_grid ?? !this.input) this.focus_cell();
		this.focus_grid = null;
	}

	/** @param {boolean} [refocus] Put focus back on the field or trigger. */
	close(refocus = false) {
		if (!this.is_open) return;
		const had_focus = this.popover.panel?.contains(document.activeElement);
		this.popover.close("owner");
		if (!(refocus || had_focus)) return;
		this.refocusing = true;
		this.focus({ preventScroll: true });
		this.refocusing = false;
	}

	toggle() {
		this.is_open ? this.close() : this.open();
	}

	make_field() {
		const wrap = document.createElement("div");
		wrap.className = ["es-input-wrap es-date-picker", this.opts.css_class]
			.filter(Boolean)
			.join(" ");
		wrap.setAttribute("data-size", this.size);
		wrap.innerHTML = `<input class="es-input" type="text" autocomplete="off" role="combobox"
				aria-haspopup="dialog" aria-expanded="false" data-has-suffix>
			<span class="es-input__suffix">
				<span class="es-date-picker__chevron">${frappe.utils.icon("chevron-down", "sm")}</span>
			</span>`;
		this.input = wrap.querySelector("input");
		this.input.setAttribute("data-size", this.size);
		this.input.setAttribute("data-variant", this.variant);
		this.input.placeholder = this.opts.placeholder || __("Select date");
		this.input.readOnly = this.opts.typeable === false;

		wrap.addEventListener("pointerdown", () => (this.pressed_at = Date.now()));
		this.input.addEventListener("focus", () => {
			const by_pointer = Date.now() - (this.pressed_at || 0) < 300;
			if (this.opts.open_on_focus && !this.refocusing && !by_pointer) this.open(false);
		});
		this.input.addEventListener("keydown", (e) => this.handle_field_key(e));
		this.input.addEventListener("blur", (e) => {
			if (this.popover.panel?.contains(e.relatedTarget)) return;
			this.commit_input();
		});
		const chevron = wrap.querySelector(".es-date-picker__chevron");
		chevron.addEventListener("mousedown", (e) => {
			e.preventDefault();
			this.input.focus();
		});
		this.el = wrap;
	}

	use_trigger(el) {
		this.el = el;
		el.addEventListener("keydown", (e) => {
			if (e.key === "ArrowDown" && !this.is_open) {
				e.preventDefault();
				this.open(true);
			}
		});
	}

	handle_field_key(e) {
		if (e.isComposing) return;
		if (e.key === "ArrowDown") {
			e.preventDefault();
			this.is_open ? this.focus_cell() : this.open(true);
		} else if (e.key === "Enter") {
			e.preventDefault();
			if (this.commit_input()) this.close();
		} else if (e.key === "Escape" && this.is_open) {
			e.stopPropagation();
			this.close();
		}
	}

	// Commit what was typed; text that isn't an available date goes back to the last value.
	commit_input() {
		if (!this.input || this.input.readOnly) return true;
		const raw = this.input.value.trim();
		if (!raw) {
			this.commit(this.opts.clearable === false ? frappe.datetime.get_today() : "");
			return true;
		}
		const format = this.get_format();
		const date = moment(raw, [format, format.replace("YYYY", "YY"), VALUE_FORMAT], true);
		const value = date.isValid() ? date.locale("en").format(VALUE_FORMAT) : null;
		if (value && this.is_available(value)) {
			this.commit(value);
			return true;
		}
		this.render_field();
		return false;
	}

	commit(value) {
		const changed = value !== this.value;
		this.value = value;
		this.render_field();
		if (this.is_open) this.render_calendar();
		if (changed) this.opts.on_change?.(value, this);
	}

	render_field() {
		if (!this.input) return;
		this.input.value = this.value
			? moment(this.value, VALUE_FORMAT).format(this.get_format())
			: "";
	}

	get_format() {
		return this.opts.format || frappe.datetime.get_user_date_fmt().toUpperCase();
	}

	after_close(reason) {
		this.set_expanded(false);
		this.grid = null;
		this.calendar = null;
		if (this.input && (reason === "escape" || reason === "tab")) {
			this.input.focus({ preventScroll: true });
		}
	}

	set_expanded(open) {
		if (!this.input) return;
		this.input.setAttribute("aria-expanded", String(open));
		if (open) this.input.setAttribute("aria-controls", this.popover.panel.id);
		else this.input.removeAttribute("aria-controls");
		this.el.setAttribute("data-state", open ? "open" : "closed");
	}

	make_panel() {
		if (this.disabled) return null;
		this.view = "date";
		this.view_month = this.get_start_month();
		this.focus_date = this.get_initial_focus();

		const body = document.createElement("div");
		body.className = "es-date-picker-panel__body";
		body.addEventListener("keydown", (e) => {
			if (e.key !== "Escape") return;
			e.stopPropagation();
			this.close(true);
		});

		const actions =
			typeof this.opts.actions === "function" ? this.opts.actions(this) : this.opts.actions;
		if (actions?.length) {
			const aside = document.createElement("aside");
			aside.className = "es-date-picker-panel__actions";
			aside.setAttribute("aria-label", __("Shortcuts"));
			aside.append(
				...actions.map(
					(action) =>
						frappe.ui.button({
							label: action.label,
							variant: "ghost",
							css_class: "es-date-picker-panel__action",
							onclick: () => action.onclick(this),
						})[0]
				)
			);
			body.append(aside);
		}

		this.calendar = document.createElement("div");
		this.calendar.className = "es-date-picker-calendar";
		body.append(this.calendar);
		this.render_calendar();
		return body;
	}

	render_calendar() {
		if (!this.calendar) return;
		this.calendar.replaceChildren(
			this.make_header(),
			this.view === "date" ? this.make_grid() : this.make_month_year()
		);
		if (this.view !== "date") this.center_month_year();
	}

	make_header() {
		const header = document.createElement("div");
		header.className = "es-date-picker-calendar__header";
		const title = frappe.ui.button({
			label: this.view_month.format("MMM YYYY"),
			variant: "ghost",
			css_class: "es-date-picker-calendar__title",
			attrs: { "aria-live": "polite" },
			onclick: () => {
				this.view = this.view === "date" ? "month_year" : "date";
				this.render_calendar();
				if (this.view === "date") this.focus_cell();
			},
		})[0];
		header.append(title);
		if (this.view !== "date") return header;

		const nav = document.createElement("div");
		nav.className = "es-date-picker-calendar__nav";
		nav.append(
			frappe.ui.button({
				icon: "chevron-left",
				variant: "ghost",
				tooltip: __("Previous month"),
				onclick: () => this.shift_view(-1),
			})[0],
			frappe.ui.button({
				label: __("Today"),
				variant: "ghost",
				css_class: "es-date-picker-calendar__today",
				onclick: () => this.pick(frappe.datetime.get_today()),
			})[0],
			frappe.ui.button({
				icon: "chevron-right",
				variant: "ghost",
				tooltip: __("Next month"),
				onclick: () => this.shift_view(1),
			})[0]
		);
		header.append(nav);
		return header;
	}

	make_grid() {
		const grid = document.createElement("div");
		grid.className = "es-date-picker-calendar__grid";
		grid.setAttribute("role", "grid");
		grid.setAttribute("aria-label", __("Calendar dates"));

		const first_day = frappe.datetime.get_first_day_of_the_week_index();
		const weekdays = moment.weekdaysMin();
		const head = document.createElement("div");
		head.className = "es-date-picker-calendar__weekdays";
		for (let i = 0; i < 7; i++) {
			const label = document.createElement("span");
			label.className = "es-date-picker-calendar__weekday";
			label.textContent = weekdays[(first_day + i) % 7].charAt(0);
			label.title = moment.weekdays()[(first_day + i) % 7];
			head.append(label);
		}
		grid.append(head);

		const month_start = this.view_month.clone().startOf("month");
		const start = month_start
			.clone()
			.subtract((month_start.day() - first_day + 7) % 7, "days");
		const today = frappe.datetime.get_today();
		const weeks = document.createElement("div");
		weeks.className = "es-date-picker-calendar__weeks";
		for (let w = 0; w < 6; w++) {
			const row = document.createElement("div");
			row.className = "es-date-picker-calendar__week";
			row.setAttribute("role", "row");
			for (let d = 0; d < 7; d++) {
				row.append(this.make_day(start.clone().add(w * 7 + d, "days"), today));
			}
			weeks.append(row);
		}
		grid.append(weeks);
		grid.addEventListener("keydown", (e) => this.handle_grid_key(e));
		this.grid = grid;
		return grid;
	}

	make_day(date, today) {
		const value = date.format(VALUE_FORMAT);
		const cell = document.createElement("button");
		cell.type = "button";
		cell.className = "es-date-picker-calendar__day";
		cell.setAttribute("role", "gridcell");
		cell.setAttribute("data-value", value);
		cell.textContent = date.date();
		const selected = value === this.value;
		cell.setAttribute("aria-selected", String(selected));
		cell.toggleAttribute("data-selected", selected);
		cell.toggleAttribute("data-today", value === today);
		cell.toggleAttribute("data-outside-view", date.month() !== this.view_month.month());
		const label = frappe.datetime.str_to_user(value);
		cell.setAttribute("aria-label", value === today ? `${label} (${__("Today")})` : label);
		cell.tabIndex = value === this.focus_date ? 0 : -1;
		if (!this.is_available(value)) {
			cell.disabled = true;
			cell.setAttribute("aria-disabled", "true");
			cell.setAttribute("data-disabled", "");
		}
		cell.addEventListener("click", () => this.pick(value));
		cell.addEventListener("focus", () => (this.focus_date = value));
		return cell;
	}

	handle_grid_key(e) {
		const moves = {
			ArrowLeft: [-1, "days"],
			ArrowRight: [1, "days"],
			ArrowUp: [-7, "days"],
			ArrowDown: [7, "days"],
			PageUp: [-1, e.shiftKey ? "years" : "months"],
			PageDown: [1, e.shiftKey ? "years" : "months"],
		};
		const current = moment(this.focus_date, VALUE_FORMAT);
		const first_day = frappe.datetime.get_first_day_of_the_week_index();
		const week_offset = (current.day() - first_day + 7) % 7;
		let target;
		if (moves[e.key]) target = current.clone().add(...moves[e.key]);
		else if (e.key === "Home") target = current.clone().subtract(week_offset, "days");
		else if (e.key === "End") target = current.clone().add(6 - week_offset, "days");
		else if (e.key === "Enter" || e.key === " ") {
			e.preventDefault();
			if (this.is_available(this.focus_date)) this.pick(this.focus_date);
			return;
		} else return;

		e.preventDefault();
		const step = target.isBefore(current) ? -1 : 1;
		const found = this.find_available(target, step);
		if (found) this.move_focus(found);
	}

	// Unavailable dates are skipped in the same direction; past min or max goes nowhere.
	find_available(date, step) {
		for (let i = 0; i < 366; i++) {
			const value = date.format(VALUE_FORMAT);
			if (
				(this.opts.min && value < this.opts.min) ||
				(this.opts.max && value > this.opts.max)
			) {
				return null;
			}
			if (this.is_available(value)) return value;
			date.add(step, "days");
		}
		return null;
	}

	move_focus(value) {
		this.focus_date = value;
		const date = moment(value, VALUE_FORMAT);
		if (!date.isSame(this.view_month, "month")) {
			this.view_month = date.clone().startOf("month");
			this.render_calendar();
		}
		this.focus_cell();
	}

	focus_cell() {
		if (!this.grid) return;
		const cell =
			this.grid.querySelector(`[data-value="${this.focus_date}"]`) ||
			this.grid.querySelector(
				".es-date-picker-calendar__day:not([data-outside-view]):not(:disabled)"
			);
		this.grid
			.querySelectorAll(".es-date-picker-calendar__day")
			.forEach((day) => (day.tabIndex = -1));
		if (!cell) return;
		cell.tabIndex = 0;
		cell.focus({ preventScroll: true });
	}

	pick(value) {
		if (!this.is_available(value)) return;
		this.set_date(value);
	}

	shift_view(months) {
		this.view_month = this.view_month.clone().add(months, "months");
		this.render_calendar();
	}

	make_month_year() {
		const wrap = document.createElement("div");
		wrap.className = "es-date-picker-calendar__month-year";
		const year = this.view_month.year();
		const now = moment().year();
		const first = this.opts.min ? Number(this.opts.min.slice(0, 4)) : now - 100;
		const last = this.opts.max ? Number(this.opts.max.slice(0, 4)) : now + 10;
		const years = [];
		for (let y = Math.min(first, year); y <= Math.max(last, year); y++) years.push(y);

		const make_list = (label, items, is_current, on_pick) => {
			const list = document.createElement("div");
			list.className = "es-date-picker-calendar__list";
			list.setAttribute("role", "listbox");
			list.setAttribute("aria-label", label);
			items.forEach(([value, text]) => {
				const item = document.createElement("button");
				item.type = "button";
				item.className = "es-date-picker-calendar__list-item";
				item.setAttribute("role", "option");
				item.textContent = text;
				const current = is_current(value);
				item.setAttribute("aria-selected", String(current));
				item.toggleAttribute("data-selected", current);
				item.addEventListener("click", () => on_pick(value));
				list.append(item);
			});
			return list;
		};

		wrap.append(
			make_list(
				__("Select year"),
				years.map((y) => [y, String(y)]),
				(y) => y === year,
				(y) => {
					this.view_month = this.view_month.clone().year(y);
					this.render_calendar();
				}
			),
			make_list(
				__("Select month"),
				moment.monthsShort().map((m, i) => [i, m]),
				(m) => m === this.view_month.month(),
				(m) => {
					this.view_month = this.view_month.clone().month(m);
					this.view = "date";
					this.render_calendar();
					this.focus_cell();
				}
			)
		);
		return wrap;
	}

	center_month_year() {
		requestAnimationFrame(() => {
			this.calendar?.querySelectorAll(".es-date-picker-calendar__list").forEach((list) => {
				const item = list.querySelector("[data-selected]");
				if (item)
					list.scrollTop =
						item.offsetTop - list.clientHeight / 2 + item.offsetHeight / 2;
			});
		});
	}

	get_start_month() {
		return moment(this.value || frappe.datetime.get_today(), VALUE_FORMAT).startOf("month");
	}

	get_initial_focus() {
		const today = frappe.datetime.get_today();
		if (this.value && this.is_available(this.value)) return this.value;
		if (this.is_available(today)) return today;
		return this.find_available(this.view_month.clone(), 1) || today;
	}

	is_available(value) {
		if (this.opts.min && value < this.opts.min) return false;
		if (this.opts.max && value > this.opts.max) return false;
		return !this.opts.is_date_unavailable?.(value);
	}
};

/**
 * Returns the text field (or your trigger); the instance is on `.data("es-date-picker")`.
 * @param {DatePickerOpts} opts
 * @returns {JQuery}
 */
frappe.ui.date_picker = (opts) => new frappe.ui.DatePicker(opts).$el;

export default frappe.ui.date_picker;
