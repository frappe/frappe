// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.FilterList = Class.extend({
	init(opts) {
		$.extend(this, opts);
		this.wrapper = this.parent;
		this.filters = [];
		this.stats = [];
		this.make();
	},

	make() {
		console.log("this", this);
		this.wrapper.append(this.get_container_template());
		this.set_events();
	},

	set_events() {
		this.wrapper.find('.add-filter').bind('click', this.add_filter.bind(this));
	},

	add_filter(doctype, fieldname, condition, value, hidden) {
		// adds a new filter, returns true if filter has been added

		// allow equal to be used as like
		let base_filter = this.base_list.page.fields_dict[fieldname];
		if (base_filter
			&& (base_filter.df.condition==condition
				|| (condition==='=' && base_filter.df.condition==='like'))) {
			// if filter exists in base_list, then exit
			this.base_list.page.fields_dict[fieldname].set_input(value);

			return true;
		}

		if(doctype && fieldname
			&& !frappe.meta.has_field(doctype, fieldname)
			&& !in_list(frappe.model.std_fields_list, fieldname)) {
			frappe.msgprint({
				message: __('Filter {0} missing', [fieldname.bold()]),
				title: 'Invalid Filter',
				indicator: 'red'
			});
			return false;
		}

		this.wrapper.find('.tag-filters-area').toggle(true);
		var is_new_filter = arguments.length===0;

		if (is_new_filter && this.wrapper.find(".new-filter:visible").length) {
			// only allow 1 new filter at a time!
			return false;
		}

		var filter = this.add_new_filter(doctype, fieldname, condition, value);
		if (!filter) return;

		if (filter && is_new_filter) {
			filter.wrapper.addClass("new-filter");
		} else {
			filter.freeze();
		}

		if (hidden) {
			filter.$btn_group.addClass("hide");
		}

		return true;
	},

	add_new_filter(doctype, fieldname, condition, value) {
		if(this.filter_exists([doctype, fieldname, condition, value])) {
			return;
		}
		// {}: Clear page filter fieldname field
		this._add_new_filter(doctype, fieldname, condition, value);
	},

	_add_new_filter(doctype, fieldname, condition, value) {
		var filter = new frappe.ui.Filter({
			flist: this,
			_doctype: doctype,
			fieldname: fieldname,
			condition: condition,
			value: value
		});
		this.filters.push(filter);
		return filter;
	},

	filter_exists(filter_value) {
		// filter_value of form: [doctype, fieldname, condition, value]
		let exists = false;
		this.filters.filter(f => f.field).map(f => {
			let f_value = f.get_value();
			let value = filter_value[3];
			let equal = frappe.utils.arrays_equal;

			if(equal(f_value, filter_value) ||
				(Array.isArray(value) &&
				equal(value, f_value[3]))) {
					exists = true;
				}
		});
		return exists;
	},

	get_filters() {
		return this.filters.filter(f => f.field).map(f => {
			f.freeze();
			return f.get_value();
		});
		// {}: this.base_list.update_standard_filters(values);
	},

	update_filters() {
		this.filters = this.filters.filter(f => f.field); // remove hidden filters
	},

	clear_filters() {
		$.each(this.filters, function(i, f) { f.remove(true); });
		// {}: Clear page filters, .date-range-picker (called list run())
		this.filters = [];
	},

	get_filter(fieldname) {
		return this.filters.filter(f => {
			return (f.field && f.field.df.fieldname==fieldname);
		})[0];
	},

	get_formatted_value(field, value){
		if(field.df.fieldname==="docstatus") {
			value = {0:"Draft", 1:"Submitted", 2:"Cancelled"}[value] || value;
		} else if(field.df.original_type==="Check") {
			value = {0:"No", 1:"Yes"}[cint(value)];
		}
		return frappe.format(value, field.df, {only_value: 1});
	},

	get_container_template() {
		return $(`<div class="tag-filters-area">
			<div class="active-tag-filters">
				<button class="btn btn-default btn-xs add-filter text-muted">
						${__("Add Filter")}
				</button>
			</div>
		</div>
		<div class="filter-update-area"></div>`);
	}
});
