// A list of filter rows, in a popover on `filter_button` or in place in
// `parent` (dialogs, form fields). A row applies as soon as it is complete.
frappe.ui.FilterGroup = class {
	constructor(opts) {
		$.extend(this, opts);
		this.filters = this.filters || [];
		window.fltr = this;
		if (!this.filter_button) {
			this.wrapper = this.parent;
			this.wrapper.append(this.get_filter_area_template());
			this.set_filter_events();
		} else {
			this.make_popover();
		}
	}

	make_popover() {
		// the rows outlive the panel: the area is kept and re-mounted on every open
		this.wrapper = this.get_filter_area_template();
		this.set_filter_events();
		this.popover = new frappe.ui.Popover({
			trigger: this.filter_button,
			content: () => this.get_popover_content(),
			side: "bottom",
			align: "end",
			css_class: "filter-popover",
			on_open: (popover) => this.on_popover_open(popover),
			on_close: () => {
				this.drop_standard_rows();
				this.update_filters();
				this.apply_changes();
			},
		});
		this.set_clear_all_filters_event();

		frappe.router.on("change", () => this.hide_popover());
	}

	set_clear_all_filters_event() {
		if (!this.filter_x_button) return;

		this.filter_x_button.on("click", () => {
			this.toggle_empty_filters(true);
			if (typeof this.base_list !== "undefined") {
				// It's a list view. Clear all the filters, also the ones in the
				// FilterArea outside this FilterGroup
				this.base_list.filter_area.clear();
			} else {
				// Not a list view, just clear the filters in this FilterGroup
				this.clear_filters();
			}
			this.update_filter_button();
		});
	}

	// rows go in before the panel is measured, so it opens at its final size
	get_popover_content() {
		this.sync_standard_rows();
		if (!this.filters.length) this.add_new_filter({ open_picker: false });
		return this.wrapper[0];
	}

	// the list's toolbar filters show as rows too, while the toolbar box stays their home
	sync_standard_rows() {
		const filter_area = this.base_list?.filter_area;
		if (!filter_area) return;
		this.drop_standard_rows();
		const own = this.filters.slice();
		const rows = filter_area
			.get_standard_filters()
			.map(([doctype, fieldname, condition, value]) => {
				if (condition === "like" && typeof value === "string") {
					value = value.replace(/^%+|%+$/g, "");
				}
				const filter = this._push_new_filter(doctype, fieldname, condition, value);
				filter.standard_field = fieldname;
				own.length && filter.filter_edit_area.insertBefore(own[0].filter_edit_area);
				return filter;
			});
		this.filters = [...rows, ...own];
		rows.length && this.toggle_empty_filters(false);
		// a Type set in the toolbar turns a Dynamic Link row into a record picker
		this.refresh_dynamic_link_filters();
		this.refresh_prefixes();
	}

	drop_standard_rows() {
		this.filters.filter((f) => f.standard_field).forEach((f) => f.remove());
		this.filters = this.filters.filter((f) => !f.standard_field);
	}

	// write a toolbar row back to its box; once the box can't hold it, it becomes a panel filter
	sync_to_toolbar(filter) {
		const box = this.base_list.page.fields_dict[filter.standard_field];
		const condition = filter.get_condition();
		const value = this.is_complete(filter) ? filter.get_selected_value() : null;
		const box_condition = box.df.match_type || box.df.condition || "=";
		// text boxes switch between equals and like
		const text_box = !!box.df.match_type;
		const fits =
			value != null &&
			filter.field.df.fieldname === filter.standard_field &&
			(condition === box_condition || (text_box && ["=", "like"].includes(condition))) &&
			!(box.df.fieldtype === "Check" && !cint(value));

		if (fits) {
			if (text_box) {
				box.df.match_type = condition;
				box.$wrapper
					.find(".match-type-dropdown-btn")
					.html(frappe.utils.icon(condition === "=" ? "equal" : "equal-approximately"));
			}
			box.set_value(condition === "like" ? value.replace(/^%+|%+$/g, "") : value);
			return;
		}

		filter.standard_field = null;
		box.set_value("");
		this.apply_changes();
	}

	on_popover_open(popover) {
		this.applied_filters = JSON.stringify(this.get_filters());
		const only_row = this.filters.length === 1 && this.filters[0];
		if (only_row && only_row.is_empty()) {
			this.after_enter(popover.panel, () => only_row.fieldselect.open());
		}
	}

	// opened mid enter-animation, the picker lines up with a trigger that is still scaling in
	after_enter(panel, fn) {
		let done = false;
		const run = () => {
			if (done || !this.is_popover_open()) return;
			done = true;
			fn();
		};
		panel.addEventListener("animationend", run, { once: true });
		setTimeout(run, 200);
	}

	hide_popover() {
		this.popover?.close("owner");
	}

	is_popover_open() {
		return !!this.popover?.is_open;
	}

	toggle_empty_filters(show) {
		this.wrapper && this.wrapper.find(".empty-filters").toggleClass("hidden", !show);
	}

	apply() {
		this.update_filters();
		this.applied_filters = JSON.stringify(this.get_filters());
		this.on_change();
	}

	// the same filters again refresh nothing, so opening and closing is free
	apply_changes() {
		const filters = JSON.stringify(this.get_filters());
		if (filters === this.applied_filters) return;
		this.applied_filters = filters;
		this.update_filter_button();
		this.on_change();
	}

	update_filter_button() {
		if (!this.filter_button) return;

		const standard = this.base_list?.filter_area?.get_standard_filters().length || 0;
		const count = this.get_filters().length + standard;
		this.filter_button.find(".filter-label").text(count).toggleClass("hidden", !count);
		// the clear button only shows, and joins the filter button, when there is something to clear
		this.filter_button.toggleClass("rounded-se-none rounded-ee-none", count > 0);
		this.filter_x_button?.toggleClass("hidden", !count);
		this.filter_button.attr(
			"title",
			count ? __("{0} filters applied", [count]) : __("Filter")
		);
	}

	set_filter_events() {
		this.wrapper.find(".add-filter").on("click", () => this.add_new_filter());

		this.wrapper.find(".clear-filters").on("click", () => {
			this.toggle_empty_filters(true);
			if (this.base_list) {
				// the toolbar boxes are cleared too
				const had_filters = this.get_filters().length;
				this.base_list.filter_area.clear().then(() => had_filters && this.on_change());
			} else {
				this.filters.forEach((f) => f.remove());
				this.filters = [];
				this.apply_changes();
			}
			this.hide_popover();
		});
	}

	// a row with no field yet; its picker opens so the first click lands on a field
	add_new_filter({ open_picker = true } = {}) {
		this.toggle_empty_filters(false);
		let filter = this.filters.find((f) => f.is_empty());
		if (!filter) {
			filter = this._push_new_filter(this.doctype, null);
			this.refresh_prefixes();
		}
		open_picker && filter.fieldselect.open();
		return filter;
	}

	add_filters(filters) {
		let promises = [];

		for (const filter of filters) {
			promises.push(() => this.add_filter(...filter));
		}

		return frappe.run_serially(promises).then(() => {
			this.update_filters();
			// set from outside (saved view, route): the host refreshes for these itself
			this.applied_filters = JSON.stringify(this.get_filters());
		});
	}

	add_filter(doctype, fieldname, condition, value, hidden) {
		if (!fieldname) return Promise.resolve();
		// adds a new filter, returns true if filter has been added

		if (!this.validate_args(doctype, fieldname)) return false;
		let args = [doctype, fieldname, condition, value, hidden];
		const promise = this.push_new_filter(args);
		this.toggle_empty_filters(false);
		this.refresh_prefixes();
		return promise && promise.then ? promise : Promise.resolve();
	}

	validate_args(doctype, fieldname) {
		if (
			doctype &&
			fieldname &&
			!frappe.meta.has_field(doctype, fieldname) &&
			frappe.model.is_non_std_field(fieldname)
		) {
			frappe.msgprint({
				message: __("Invalid filter: {0}", [fieldname.bold()]),
				indicator: "red",
			});

			return false;
		}
		return true;
	}

	push_new_filter(args) {
		// args: [doctype, fieldname, condition, value]
		if (this.filter_exists(args)) return;

		let filter = this._push_new_filter(...args);

		if (filter && filter.value) {
			return filter._filter_value_set; // internal promise
		}
	}

	_push_new_filter(doctype, fieldname, condition, value, hidden = false) {
		let filter;
		let args = {
			parent: this.wrapper,
			parent_doctype: this.doctype,
			doctype: doctype,
			_parent_doctype: this.parent_doctype,
			fieldname: fieldname,
			condition: condition,
			value: value,
			hidden: hidden,
			index: this.filters.length + 1,
			on_change: (update) => {
				if (update) this.update_filters();
				this.refresh_dynamic_link_filters();
				this.refresh_prefixes();
				if (filter?.standard_field) return this.sync_to_toolbar(filter);
				this.apply_changes();
			},
			on_enter: () => this.hide_popover(),
			filter_items: (doctype, fieldname) => {
				return !this.filter_exists([doctype, fieldname]);
			},
			filter_list: this.base_list || this,
		};

		filter = new frappe.ui.Filter(args);
		this.filters.push(filter);
		return filter;
	}

	// "Where" on the first row, "And" on the rest
	refresh_prefixes() {
		const rows = this.filters.filter((f) => f.filter_edit_area.parent().length);
		rows.forEach((f, i) => f.set_prefix(i === 0 ? __("Where") : __("And")));
	}

	get_filter_value(fieldname) {
		let filter_obj = this.filters.find((f) => f.fieldname == fieldname) || {};
		return filter_obj.value;
	}

	refresh_dynamic_link_filters() {
		if (!this.filters) return;

		this.filters.forEach((f) => {
			if (!f.field || f.field.df.original_type !== "Dynamic Link") return;
			if (!f.link_friendly_conditions.has(f.get_condition())) return;

			f.set_field(f.field.df.parent, f.field.df.fieldname, null, f.get_condition());
		});
	}

	filter_exists(filter_value) {
		// filter_value of form: [doctype, fieldname, condition, value]
		return this.filters
			.filter((f) => f.field)
			.some((f) => {
				let f_value = f.get_value();
				if (filter_value.length === 2) {
					return filter_value[0] === f_value[0] && filter_value[1] === f_value[1];
				}
				return frappe.utils.arrays_equal(f_value.slice(0, 4), filter_value.slice(0, 4));
			});
	}

	// a row counts once it has a field and a value
	is_complete(filter) {
		if (!filter.field) return false;
		const value = filter.get_selected_value();
		return value != null && value !== "" && !(Array.isArray(value) && !value.length);
	}

	// toolbar rows are left out: the list reads those from the toolbar boxes
	get_filters() {
		return this.filters
			.filter((f) => !f.standard_field && this.is_complete(f))
			.map((f) => f.get_value());
	}

	update_filters() {
		this.filters.map((f) => !this.is_complete(f) && f.remove());
		this.filters = this.filters.filter((f) => this.is_complete(f));
		this.refresh_prefixes();
		this.update_filter_button();
		this.filters.length === 0 && this.toggle_empty_filters(true);
	}

	clear_filters() {
		this.filters.map((f) => f.remove(true));
		this.filters = [];
		this.applied_filters = "[]";
		this.update_filter_button();
	}

	get_filter(fieldname) {
		return this.filters.filter((f) => {
			return f.field && f.field.df.fieldname == fieldname;
		})[0];
	}

	get_filter_area_template() {
		const $area = $(`
			<div class="filter-area">
				<div class="filter-edit-area">
					<div class="empty-filters text-ink-gray-5">
						${__("No filters selected")}
					</div>
				</div>
				<div class="filter-action-buttons flex items-center justify-between gap-2"></div>
			</div>`);
		$area.find(".filter-action-buttons").append(
			frappe.ui.button({
				label: __("Add filter"),
				icon: "plus",
				css_class: "add-filter",
			}),
			frappe.ui.button({
				label: __("Clear all"),
				variant: "ghost",
				css_class: "clear-filters text-ink-gray-6",
			})
		);
		return $area;
	}

	get_filters_as_object() {
		return this.get_filters().reduce((acc, filter) => {
			return Object.assign(acc, {
				[filter[1]]: [filter[2], filter[3]],
			});
		}, {});
	}

	add_filters_to_filter_group(filters) {
		if (filters && filters.length) {
			this.toggle_empty_filters(false);
			filters.forEach((filter) => {
				this.add_filter(filter[0], filter[1], filter[2], filter[3]);
			});
		}
	}

	add(filters, refresh = true) {
		if (!filters || (Array.isArray(filters) && filters.length === 0)) return Promise.resolve();

		if (typeof filters[0] === "string") {
			// passed in the format of doctype, field, condition, value
			const filter = Array.from(arguments);
			filters = [filter];
		}

		filters = filters.filter((f) => {
			return !this.exists(f);
		});

		const { non_standard_filters, promise } = this.set_standard_filter(filters);

		return promise
			.then(() => {
				return (
					non_standard_filters.length > 0 &&
					this.filter_list.add_filters(non_standard_filters)
				);
			})
			.then(() => {
				refresh && this.list_view.refresh();
			});
	}
};
