import { TABBABLE } from "../../ui/components/utils.js";
import { get_currency_doc, get_ranked_field, get_total_field } from "./totals";

/** Every edit calls `on_change` with the new grouping, or null once no level is left. */
export default class GroupEditor {
	/**
	 * @param {Object} opts
	 * @param {string} opts.doctype
	 * @param {Object|null} opts.grouping The current grouping.
	 * @param {Array} opts.columns The DocFields of the list's columns: the number ones can show totals.
	 * @param {Array} [opts.filters] The list's filters: a list of one company names its currency.
	 * @param {boolean} [opts.show_header=true] The title and Remove grouping; a host with its own title leaves it out.
	 * @param {frappe.ui.BottomSheet} [opts.sheet] The phone sheet the editor sits in: its pickers open as the sheet's steps.
	 * @param {function} opts.on_change
	 */
	constructor(opts) {
		this.opts = opts;
		const { ListView } = frappe.views;
		this.fields = ListView.get_groupable_fields(opts.doctype);
		this.number_fields = (opts.columns || []).filter(
			(df) => frappe.model.is_numeric_field(df) && ListView.can_read_field(opts.doctype, df)
		);
		this.grouping = opts.grouping ? structuredClone(opts.grouping) : null;
		this.$el = $('<div class="flex flex-col gap-3"></div>');
		// each picker's choices as a sheet step, by its data-focus key
		this.pickers = new Map();
		if (opts.sheet) {
			this.$el.addClass("group-editor-sheet");
			this.catch_pickers();
		}
		this.render();
	}

	/** In a sheet, a tap on a picker opens its step instead of a dropdown over the sheet. */
	catch_pickers() {
		const pick = (e) => {
			if (e.type === "keydown" && !["Enter", " ", "ArrowDown", "ArrowUp"].includes(e.key)) {
				return;
			}
			const open = this.pickers.get(e.target.closest("[data-focus]")?.dataset.focus);
			if (!open) return;
			e.preventDefault();
			e.stopPropagation();
			open();
		};
		this.$el[0].addEventListener("click", pick, true);
		this.$el[0].addEventListener("keydown", pick, true);
	}

	pick_step({ title, options, value, on_pick, search = false }) {
		const sheet = this.opts.sheet;
		const rows = (query = "") =>
			options
				.filter((o) => o.label.toLowerCase().includes(query.toLowerCase()))
				.map((o) => ({
					label: o.label,
					icon: o.icon,
					selected: o.value === value,
					onclick: () => {
						sheet.pop();
						if (o.value !== value) on_pick(o.value);
						return false;
					},
				}));
		const $search =
			search &&
			$('<input type="search" class="form-control">')
				.attr({ placeholder: __("Search fields"), "aria-label": __("Search fields") })
				.on("input", () => sheet.set_options(rows($search.val())));
		sheet.push({ title, header: $search || undefined, options: rows() });
	}

	size(in_sheet) {
		return this.opts.sheet ? in_sheet : "sm";
	}

	get levels() {
		return this.grouping?.levels || [];
	}

	field(fieldname) {
		return this.fields.find((f) => f.fieldname === fieldname);
	}

	change(grouping, focus = null) {
		this.grouping = grouping?.levels.length ? grouping : null;
		this.render(focus);
		this.opts.on_change(this.grouping);
	}

	set_levels(levels, focus = null) {
		this.change({ ...(this.grouping || this.new_grouping()), levels }, focus);
	}

	new_level(fieldname) {
		return { fieldname, order: "value-asc" };
	}

	with_level(index, level) {
		return this.levels.map((l, i) => (i === index ? level : l));
	}

	set_option(key, value) {
		this.change({ ...this.grouping, [key]: value });
	}

	new_grouping() {
		const totals = Object.fromEntries(
			this.number_fields.map((df) => [
				df.fieldname,
				df.fieldtype === "Percent" ? "avg" : "sum",
			])
		);
		return { levels: [], open: "none", totals, show_empty: 0, hide_grouped_columns: 1 };
	}

	/** Keeps focus in the editor, so Escape still closes the popover. */
	render(focus = null) {
		const active = document.activeElement;
		const had_focus = Boolean(focus) || this.$el[0].contains(active);
		const focus_key =
			focus || (had_focus ? active.closest("[data-focus]")?.dataset.focus : null);
		const in_dialog = this.opts.show_header === false;

		this.$el.empty();
		this.pickers.clear();
		if (!in_dialog) this.$el.append(this.make_header());
		if (this.levels.length) {
			// a dialog divides its own sections with lines
			this.$el.append(
				this.make_levels(),
				in_dialog ? "" : frappe.ui.divider(),
				this.make_options()
			);
		} else {
			this.$el.append(this.make_start());
		}

		if (!had_focus) return;
		const find = (key) => {
			const $el = this.$el.find(`[data-focus="${key}"]`).first();
			if ($el.is(TABBABLE)) return $el;
			const $picked = $el.find('[aria-checked="true"]').first();
			return $picked.length ? $picked : $el.find(TABBABLE).first();
		};
		[find(focus_key), find("add"), this.$el.find(TABBABLE).first()]
			.find(($el) => $el.length)
			?.trigger("focus");
	}

	make_header() {
		const $header = $(`<div class="flex items-center justify-between gap-2">
			<span class="text-base-medium text-ink-gray-8"></span>
		</div>`);
		$header.find("span").text(__("Grouping"));
		if (this.levels.length) {
			$header.append(
				frappe.ui.button({
					label: __("Remove grouping"),
					variant: "ghost",
					size: "sm",
					attrs: { "data-focus": "remove-all" },
					onclick: () => this.change(null),
				})
			);
		}
		return $header;
	}

	make_start() {
		const $start = $('<div class="flex flex-col gap-3"></div>').append(
			this.field_picker({
				placeholder: __("Pick a field to group by"),
				title: __("Group by"),
				focus: "add",
				on_pick: (fieldname) => this.set_levels([this.new_level(fieldname)]),
			})
		);

		const suggested = this.fields.filter((f) => f.suggested).slice(0, 6);
		if (suggested.length) {
			const $buttons = $('<div class="flex flex-wrap gap-2"></div>').append(
				suggested.map((f) =>
					frappe.ui.button({
						label: f.label,
						icon: f.icon,
						size: this.size("md"),
						onclick: () => this.set_levels([this.new_level(f.fieldname)]),
					})
				)
			);
			$start.append(
				$('<div class="flex flex-col gap-2"></div>').append(
					$('<span class="text-sm text-ink-gray-5"></span>').text(__("Suggested")),
					$buttons
				)
			);
		}
		return $start;
	}

	make_levels() {
		const $levels = $('<div class="flex flex-col gap-2"></div>');
		this.levels.forEach((level, index) => {
			const in_sheet = Boolean(this.opts.sheet);
			const $row = $('<div class="flex items-center gap-2"></div>').append(
				this.row_label(index ? __("then by") : __("Group by")),
				this.field_picker({
					value: level.fieldname,
					title: index ? __("Then by") : __("Group by"),
					focus: `field-${index}`,
					exclude: index,
					on_pick: (fieldname) =>
						this.set_levels(this.with_level(index, this.new_level(fieldname))),
				}),
				in_sheet ? "" : this.order_menu(level, index),
				frappe.ui.button({
					icon: "x",
					tooltip: __("Remove this level"),
					variant: "ghost",
					size: this.size("lg"),
					attrs: { "data-focus": `remove-${index}` },
					onclick: () => this.set_levels(this.levels.filter((l, i) => i !== index)),
				})
			);
			$levels.append($row);
			// a phone shows no tooltips: the order shows in words, on a line of its own
			if (in_sheet) {
				$levels.append(
					$('<div class="group-editor-order flex items-center gap-2"></div>').append(
						this.row_label(""),
						this.order_menu(level, index)
					)
				);
			}
		});

		if (this.levels.length < this.fields.length) {
			$levels.append(
				$('<div class="group-editor-add flex items-center gap-2"></div>').append(
					this.row_label(__("then by")),
					this.field_picker({
						placeholder: __("Add a sub-group"),
						title: __("Then by"),
						focus: "add",
						exclude: -1,
						on_pick: (fieldname) =>
							this.set_levels([...this.levels, this.new_level(fieldname)]),
					})
				)
			);
		}
		return $levels;
	}

	row_label(text) {
		return $(
			'<span class="group-editor-row-label shrink-0 whitespace-nowrap text-sm text-ink-gray-5"></span>'
		).text(text);
	}

	/** A field used by another level is left out. */
	field_picker({ value = null, placeholder, title, focus, exclude = -1, on_pick }) {
		const used = this.levels.filter((l, i) => i !== exclude).map((l) => l.fieldname);
		const options = this.fields
			.filter((f) => !used.includes(f.fieldname))
			.sort((a, b) => b.suggested - a.suggested)
			.map((f) => ({ label: f.label, value: f.fieldname, icon: f.icon }));
		const combobox = new frappe.ui.Combobox({
			options,
			value,
			placeholder: placeholder || __("Pick a field"),
			clear_button: false,
			on_change: (fieldname) => fieldname && fieldname !== value && on_pick(fieldname),
		});
		this.pickers.set(focus, () =>
			this.pick_step({ title, options, value, on_pick, search: true })
		);
		return $('<div class="min-w-0 flex-1"></div>')
			.attr("data-focus", focus)
			.append(combobox.$trigger);
	}

	order_menu(level, index) {
		const options = this.order_options(level);
		const current = options.find((o) => o.value === level.order) || options[0];
		const pick = (order) =>
			this.set_levels(this.with_level(index, { ...level, order }), `order-${index}`);
		this.pickers.set(`order-${index}`, () =>
			this.pick_step({
				title: __("Order of groups"),
				options,
				value: current.value,
				on_pick: pick,
			})
		);
		if (this.opts.sheet) {
			const combobox = new frappe.ui.Combobox({
				options,
				value: current.value,
				hide_search: true,
				clear_button: false,
				on_change: (order) => order && order !== current.value && pick(order),
			});
			return $('<div class="min-w-0 flex-1"></div>')
				.attr("data-focus", `order-${index}`)
				.append(combobox.$trigger);
		}
		return frappe.ui
			.dropdown({
				button: {
					icon: current.icon,
					tooltip: __("Order of groups: {0}", [current.label]),
					variant: "ghost",
				},
				align: "end",
				options: () =>
					options.map((o) => ({
						label: o.label,
						icon: o.icon,
						selected: o.value === level.order,
						onclick: () => pick(o.value),
					})),
			})
			.attr("data-focus", `order-${index}`);
	}

	order_options(level) {
		const has_options = this.field(level.fieldname)?.has_options;
		const options = [
			{
				label: has_options ? __("Field order") : __("A → Z"),
				value: "value-asc",
				icon: "arrow-up-narrow-wide",
			},
			{
				label: has_options ? __("Reverse order") : __("Z → A"),
				value: "value-desc",
				icon: "arrow-down-wide-narrow",
			},
			{ label: __("Most rows first"), value: "count-desc", icon: "list-ordered" },
		];
		const ranked = this.ranked_field();
		if (ranked) {
			const label = frappe.meta.get_translated_label(this.opts.doctype, ranked.fieldname);
			options.push({
				label: __("Highest {0} first", [label]),
				value: "sum-desc",
				icon: "sigma",
			});
		}
		return options;
	}

	make_options() {
		const $options = $('<div class="flex flex-col gap-3"></div>');

		const open = new frappe.ui.TabButtons({
			label: __("Open groups"),
			size: this.size("md"),
			options: [
				{ label: __("All"), value: "all" },
				{ label: __("First"), value: "first" },
				{ label: __("None"), value: "none" },
			],
			value: this.grouping.open,
			on_change: (value) => this.set_option("open", value),
		});
		$options.append(this.option_row(__("Open groups"), open.$el.attr("data-focus", "open")));

		for (const df of this.number_fields) {
			const totals = this.grouping.totals || {};
			const options = [
				{ label: __("Sum"), value: "sum" },
				{ label: __("Average"), value: "avg" },
				{ label: __("Hide"), value: "" },
			];
			const value = totals[df.fieldname] || "";
			const set_total = (fn) => {
				const next = { ...totals };
				if (fn) next[df.fieldname] = fn;
				else delete next[df.fieldname];
				this.set_option("totals", next);
			};
			const combobox = new frappe.ui.Combobox({
				options,
				value,
				hide_search: true,
				clear_button: false,
				on_change: set_total,
			});
			this.pickers.set(`total-${df.fieldname}`, () =>
				this.pick_step({
					title: __("{0} on group rows", [this.total_label(df)]),
					options,
					value,
					on_pick: set_total,
				})
			);
			$options.append(
				this.option_row(
					__("{0} on group rows", [this.total_label(df)]),
					$('<div class="group-editor-total"></div>')
						.attr("data-focus", `total-${df.fieldname}`)
						.append(combobox.$trigger)
				)
			);
		}

		const can_show_empty = this.levels.some((l) => this.field(l.fieldname)?.has_options);
		$options.append(
			this.checkbox({
				key: "show_empty",
				label: __("Show empty groups"),
				description: __("Show every option, even with no rows"),
				disabled: !can_show_empty,
			}),
			this.checkbox({
				key: "hide_grouped_columns",
				label: __("Hide grouped columns"),
				description: __("The group row already shows the value"),
			})
		);
		// how to use the list, not part of a saved layout
		if (this.opts.show_header !== false) {
			$options.append(
				$('<p class="mb-0 text-p-xs text-ink-gray-5"></p>').text(
					frappe.utils.is_mac()
						? __("Option-click a group to open or close every group at its level.")
						: __("Alt-click a group to open or close every group at its level.")
				)
			);
		}
		return $options;
	}

	ranked_field() {
		return get_ranked_field(this.opts.doctype, this.number_fields, this.grouping.totals || {});
	}

	/** A total in the company's currency names that currency, like the form does: "Grand Total (INR)". */
	total_label(df) {
		const { doctype } = this.opts;
		const label = frappe.meta.get_translated_label(doctype, df.fieldname);
		const source = get_total_field(doctype, df);
		if (source === df) return label;
		const doc = get_currency_doc(source, this.opts.filters);
		return __("{0} ({1})", [label, frappe.meta.get_field_currency(source, doc)]);
	}

	option_row(label, $control) {
		return $('<div class="flex items-center justify-between gap-3"></div>').append(
			$('<span class="text-sm text-ink-gray-7"></span>').text(label),
			$control
		);
	}

	checkbox({ key, label, description, disabled = false }) {
		const $row = $(`<label class="mb-0 flex gap-2 cursor-pointer">
			<input type="checkbox">
			<span class="flex flex-col gap-1">
				<span class="text-sm text-ink-gray-7"></span>
				<span class="text-p-xs text-ink-gray-5"></span>
			</span>
		</label>`).attr("data-focus", key);
		$row.find(".text-sm").text(label);
		$row.find(".text-p-xs").text(description);
		$row.find("input")
			.prop({ checked: Boolean(this.grouping[key]), disabled })
			.on("change", (e) => this.set_option(key, e.target.checked ? 1 : 0));
		return $row;
	}
}
