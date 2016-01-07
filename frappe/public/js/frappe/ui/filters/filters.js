// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.FilterList = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.filters = [];
		this.$w = this.$parent;
		this.set_events();
	},
	set_events: function() {
		var me = this;
		// show filters
		this.$w.find('.new-filter').bind('click', function() {
			me.add_filter();
		});
	},

	show_filters: function() {
		this.$w.find('.show_filters').toggle();
		if(!this.filters.length) {
			this.add_filter();
			this.filters[0].$w.find(".filter_field input").focus();
		}
	},

	clear_filters: function() {
		$.each(this.filters, function(i, f) { f.remove(true); });
		this.filters = [];
	},

	add_filter: function(doctype, fieldname, condition, value, hidden) {
		this.$w.find('.show_filters').toggle(true);
		var is_new_filter = arguments.length===0;

		if (is_new_filter && this.$w.find(".is-new-filter:visible").length) {
			// only allow 1 new filter at a time!
			return;
		}

		var filter = this.push_new_filter(doctype, fieldname, condition, value);

		if (filter && is_new_filter) {
			filter.$w.addClass("is-new-filter");
		}

		if (filter && hidden) {
			filter.freeze();
			filter.$btn_group.addClass("hide");
		}

		return filter;
	},

	push_new_filter: function(doctype, fieldname, condition, value) {
		if(this.filter_exists(doctype, fieldname, condition, value)) return;

		var filter = new frappe.ui.Filter({
			flist: this,
			_doctype: doctype,
			fieldname: fieldname,
			condition: condition,
			value: value,
        });

		this.filters.push(filter);

		return filter;
	},

	filter_exists: function(doctype, fieldname, condition, value) {
		for(var i in this.filters) {
			if(this.filters[i].field) {
				var f = this.filters[i].get_value();
				if(f[0]==doctype && f[1]==fieldname && f[2]==condition
					&& f[3]==value) return true;

			}
		}
		return false;
	},

	get_filters: function() {
		// get filter values as dict
		var values = [];
		$.each(this.filters, function(i, filter) {
			if(filter.field) {
				filter.freeze();
				values.push(filter.get_value());
			}
		});
		return values;
	},

	// remove hidden filters
	update_filters: function() {
		var fl = [];
		$.each(this.filters, function(i, f) {
			if(f.field) fl.push(f);
		})
		this.filters = fl;
	},

	get_filter: function(fieldname) {
		for(var i in this.filters) {
			if(this.filters[i].field && this.filters[i].field.df.fieldname==fieldname)
				return this.filters[i];
		}
	}
});

frappe.ui.Filter = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		this.doctype = this.flist.doctype;
		this.make();
		this.make_select();
		this.set_events();
	},
	make: function() {
		this.$w = $(frappe.render_template("edit_filter", {})).appendTo(this.flist.$w.find('.filter_area'));
	},
	make_select: function() {
		var me = this;
		this.fieldselect = new frappe.ui.FieldSelect({
			parent: this.$w.find('.fieldname_select_area'),
			doctype: this.doctype,
			filter_fields: this.filter_fields,
			select: function(doctype, fieldname) {
				me.set_field(doctype, fieldname);
			}
		});
		if(this.fieldname) {
			this.fieldselect.set_value(this._doctype || this.doctype, this.fieldname);
		}
	},
	set_events: function() {
		var me = this;

		this.$w.find("a.remove-filter").on("click", function() {
			me.remove();
		});

		this.$w.find(".set-filter-and-run").on("click", function() {
			me.$w.removeClass("is-new-filter");
			me.flist.listobj.run();
		});

		// add help for "in" codition
		me.$w.find('.condition').change(function() {
			var condition = $(this).val();
			if(in_list(["in", "like", "not in", "not like"], condition)) {
				me.set_field(me.field.df.parent, me.field.df.fieldname, 'Data', condition);
				if(!me.field.desc_area) {
					me.field.desc_area = $('<div class="text-muted small">').appendTo(me.field.wrapper);
				}
				// set description
				me.field.desc_area.html((in_list(["in", "not in"], condition)==="in"
					? __("values separated by commas")
					: __("use % as wildcard"))+'</div>');
			} else {
				me.set_field(me.field.df.parent, me.field.df.fieldname, null,
					 condition);
			}
		});

		// set the field
		if(me.fieldname) {
			// pre-sets given (could be via tags!)
			this.set_values(me._doctype, me.fieldname, me.condition, me.value);
		} else {
			me.set_field(me.doctype, 'name');
		}
	},

	remove: function(dont_run) {
		this.$w.remove();
		this.$btn_group && this.$btn_group.remove();
		this.field = null;
		this.flist.update_filters();

		if(!dont_run) {
			this.flist.listobj.dirty = true;
			this.flist.listobj.refresh();
		}
	},

	set_values: function(doctype, fieldname, condition, value) {
		// presents given (could be via tags!)
		this.set_field(doctype, fieldname);
		if(condition) this.$w.find('.condition').val(condition).change();
		if(value!=null) this.field.set_input(value);
	},

	set_field: function(doctype, fieldname, fieldtype, condition) {
		var me = this;

		// set in fieldname (again)
		var cur = me.field ? {
			fieldname: me.field.df.fieldname,
			fieldtype: me.field.df.fieldtype,
			parent: me.field.df.parent,
		} : {};

		var original_docfield = me.fieldselect.fields_by_name[doctype][fieldname];
		if(!original_docfield) {
			msgprint(__("Field {0} is not selectable.", [fieldname]));
			return;
		}

		var df = copy_dict(me.fieldselect.fields_by_name[doctype][fieldname]);

		// all fields shown in filters
		if(df.hidden) {
			df.hidden = 0;
		}

		this.set_fieldtype(df, fieldtype);

		// called when condition is changed,
		// don't change if all is well
		if(me.field && cur.fieldname == fieldname && df.fieldtype == cur.fieldtype &&
			df.parent == cur.parent) {
			return;
		}

		// clear field area and make field
		me.fieldselect.selected_doctype = doctype;
		me.fieldselect.selected_fieldname = fieldname;

		// save old text
		var old_text = null;
		if(me.field) {
			old_text = me.field.get_parsed_value();
		}

		var field_area = me.$w.find('.filter_field').empty().get(0);
		var f = frappe.ui.form.make_control({
			df: df,
			parent: field_area,
			only_input: true,
		})
		f.refresh();

		me.field = f;
		if(old_text && me.field.df.fieldtype===cur.fieldtype)
			me.field.set_input(old_text);

		if(!condition) this.set_default_condition(df, fieldtype);

		// run on enter
		$(me.field.wrapper).find(':input').keydown(function(ev) {
			if(ev.which==13) {
				me.flist.listobj.run();
			}
		})
	},

	set_fieldtype: function(df, fieldtype) {
		// reset
		if(df.original_type)
			df.fieldtype = df.original_type;
		else
			df.original_type = df.fieldtype;

		df.description = ''; df.reqd = 0;

		// given
		if(fieldtype) {
			df.fieldtype = fieldtype;
			return;
		}

		// scrub
		if(df.fieldname=="docstatus") {
			df.fieldtype="Select",
			df.options=[
				{value:0, label:"Draft"},
				{value:1, label:"Submitted"},
				{value:2, label:"Cancelled"},
			]
		} else if(df.fieldtype=='Check') {
			df.fieldtype='Select';
			df.options='No\nYes';
		} else if(['Text','Small Text','Text Editor','Code','Tag','Comments',
			'Dynamic Link','Read Only','Assign'].indexOf(df.fieldtype)!=-1) {
			df.fieldtype = 'Data';
		} else if(df.fieldtype=='Link' && this.$w.find('.condition').val()!="=") {
			df.fieldtype = 'Data';
		}
		if(df.fieldtype==="Data" && (df.options || "").toLowerCase()==="email") {
			df.options = null;
		}
	},

	set_default_condition: function(df, fieldtype) {
		if(!fieldtype) {
			// set as "like" for data fields
			if(df.fieldtype=='Data') {
				this.$w.find('.condition').val('like');
			} else {
				this.$w.find('.condition').val('=');
			}
		}
	},

	get_value: function() {
		return [this.fieldselect.selected_doctype,
			this.field.df.fieldname, this.get_condition(), this.get_selected_value()];
	},

	get_selected_value: function() {
		var val = this.field.get_parsed_value();

		if(this.field.df.original_type == 'Check') {
			val = (val=='Yes' ? 1 :0);
		}

		if(this.get_condition().indexOf('like', 'not like')!==-1) {
			// automatically append wildcards
			if(val) {
				if(val.slice(0,1) !== "%") {
					val = "%" + val;
				}
				if(val.slice(-1) !== "%") {
					val = val + "%";
				}
			}
		} else if(in_list(["in", "not in"], this.get_condition())) {
			val = $.map(val.split(","), function(v) { return strip(v); });
		} if(val === '%') {
			val = "";
		}

		return val;
	},

	get_condition: function() {
		return this.$w.find('.condition').val();
	},

	freeze: function() {
		if(this.$btn_group) {
			// already made, just hide the condition setter
			this.set_filter_button_text();
			this.$w.toggle(false);
			return;
		}

		var me = this;

		// add a button for new filter if missing
		this.$btn_group = $('<div class="btn-group">\
			<button class="btn btn-default btn-xs toggle-filter"\
				title="'+__("Edit Filter")+'">\
				%(label)s %(condition)s "%(value)s"\
			</button>\
			<button class="btn btn-default btn-xs remove-filter"\
				title="'+__("Remove Filter")+'">\
				<i class="icon-remove text-muted"></i>\
			</button></div>')
			.insertAfter(this.flist.$w.find(".set-filters .new-filter"));

		this.set_filter_button_text();

		this.$btn_group.find(".remove-filter").on("click", function() {
			me.remove();
		});

		this.$btn_group.find(".toggle-filter").on("click", function() {
			me.$w.toggle();
		})
		this.$w.toggle(false);
	},

	set_filter_button_text: function() {
		var value = this.get_selected_value();

		if(this.field.df.fieldname==="docstatus") {
			value = {0:"Draft", 1:"Submitted", 2:"Cancelled"}[value] || value;
		} else if(this.field.df.original_type==="Check") {
			value = {0:"No", 1:"Yes"}[cint(value)];
		} else if (in_list(["Date", "Datetime"], this.field.df.fieldtype)) {
			value = frappe.datetime.str_to_user(value);
		} else {
			value = this.field.get_value();
		}

		this.$btn_group.find(".toggle-filter")
			.html(repl('%(label)s %(condition)s "%(value)s"', {
				label: __(this.field.df.label),
				condition: this.get_condition(),
				value: __(value),
			}));
	}

});

// <select> widget with all fields of a doctype as options
frappe.ui.FieldSelect = Class.extend({
	// opts parent, doctype, filter_fields, with_blank, select
	init: function(opts) {
		var me = this;
		$.extend(this, opts);
		this.fields_by_name = {};
		this.options = [];
		this.$select = $('<input class="form-control">')
			.appendTo(this.parent)
			.on("click", function () { $(this).select(); })
			.autocomplete({
				source: me.options,
				minLength: 0,
				autoFocus: true,
				focus: function(event, ui) {
					event.preventDefault();
				},
				select: function(event, ui) {
					me.selected_doctype = ui.item.doctype;
					me.selected_fieldname = ui.item.fieldname;
					me.$select.val(ui.item.label);
					if(me.select) me.select(ui.item.doctype, ui.item.fieldname);
					return false;
				}
			});

		this.$select.data('ui-autocomplete')._renderItem = function(ul, item) {
			return $(repl('<li class="filter-field-select"><p>%(label)s</p></li>', item))
				.data("item.autocomplete", item)
				.appendTo(ul);
		}

		if(this.filter_fields) {
			for(var i in this.filter_fields)
				this.add_field_option(this.filter_fields[i])
		} else {
			this.build_options();
		}
		this.set_value(this.doctype, "name");
		window.last_filter = this;
	},
	get_value: function() {
		return this.selected_doctype ? this.selected_doctype + "." + this.selected_fieldname : null;
	},
	val: function(value) {
		if(value===undefined) {
			return this.get_value()
		} else {
			this.set_value(value)
		}
	},
	clear: function() {
		this.selected_doctype = null;
		this.selected_fieldname = null;
		this.$select.val("");
	},
	set_value: function(doctype, fieldname) {
		var me = this;
		this.clear();
		if(!doctype) return;

		// old style
		if(doctype.indexOf(".")!==-1) {
			parts = doctype.split(".");
			doctype = parts[0];
			fieldname = parts[1];
		}

		$.each(this.options, function(i, v) {
			if(v.doctype===doctype && v.fieldname===fieldname) {
				me.selected_doctype = doctype;
				me.selected_fieldname = fieldname;
				me.$select.val(v.label);
				return false;
			}
		});
	},
	build_options: function() {
		var me = this;
		me.table_fields = [];
		var std_filters = $.map(frappe.model.std_fields, function(d) {
			var opts = {parent: me.doctype}
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
			})
		}

		// main table
		var main_table_fields = std_filters.concat(frappe.meta.docfield_list[me.doctype]);
		$.each(frappe.utils.sort(main_table_fields, "label", "string"), function(i, df) {
			if(frappe.perm.has_perm(me.doctype, df.permlevel, "read"))
				me.add_field_option(df);
		});

		// child tables
		$.each(me.table_fields, function(i, table_df) {
			if(table_df.options) {
				var child_table_fields = [].concat(frappe.meta.docfield_list[table_df.options]);
				$.each(frappe.utils.sort(child_table_fields, "label", "string"), function(i, df) {
					if(frappe.perm.has_perm(me.doctype, df.permlevel, "read"))
						me.add_field_option(df);
				});
			}
		});
	},

	add_field_option: function(df) {
		var me = this;
		if(me.doctype && df.parent==me.doctype) {
			var label = __(df.label);
			var table = me.doctype;
			if(df.fieldtype=='Table') me.table_fields.push(df);
		} else {
			var label = __(df.label) + ' (' + __(df.parent) + ')';
			var table = df.parent;
		}
		if(frappe.model.no_value_type.indexOf(df.fieldtype)==-1 &&
			!(me.fields_by_name[df.parent] && me.fields_by_name[df.parent][df.fieldname])) {
				this.options.push({
					label: label,
					value: table + "." + df.fieldname,
					fieldname: df.fieldname,
					doctype: df.parent
				})
			if(!me.fields_by_name[df.parent]) me.fields_by_name[df.parent] = {};
			me.fields_by_name[df.parent][df.fieldname] = df;
		}
	},
})
