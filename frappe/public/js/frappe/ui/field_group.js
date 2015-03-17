// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.ui');

frappe.ui.FieldGroup = frappe.ui.form.Layout.extend({
	init: function(opts) {
		$.extend(this, opts);
		this._super();
		$.each(this.fields || [], function(i, f) {
			if(!f.fieldname && f.label) {
				f.fieldname = f.label.replace(/ /g, "_").toLowerCase();
			}
		})
	},
	make: function() {
		if(this.fields) {
			this._super();
			this.refresh();
			// set default
			$.each(this.fields_list, function(i, f) {
				if(f.df["default"])
					f.set_input(f.df["default"]);
			})
			if(!this.no_submit_on_enter) {
				this.catch_enter_as_submit();
			}
		}
	},
	first_button: false,
	catch_enter_as_submit: function() {
		var me = this;
		$(this.body).find('input[type="text"], input[type="password"]').keypress(function(e) {
			if(e.which==13) {
				if(this.has_primary_action) {
					e.preventDefault();
					this.get_primary_btn().trigger("click");
				}
			}
		});
	},
	get_input: function(fieldname) {
		var field = this.fields_dict[fieldname];
		return $(field.txt ? field.txt : field.input);
	},
	get_field: function(fieldname) {
		return this.fields_dict[fieldname];
	},
	get_values: function() {
		var ret = {};
		var errors = [];
		for(var key in this.fields_dict) {
			var f = this.fields_dict[key];
			if(f.get_parsed_value) {
				var v = f.get_parsed_value();

				if(f.df.reqd && !v)
					errors.push('- ' + __(f.df.label) + "<br>");

				if(v) ret[f.df.fieldname] = v;
			}
		}
		if(errors.length) {
			msgprint($.format('<i class="icon-warning-sign"></i>\
						<b>{0}</b>:\
						<br/><br/>\
						{1}', [__('Missing Values Required'), errors.join('\n')]));
			return null;
		}
		return ret;
	},
	get_value: function(key) {
		var f = this.fields_dict[key];
		return f && (f.get_parsed_value ? f.get_parsed_value() : null);
	},
	set_value: function(key, val){
		var f = this.fields_dict[key];
		if(f) {
			f.set_input(val);
		}
	},
	set_input: function(key, val) {
		return this.set_value(key, val);
	},
	set_values: function(dict) {
		for(var key in dict) {
			if(this.fields_dict[key]) {
				this.set_value(key, dict[key]);
			}
		}
	},
	clear: function() {
		for(key in this.fields_dict) {
			var f = this.fields_dict[key];
			if(f) {
				f.set_input(f.df['default'] || '');
			}
		}
	},
});
