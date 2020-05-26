frappe.ui.FilterGroup = class {
	constructor(opts) {
		$.extend(this, opts);
		this.wrapper = this.parent;
		this.filters = [];
		this.make();
		window.fltr = this;
	}

	make() {
		this.wrapper.append(this.get_container_template());
		this.set_events();
	}

	toggle_clear_filter() {
		let clear_filter_button = this.wrapper.find('.clear-filters');

		if (this.filters.length == 0) {
			clear_filter_button.hide();
		} else {
			clear_filter_button.show();
		}
	}
	set_events() {
		this.wrapper.find('.add-filter').on('click', () => {
			this.add_filter(this.doctype, 'name')
				.then(this.toggle_clear_filter());

		});
		this.wrapper.find('.clear-filters').on('click', () => {
			this.clear_filters();
		});
	}

	add_filters(filters) {
		let promises = [];

		for (const filter of filters) {
			promises.push(() => this.add_filter(...filter));
		}

		promises.push(() => this.toggle_clear_filter());

		return frappe.run_serially(promises);
	}

	add_filter(doctype, fieldname, condition, value, hidden) {
		if (!fieldname) return Promise.resolve();
		// adds a new filter, returns true if filter has been added

		// {}: Add in page filter by fieldname if exists ('=' => 'like')

		if(!this.validate_args(doctype, fieldname)) return false;
		const is_new_filter = arguments.length < 2;
		if (is_new_filter && this.wrapper.find(".new-filter:visible").length) {
			// only allow 1 new filter at a time!
			return Promise.resolve();
		} else {
			let args = [doctype, fieldname, condition, value, hidden];
			const promise = this.push_new_filter(args, is_new_filter);
			return (promise && promise.then) ? promise : Promise.resolve();
		}
	}

	validate_args(doctype, fieldname) {

		if(doctype && fieldname
			&& !frappe.meta.has_field(doctype, fieldname)
			&& !frappe.model.std_fields_list.includes(fieldname)) {

			frappe.throw(__(`Invalid filter: "${[fieldname.bold()]}"`));
			return false;
		}
		return true;
	}

	push_new_filter(args, is_new_filter=false) {
		// args: [doctype, fieldname, condition, value]
		if(this.filter_exists(args)) return;

		// {}: Clear page filter fieldname field

		let filter = this._push_new_filter(...args);

		if (filter && filter.value) {
			filter.setup_state(is_new_filter);
			return filter._filter_value_set; // internal promise
		}
	}

	_push_new_filter(doctype, fieldname, condition, value, hidden = false) {
		let args = {
			parent: this.wrapper,
			parent_doctype: this.doctype,
			doctype: doctype,
			fieldname: fieldname,
			condition: condition,
			value: value,
			hidden: hidden,
			on_change: (update) => {
				if(update) this.update_filters();
				this.on_change();
			},
			filter_items: (doctype, fieldname) => {
				return !this.filter_exists([doctype, fieldname]);
			},
			base_list: this.base_list
		};
		let filter = new frappe.ui.Filter(args);
		this.filters.push(filter);
		return filter;
	}

	filter_exists(filter_value) {
		// filter_value of form: [doctype, fieldname, condition, value]
		let exists = false;
		this.filters.filter(f => f.field).map(f => {
			let f_value = f.get_value();
			if (filter_value.length === 2) {
				exists = filter_value[0] === f_value[0] && filter_value[1] === f_value[1];
				return;
			}

			let value = filter_value[3];
			let equal = frappe.utils.arrays_equal;

			if(equal(f_value.slice(0, 4), filter_value.slice(0, 4)) || (Array.isArray(value) && equal(value, f_value[3]))) {
				exists = true;
			}
		});
		return exists;
	}

	get_filters() {
		return this.filters.filter(f => f.field).map(f => {
			return f.get_value();
		});
		// {}: this.list.update_standard_filters(values);
	}

	update_filters() {
		this.filters = this.filters.filter(f => f.field); // remove hidden filters
		this.toggle_clear_filter();
	}

	clear_filters() {
		this.filters.map(f => f.remove(true));
		// {}: Clear page filters, .date-range-picker (called list run())
		this.filters = [];
	}

	get_filter(fieldname) {
		return this.filters.filter(f => {
			return (f.field && f.field.df.fieldname==fieldname);
		})[0];
	}

	get_container_template() {
		return $(`<div class="tag-filters-area">
			<div class="active-tag-filters">
				<button class="btn btn-default btn-xs filter-button text-muted add-filter">
					${__("Add Filter")}
				</button><button class="btn btn-default btn-xs filter-button text-muted clear-filters" style="display: none;">
					${__("Clear Filters")}
				</button>
			</div>
		</div>
		<div class="filter-edit-area"></div>`);
	}

	get_filters_as_object() {
		let filters = this.get_filters().reduce((acc, filter) => {
			return Object.assign(acc, {
				[filter[1]]: [filter[2], filter[3]]
			});
		}, {});
		return filters;
	}

	add_filters_to_filter_group(filters) {

		filters.forEach(filter => {
			this.add_filter(filter[0], filter[1], filter[2], filter[3]);
		});
	}
};
