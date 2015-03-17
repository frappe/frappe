// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.views.CalendarBase = Class.extend({
	add_filters: function() {
		var me = this;
		if(this.filters) {
			$.each(this.filters, function(i, df) {
				df.change = function() {
					me.refresh();
				};
				me.page.add_field(df);
			});
		}
	},
	set_filter: function(doctype, value) {
		var me = this;
		if(this.filters) {
			$.each(this.filters, function(i, df) {
				if(df.options===value)
					me.page.fields_dict[df.fieldname].set_input(value);
					return false;
			});
		}
	},
	get_filters: function() {
		var filter_vals = {},
			me = this;
		if(this.filters) {
			$.each(this.filters, function(i, df) {
				filter_vals[df.fieldname || df.label] =
					me.page.fields_dict[df.fieldname || df.label].get_parsed_value();
			});
		}
		return filter_vals;
	},
	set_filters_from_route_options: function() {
		var me = this;
		if(frappe.route_options) {
			$.each(frappe.route_options, function(k, value) {
				if(me.page.fields_dict[k]) {
					me.page.fields_dict[k].set_input(value);
				};
			})
			frappe.route_options = null;
			me.refresh();
			return false;
		}
	}
})
