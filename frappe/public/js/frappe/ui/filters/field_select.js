// <select> widget with all fields of a doctype as options
frappe.ui.FieldSelect = Class.extend({
	// opts parent, doctype, filter_fields, with_blank, select
	init(opts) {
		var me = this;
		$.extend(this, opts);
		this.fields_by_name = {};
		this.options = [];
		this.$input = $('<input class="form-control">')
			.appendTo(this.parent)
			.on("click", function () { $(this).select(); });
		this.select_input = this.$input.get(0);
		this.awesomplete = new Awesomplete(this.select_input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: me.options,
			item(item) {
				return $(repl('<li class="filter-field-select"><p>%(label)s</p></li>', item))
					.data("item.autocomplete", item)
					.get(0);
			}
		});
		this.$input.on("awesomplete-select", function(e) {
			var o = e.originalEvent;
			var value = o.text.value;
			var item = me.awesomplete.get_item(value);
			me.selected_doctype = item.doctype;
			me.selected_fieldname = item.fieldname;
			if(me.select) me.select(item.doctype, item.fieldname);
		});
		this.$input.on("awesomplete-selectcomplete", function(e) {
			var o = e.originalEvent;
			var value = o.text.value;
			var item = me.awesomplete.get_item(value);
			me.$input.val(item.label);
		});

		if(this.filter_fields) {
			for(var i in this.filter_fields)
				this.add_field_option(this.filter_fields[i]);
		} else {
			this.build_options();
		}
		this.set_value(this.doctype, "name");
	},
	get_value() {
		return this.selected_doctype ? this.selected_doctype + "." + this.selected_fieldname : null;
	},
	val(value) {
		if(value===undefined) {
			return this.get_value();
		} else {
			this.set_value(value);
		}
	},
	clear() {
		this.selected_doctype = null;
		this.selected_fieldname = null;
		this.$input.val("");
	},
	set_value(doctype, fieldname) {
		var me = this;
		this.clear();
		if(!doctype) return;

		// old style
		if(doctype.indexOf(".")!==-1) {
			var parts = doctype.split(".");
			doctype = parts[0];
			fieldname = parts[1];
		}

		$.each(this.options, function(i, v) {
			if(v.doctype===doctype && v.fieldname===fieldname) {
				me.selected_doctype = doctype;
				me.selected_fieldname = fieldname;
				me.$input.val(v.label);
				return false;
			}
		});
	},
	build_options() {
		var me = this;
		me.table_fields = [];
		var std_filters = $.map(frappe.model.std_fields, function(d) {
			var opts = {parent: me.doctype};
			if(d.fieldname=="name") opts.options = me.doctype;
			return $.extend(copy_dict(d), opts);
		});

		// add parenttype column
		var doctype_obj = locals['DocType'][me.doctype];
		if(doctype_obj && cint(doctype_obj.istable)) {
			std_filters = std_filters.concat([{
				fieldname: 'parent',
				fieldtype: 'Data',
				label: 'Parent',
				parent: me.doctype,
			}]);
		}

		// blank
		if(this.with_blank) {
			this.options.push({
				label:"",
				value:"",
			});
		}

		// main table
		var main_table_fields = std_filters.concat(frappe.meta.docfield_list[me.doctype]);
		$.each(frappe.utils.sort(main_table_fields, "label", "string"), function(i, df) {
			// show fields where user has read access and if report hide flag is not set
			if(frappe.perm.has_perm(me.doctype, df.permlevel, "read") && !df.report_hide)
				me.add_field_option(df);
		});

		// child tables
		$.each(me.table_fields, function(i, table_df) {
			if(table_df.options) {
				var child_table_fields = [].concat(frappe.meta.docfield_list[table_df.options]);
				$.each(frappe.utils.sort(child_table_fields, "label", "string"), function(i, df) {
					// show fields where user has read access and if report hide flag is not set
					if(frappe.perm.has_perm(me.doctype, df.permlevel, "read") && !df.report_hide)
						me.add_field_option(df);
				});
			}
		});
	},

	add_field_option(df) {
		if (df.fieldname == 'docstatus' && !frappe.model.is_submittable(this.doctype))
			return;

		var me = this;
		var label, table;
		if(me.doctype && df.parent==me.doctype) {
			label = __(df.label);
			table = me.doctype;
			if(df.fieldtype=='Table') me.table_fields.push(df);
		} else {
			label = __(df.label) + ' (' + __(df.parent) + ')';
			table = df.parent;
		}

		if(frappe.model.no_value_type.indexOf(df.fieldtype) == -1 &&
			!(me.fields_by_name[df.parent] && me.fields_by_name[df.parent][df.fieldname])) {
			this.options.push({
				label: label,
				value: table + "." + df.fieldname,
				fieldname: df.fieldname,
				doctype: df.parent
			});
			if(!me.fields_by_name[df.parent]) me.fields_by_name[df.parent] = {};
			me.fields_by_name[df.parent][df.fieldname] = df;
		}
	},
});
