frappe.ui.FilterGroup = class {
	constructor(opts) {
		$.extend(this, opts);
		this.filters = [];
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
		this.init_filter_popover();
		this.set_clear_all_filters_event();
		this.set_popover_events();
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

	hide_popover() {
		this.filter_button.popover("hide");
	}

	init_filter_popover() {
		this.filter_button.popover({
			content: this.get_filter_area_template(),
			template: `
				<div class="filter-popover popover">
					<div class="arrow"></div>
					<div class="popover-body popover-content">
					</div>
				</div>
			`,
			html: true,
			trigger: "manual",
			container: "body",
			placement: "bottom",
			offset: "-100px, 0",
		});
	}

	toggle_empty_filters(show) {
		this.wrapper && this.wrapper.find(".empty-filters").toggle(show);
	}

	set_popover_events() {
		$(document.body).on("click", (e) => {
			if (this.wrapper && this.wrapper.is(":visible")) {
				const in_datepicker =
					$(e.target).is(".datepicker--cell") ||
					$(e.target).closest(".datepicker--nav-title").length !== 0 ||
					$(e.target).parents(".datepicker--nav-action").length !== 0;

				if (
					$(e.target).parents(".filter-popover").length === 0 &&
					$(e.target).parents(".filter-box").length === 0 &&
					this.filter_button.find($(e.target)).length === 0 &&
					!$(e.target).is(this.filter_button) &&
					!in_datepicker
				) {
					this.wrapper && this.hide_popover();
				}
			}
		});

		this.filter_button.on("click", () => {
			this.filter_button.popover("toggle");
		});

		this.filter_button.on("shown.bs.popover", () => {
			let hide_empty_filters = this.filters && this.filters.length > 0;

			if (!this.wrapper) {
				this.wrapper = $(".filter-popover");
				if (hide_empty_filters) {
					this.toggle_empty_filters(false);
					this.add_filters_to_popover(this.filters);
				}
				this.set_filter_events();
			}
			this.toggle_empty_filters(false);
			!hide_empty_filters && this.add_filter(this.doctype, "name");
		});

		this.filter_button.on("hidden.bs.popover", () => {
			this.apply();
		});

		// REDESIGN-TODO: (Temporary) Review and find best solution for this
		frappe.router.on("change", () => {
			if (this.wrapper && this.wrapper.is(":visible")) {
				this.hide_popover();
			}
		});
	}

	add_filters_to_popover(filters) {
		filters.forEach((filter) => {
			filter.parent = this.wrapper;
			filter.field = null;
			filter.make();
		});
	}

	apply() {
		this.update_filters();
		this.on_change();
	}

	update_filter_button() {
		const filters_applied = this.filters.length > 0;
		const button_label = filters_applied
			? this.filters.length > 1
				? __("{0} filters", [this.filters.length])
				: __("{0} filter", [this.filters.length])
			: __("Filter");

		this.filter_button
			.toggleClass("btn-default", !filters_applied)
			.toggleClass("btn-primary-light", filters_applied);

		this.filter_button.find(".filter-icon").toggleClass("active", filters_applied);

		this.filter_button.find(".button-label").html(button_label);
	}

	set_filter_events() {
		this.wrapper.find(".add-filter").on("click", () => {
			this.toggle_empty_filters(false);
			this.add_filter(this.doctype, "name");
		});

		this.wrapper.find(".clear-filters").on("click", () => {
			this.toggle_empty_filters(true);
			this.clear_filters();
			this.on_change();
			this.hide_popover();
		});

		this.wrapper.find(".apply-filters").on("click", () => this.hide_popover());
	}

	add_filters(filters) {
		let promises = [];

		for (const filter of filters) {
			promises.push(() => this.add_filter(...filter));
		}

		return frappe.run_serially(promises).then(() => this.update_filters());
	}

	add_filter(doctype, fieldname, condition, value, hidden) {
		if (!fieldname) return Promise.resolve();
		// adds a new filter, returns true if filter has been added

		// {}: Add in page filter by fieldname if exists ('=' => 'like')

		if (!this.validate_args(doctype, fieldname)) return false;
		const is_new_filter = arguments.length < 2;
		if (is_new_filter && this.wrapper.find(".new-filter:visible").length) {
			// only allow 1 new filter at a time!
			return Promise.resolve();
		} else {
			let args = [doctype, fieldname, condition, value, hidden];
			const promise = this.push_new_filter(args, is_new_filter);
			return promise && promise.then ? promise : Promise.resolve();
		}
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

		// {}: Clear page filter fieldname field

		let filter = this._push_new_filter(...args);

		if (filter && filter.value) {
			// filter.setup_state(is_new_filter);
			return filter._filter_value_set; // internal promise
		}
	}

	_push_new_filter(doctype, fieldname, condition, value, hidden = false) {
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
				this.on_change();
			},
			filter_items: (doctype, fieldname) => {
				return !this.filter_exists([doctype, fieldname]);
			},
			filter_list: this.base_list || this,
		};
		let filter = new frappe.ui.Filter(args);
		this.filters.push(filter);
		return filter;
	}

	get_filter_value(fieldname) {
		let filter_obj = this.filters.find((f) => f.fieldname == fieldname) || {};
		return filter_obj.value;
	}

	filter_exists(filter_value) {
		// filter_value of form: [doctype, fieldname, condition, value]
		let exists = false;
		this.filters
			.filter((f) => f.field)
			.map((f) => {
				let f_value = f.get_value();
				if (filter_value.length === 2) {
					exists = filter_value[0] === f_value[0] && filter_value[1] === f_value[1];
					return;
				}

				let value = filter_value[3];
				let equal = frappe.utils.arrays_equal;

				if (
					equal(f_value.slice(0, 4), filter_value.slice(0, 4)) ||
					(Array.isArray(value) && equal(value, f_value[3]))
				) {
					exists = true;
				}
			});
		return exists;
	}

	get_filters() {
		return this.filters
			.filter((f) => f.field)
			.map((f) => {
				return f.get_value();
			});
		// {}: this.list.update_standard_filters(values);
	}

	update_filters() {
		// remove hidden filters and undefined filters
		const filter_exists = (f) => ![undefined, null].includes(f.get_selected_value());
		this.filters.map((f) => !filter_exists(f) && f.remove());
		this.filters = this.filters.filter((f) => filter_exists(f) && f.field);
		this.update_filter_button();
		this.filters.length === 0 && this.toggle_empty_filters(true);
	}

	clear_filters() {
		this.filters.map((f) => f.remove(true));
		// {}: Clear page filters, .date-range-picker (called list run())
		this.filters = [];
	}

	get_filter(fieldname) {
		return this.filters.filter((f) => {
			return f.field && f.field.df.fieldname == fieldname;
		})[0];
	}

	get_filter_area_template() {
		/* eslint-disable indent */
		return $(`
			<div class="filter-area">
				<div class="filter-edit-area">
					<div class="text-muted empty-filters text-center">
						${__("No filters selected")}
					</div>
				</div>
				<hr class="divider"></hr>
				<div class="filter-action-buttons mt-2">
					<button class="text-muted add-filter btn btn-xs">
						+ ${__("Add a Filter")}
					</button>
					<div>
						<button class="btn btn-secondary btn-xs clear-filters">
							${__("Clear Filters")}
						</button>
						${
							this.filter_button
								? `<button class="btn btn-primary btn-xs apply-filters">
								${__("Apply Filters")}
							</button>`
								: ""
						}
					</div>
				</div>
			</div>`);
		/* eslint-disable indent */
	}

	get_filters_as_object() {
		let filters = this.get_filters().reduce((acc, filter) => {
			return Object.assign(acc, {
				[filter[1]]: [filter[2], filter[3]],
			});
		}, {});
		return filters;
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
