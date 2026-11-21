import "./filter_chips.js";
import { focus_soon, icon_of, scroll_cue, search_keys, stopwatch } from "./filter_pickers.js";
import { is_scan_helper, kind_of, list_of, same_field, std_field } from "./filter_utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} FilterPanelOpts
 * @property {frappe.ui.FilterChips} chips The bar whose filters the panel edits; the two stay in step.
 * @property {Array<{label: string, table?: boolean, fields: Object[]}>} sections The fields to list,
 *   grouped; each field carries the `doctype` it belongs to.
 * @property {Object} [focus] { doctype, fieldname } of the field to open on.
 * @property {string} [view] "advanced" to open on the host's own rows.
 * @property {Object} [last_used] { doctype, fieldname } of the field picked here last time, to
 *   open on when no field is filtered.
 * @property {function} [on_pick] Called with the field the person picks in the list.
 * @property {Object} [advanced] The host's editor for filters the pickers can't show:
 *   `{ element() → Element, on_hide() }` to show it in the panel, or `{ open() }` to open it
 *   somewhere else.
 */

const icon = (name) => frappe.utils.icon(name, "sm", "", "", "", true);

/**
 * Every field of a DocType, beside the picker of the one picked: fields on the left in the form's
 * sections with how many values each one has, the picker on the right. Filters only the host can
 * show (two conditions on one field) are edited in its own rows, behind "Advanced filters".
 * @example
 * new frappe.ui.FilterPanel({
 *     chips,
 *     sections: frappe.ui.FilterPanel.sections_for("ToDo"),
 * }).$wrapper.appendTo(popover_body);
 */
frappe.ui.FilterPanel = class FilterPanel {
	/** @param {FilterPanelOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.chips = opts.chips;
		this.$wrapper = $('<div class="es-filter-panel"></div>');
		this.$fields = $('<div class="es-filter-panel__fields"></div>').appendTo(this.$wrapper);
		this.$pane = $('<section class="es-filter-panel__pane"></section>').appendTo(
			this.$wrapper
		);
		this.$advanced = $(
			'<section class="es-filter-panel__advanced-view" tabindex="-1"></section>'
		)
			.attr("aria-label", __("Advanced filters"))
			.prop("hidden", true)
			.appendTo(this.$wrapper);

		this.make_field_list();
		this.on_chips = () => this.refresh();
		this.chips.on_render(this.on_chips);

		if (opts.view === "advanced" && opts.advanced) {
			// Back leads to the field the person came to edit
			this.current = this.all_fields().find((df) => same_field(df, opts.focus));
			this.show_advanced();
		} else {
			const asked = this.all_fields().find((df) => same_field(df, opts.focus));
			this.select(asked || this.start_field(), { focus: !!asked });
			if (!asked) focus_soon(this.$search[0]);
		}
	}

	// Up/Down light a field from the search; Enter, or Right (Left in RTL) at the text's end, opens it
	make_field_keys() {
		this.keys = search_keys(this.$fields[0], ".es-menu__item", this.$search[0]);
		this.$search.on("keydown", (e) => {
			const input = e.currentTarget;
			const into = frappe.utils.is_rtl() ? "ArrowLeft" : "ArrowRight";
			if (e.isDefaultPrevented() || e.originalEvent?.isComposing || e.keyCode === 229)
				return;
			if (e.key === "Enter" && input.value.trim()) {
				e.preventDefault();
				this.rows.find((row) => !row.$row.prop("hidden"))?.$row.trigger("click");
			} else if (e.key === into && input.selectionStart === input.value.length) {
				const lit = this.keys.lit();
				if (!lit) return;
				e.preventDefault();
				lit.click();
			}
		});
	}

	all_fields() {
		return this.opts.sections.flatMap((section) => section.fields);
	}

	/**
	 * The field the panel opens on: the one filtered last, the one picked here last time, the
	 * DocType's Status, the first quick filter, the first field; never one that is typed into.
	 */
	start_field() {
		// the bar's own field decides: its ID is a box typed into
		const typed = (df) => {
			const field = this.chips.field_of(df.doctype, df.fieldname) || df;
			return field.typed || kind_of(field) === "text";
		};
		const fields = this.all_fields().filter((df) => !typed(df));
		const find = (key) => fields.find((df) => same_field(df, key));
		const filtered = this.chips.filters.map(([doctype, fieldname]) => ({
			doctype,
			fieldname,
		}));
		return (
			filtered.map(find).filter(Boolean).pop() ||
			find(this.opts.last_used) ||
			find({ doctype: this.chips.doctype, fieldname: "status" }) ||
			this.chips.fields.map(find).find(Boolean) ||
			fields[0] ||
			this.all_fields()[0]
		);
	}

	// values picked for a field, or the conditions set on it
	count_of(df) {
		const rules = this.chips.rules_for(df);
		if (rules.length === 1 && ["in", "not in"].includes(rules[0][0])) {
			return list_of(rules[0][1]).length;
		}
		return rules.length;
	}

	make_field_list() {
		const $search = $('<label class="es-filter-panel__search"></label>').appendTo(
			this.$fields
		);
		this.$search = $('<input type="text" autocomplete="off">').attr({
			placeholder: __("Search fields"),
			"aria-label": __("Search fields"),
		});
		// clears the search; a phone's keyboard stays down, the next tap in the box brings it back
		const $clear = frappe.ui
			.button({ icon: "x", size: "xs", variant: "ghost", tooltip: __("Clear search") })
			.addClass("es-filter-panel__search-clear")
			.prop("hidden", true)
			.on("click", () => {
				this.$search.val("").trigger("input");
				if (frappe.is_mobile()) this.$search.trigger("blur");
				else this.$search.trigger("focus");
			});
		$search.append(icon("search"), this.$search, $clear);
		this.$list = $('<div class="es-filter-panel__list" role="listbox" tabindex="-1"></div>')
			.attr("aria-label", __("Fields"))
			.appendTo(this.$fields);
		this.$empty = $('<div class="es-menu__empty" hidden></div>');

		this.rows = [];
		for (const section of this.opts.sections) {
			const $group = $(
				'<div class="es-filter-panel__group flex flex-col gap-0.5" role="group"></div>'
			)
				.attr("aria-label", section.label)
				.appendTo(this.$list);
			const $label = $(
				'<div class="es-menu__group-label es-filter-panel__group-label"></div>'
			)
				.text(section.label)
				.appendTo($group);
			if (section.table) $label.append(icon("table-2"));
			for (const df of section.fields) {
				const $row = $(
					'<button type="button" class="es-menu__item" role="option" tabindex="-1"></button>'
				)
					.append(icon(icon_of(df)))
					.append($('<span class="es-menu__label"></span>').text(df.label))
					.append('<span class="es-filter-panel__count"></span>')
					.on("click", () => {
						this.select(df);
						this.opts.on_pick?.(df);
					})
					.appendTo($group);
				this.rows.push({ df, $row, section });
			}
		}
		this.$list.append(this.$empty);
		this.stop_tooltips = frappe.ui.Tooltip.delegate(this.$list, ".es-menu__label", {
			only_on_overflow: true,
		});
		this.cue = scroll_cue(this.$list[0]);
		this.cue();

		this.$search.on("input", () => {
			$clear.prop("hidden", !this.$search.val());
			this.search();
		});
		this.make_field_keys();

		if (this.opts.advanced) {
			this.$advanced_row = $(
				'<button type="button" class="es-menu__item" tabindex="-1"></button>'
			)
				.append(icon("sliders-horizontal"))
				.append($('<span class="es-menu__label"></span>').text(__("Advanced filters")))
				// a click (detail 1+) has no ring to carry to Back; Enter from the search does
				.on("click", (e) => this.show_advanced({ keyboard: !e.detail }));
			$('<div class="es-filter-panel__footer"></div>')
				.append(this.$advanced_row)
				.appendTo(this.$fields);
		}
		this.update_counts();
	}

	search() {
		const query = this.$search.val().trim().toLowerCase();
		for (const row of this.rows) {
			const text = `${row.df.label} ${row.section.label}`.toLowerCase();
			row.$row.prop("hidden", !!query && !text.includes(query));
		}
		this.$list.find(".es-filter-panel__group").each((i, group) => {
			$(group).prop("hidden", !$(group).find(".es-menu__item:not([hidden])").length);
		});
		this.$list.scrollTop(0);
		const none = this.rows.every((row) => row.$row.prop("hidden"));
		const typed = this.$search.val().trim();
		this.$empty.text(__("No results for {0}", [typed])).prop("hidden", !none);
		this.cue();
		this.keys.reset();
		// one field left: on a phone, where the list and the picker share the screen, show it
		// while typing goes on in the search
		const shown = this.rows.filter((row) => !row.$row.prop("hidden"));
		if (
			frappe.is_mobile() &&
			query &&
			shown.length === 1 &&
			!same_field(shown[0].df, this.current)
		) {
			this.select(shown[0].df, { focus: false });
			this.opts.on_pick?.(shown[0].df);
		}
	}

	update_counts() {
		const badge = ($el, count) => {
			$el.html(
				count
					? frappe.ui.badge.html({
							label: String(count),
							size: "sm",
							variant: "outline",
					  })
					: ""
			);
		};
		for (const row of this.rows) {
			const count = this.count_of(row.df);
			if (row.count === count) continue;
			row.count = count;
			row.$row.toggleClass("is-filtered", count > 0);
			badge(row.$row.find(".es-filter-panel__count"), count);
		}
	}

	refresh() {
		this.update_counts();
		if (this.current) {
			this.$clear?.prop(
				"hidden",
				!this.chips.rules_of(this.current.doctype, this.current.fieldname).length
			);
		}
		if (this.turn_watch) {
			const [rule] = this.chips.rules_for(this.current);
			const value =
				rule?.[0] === "Between" ? list_of(rule[1]).filter(Boolean).pop() : rule?.[1];
			this.turn_watch(rule?.[0] === "is" || !value ? null : cint(value));
		}
	}

	select(df, { focus = true } = {}) {
		if (!df) return;
		this.current = df;
		for (const row of this.rows) {
			const current = same_field(row.df, df);
			row.$row.attr({
				"aria-current": current ? "true" : null,
				"aria-selected": current ? "true" : "false",
			});
			// once the panel is on the page, so a field low in a long list scrolls into view
			if (current) {
				requestAnimationFrame(() => row.$row[0].scrollIntoView?.({ block: "nearest" }));
			}
		}
		this.picker?.destroy?.();
		this.$pane.empty().attr("aria-label", df.label);

		const $head = $('<header class="es-filter-panel__head"></header>').appendTo(this.$pane);
		const field_icon = icon_of(df);
		// a Duration's stopwatch turns its hand to the time picked
		const watch = df.fieldtype === "Duration" && field_icon === "timer" ? stopwatch() : null;
		this.turn_watch = watch?.turn;
		$head.append(
			watch || icon(field_icon),
			// a child table's field says whose it is: "Project (Dependent Tasks)"
			$('<h3 class="es-filter-panel__title truncate"></h3>').text(
				df.table_label ? __("{0} ({1})", [df.label, df.table_label]) : df.label
			)
		);
		const hint = this.hint_of(df);
		if (hint)
			$head.append($('<span class="es-filter-panel__hint truncate"></span>').text(hint));
		this.$clear = frappe.ui
			.button({
				label: __("Clear"),
				variant: "ghost",
				onclick: () => {
					// the picker saves what it still holds first, so Clear has the last word
					this.picker?.destroy?.();
					this.picker = null;
					this.chips.set_rules(df.doctype, df.fieldname, []);
					this.select(df);
				},
			})
			.appendTo($head);

		this.picker = this.chips.picker_for(df, {
			on_advanced: this.opts.advanced ? () => this.show_advanced() : null,
			hint:
				this.opts.advanced && df.fieldtype === "Datetime"
					? __("To filter by time, use Advanced filters")
					: "",
			autofocus: focus,
			// the header's Clear does it for every field
			clear: false,
		});
		$('<div class="es-filter-panel__picker"></div>').append(this.picker).appendTo(this.$pane);
		this.refresh();
	}

	// only what helps pick: the records a link points to, or the table a field lives in
	hint_of(df) {
		const section = this.rows.find((row) => same_field(row.df, df))?.section;
		if (section?.table) return __("{0} table · any row", [section.label]);
		// the chip's own field: the ID box is typed, not a link
		const field = this.chips.field_of(df.doctype, df.fieldname) || df;
		if (field.fieldtype === "Link" && field.options) {
			return __("Link to {0}", [__(field.options)]);
		}
		return "";
	}

	show_advanced({ keyboard = true } = {}) {
		if (this.opts.advanced.open) return this.opts.advanced.open();
		this.picker?.destroy?.();
		this.picker = null;
		this.$fields.prop("hidden", true);
		this.$pane.prop("hidden", true);
		this.$advanced.prop("hidden", false).empty();
		this.$wrapper.attr("data-view", "advanced");
		const $head = $('<header class="es-filter-panel__head"></header>').appendTo(
			this.$advanced
		);
		const $back = frappe.ui.button({
			icon: "arrow-left",
			variant: "ghost",
			css_class: "es-filter-panel__back",
			title: __("Back to fields"),
			onclick: () => this.hide_advanced(),
		});
		$head.append(
			$back,
			$('<h3 class="es-filter-panel__title truncate"></h3>').text(__("Advanced filters"))
		);
		const $body = $('<div class="es-filter-panel__advanced-body p-3"></div>')
			.append(this.opts.advanced.element())
			.appendTo(this.$advanced);
		// heard on the way down, while the removed row's button is still in it
		$body[0].addEventListener(
			"click",
			(e) => {
				if (!e.target.closest(".remove-filter")) return;
				requestAnimationFrame(() => {
					if (!this.$advanced[0].contains(document.activeElement)) {
						$body.find(".add-filter").trigger("focus");
					}
				});
			},
			true
		);
		this.advanced_shown = true;
		// the field list it hid had focus
		focus_soon(keyboard ? $back[0] : this.$advanced[0]);
	}

	hide_advanced() {
		if (!this.leave_advanced()) return;
		this.select(this.current || this.all_fields()[0], { focus: false });
		focus_soon(this.$search[0]);
	}

	leave_advanced() {
		if (!this.advanced_shown) return false;
		this.advanced_shown = false;
		// the rows are the host's: detach, so its handlers stay on them
		this.$advanced.children().detach();
		this.$advanced.prop("hidden", true);
		this.$wrapper.removeAttr("data-view");
		this.opts.advanced.on_hide?.();
		this.$fields.prop("hidden", false);
		this.$pane.prop("hidden", false);
		return true;
	}

	destroy() {
		this.stop_tooltips?.();
		this.picker?.destroy?.();
		this.leave_advanced();
		this.chips.off_render(this.on_chips);
	}

	/**
	 * The fields of a DocType the desk lets you filter on (the Advanced field picker's list), in
	 * the form's sections; the fields every DocType has, and each child table's, as groups of their own.
	 * @param {string} doctype
	 * @returns {Array<{label: string, table?: boolean, fields: Object[]}>}
	 */
	static sections_for(doctype) {
		// the Advanced rows' own rule for which fields can be filtered: permissions, child tables
		const list = Object.assign(Object.create(frappe.ui.FieldSelect.prototype), {
			doctype,
			options: [],
			fields_by_name: {},
			table_fields: [],
		});
		list.build_options();

		const meta = frappe.get_meta(doctype);
		const own = new Map(
			list.options.filter((o) => o.doctype === doctype).map((o) => [o.fieldname, o])
		);
		const sections = [{ label: __("Details"), fields: [] }];
		for (const df of meta.fields) {
			if (["Section Break", "Tab Break"].includes(df.fieldtype)) {
				if (df.label) sections.push({ label: __(df.label, null, doctype), fields: [] });
				continue;
			}
			// a password can't be matched (it is stored hashed); a scan box only fills other fields
			const unmatched = df.fieldtype === "Password" || is_scan_helper(df);
			if (!own.has(df.fieldname) || unmatched) continue;
			sections.at(-1).fields.push({ ...df, doctype, label: own.get(df.fieldname).label });
			own.delete(df.fieldname);
		}
		// a record's row number (idx) only means something inside a child table
		const standard = [...own.values()]
			.filter((o) => o.fieldname !== "idx")
			.map((o) => ({ ...std_field(doctype, o.fieldname), doctype }))
			.filter((df) => df.fieldtype);
		// the ID leads the list, as its chip leads the bar
		const id = standard.findIndex((df) => df.fieldname === "name");
		if (id !== -1) sections[0].fields.unshift(...standard.splice(id, 1));

		const tables = new Map();
		for (const o of list.options.filter((o) => o.doctype !== doctype)) {
			const df = frappe.meta.get_docfield(o.doctype, o.fieldname);
			if (!df || is_scan_helper(df)) continue;
			const group = o.group || __(o.doctype);
			if (!tables.has(group)) tables.set(group, []);
			tables
				.get(group)
				.push({ ...df, doctype: o.doctype, label: o.label, table_label: group });
		}
		for (const [label, fields] of tables) sections.push({ label, table: true, fields });
		if (standard.length) sections.push({ label: __("Activity"), fields: standard });

		return sections.filter((section) => section.fields.length);
	}
};

export default frappe.ui.FilterPanel;
