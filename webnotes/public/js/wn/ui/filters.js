// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.ui.FilterList = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.filters = [];
		this.$w = this.$parent;
		this.set_events();
	},
	set_events: function() {
		var me = this;
		// show filters
		this.$w.find('.add-filter-btn').bind('click', function() {
			me.add_filter();
		});
		this.$w.find('.search-btn').bind('click', function() {
			me.listobj.run();
		});
	},
	
	show_filters: function() {
		this.$w.find('.show_filters').toggle();
		if(!this.filters.length)
			this.add_filter();
	},

	clear_filters: function() {
		this.filters = [];
		this.$w.find('.filter_area').empty();
	},
	
	add_filter: function(tablename, fieldname, condition, value) {
		this.push_new_filter(tablename, fieldname, condition, value);
		// list must be expanded
		if(fieldname) {
			this.$w.find('.show_filters').toggle(true);
		}
	},
	
	push_new_filter: function(tablename, fieldname, condition, value) {
		this.filters.push(new wn.ui.Filter({
			flist: this,
			tablename: tablename,
			fieldname: fieldname,
			condition: condition,
			value: value
        }));
	},
	
	get_filters: function() {
		// get filter values as dict
		var values = [];
		$.each(this.filters, function(i, filter) {
			if(filter.field)
				values.push(filter.get_value());
		})
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

wn.ui.Filter = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		this.doctype = this.flist.doctype;
		this.make();
		this.make_select();
		this.set_events();
	},
	make: function() {
		this.flist.$w.find('.filter_area').append('<div class="list_filter row">\
		<div class="fieldname_select_area col-sm-4 form-group"></div>\
		<div class="col-sm-3 form-group">\
			<select class="condition form-control">\
				<option value="=">' + wn._("Equals") + '</option>\
				<option value="like">' + wn._("Like") + '</option>\
				<option value=">=">' + wn._("Greater or equals") + '</option>\
				<option value="<=">' + wn._("Less or equals") + '</option>\
				<option value=">">' + wn._("Greater than") + '</option>\
				<option value="<">' + wn._("Less than") + '</option>\
				<option value="in">' + wn._("In") + '</option>\
				<option value="!=">' + wn._("Not equals") + '</option>\
			</select>\
		</div>\
		<div class="filter_field col-sm-4 col-xs-11"></div>\
		<div class="col-sm-1 col-xs-1" style="margin-top: 8px;">\
			<a class="close">&times;</a>\
		</div>\
		</div>');
		this.$w = this.flist.$w.find('.list_filter:last-child');
	},
	make_select: function() {
		var me = this;
		this.fieldselect = new wn.ui.FieldSelect({
			parent: this.$w.find('.fieldname_select_area'), 
			doctype: this.doctype, 
			filter_fields: this.filter_fields, 
			select: function(doctype, fieldname) {
				me.set_field(doctype, fieldname);
			}
		});
	},
	set_events: function() {
		var me = this;
		
		this.$w.find('a.close').bind('click', function() { 
			me.$w.css('display','none');
			var value = me.field.get_parsed_value();
			var fieldname = me.field.df.fieldname;
			me.field = null;
			
			// hide filter section
			if(!me.flist.get_filters().length) {
				me.flist.$w.find('.set_filters').toggle(true);
				me.flist.$w.find('.show_filters').toggle(false);
			}
						
			me.flist.update_filters();
			me.flist.listobj.dirty = true;
			me.flist.listobj.run();
			return false;
		});

		// add help for "in" codition
		me.$w.find('.condition').change(function() {
			if($(this).val()=='in') {
				me.set_field(me.field.df.parent, me.field.df.fieldname, 'Data');
				if(!me.field.desc_area)
					me.field.desc_area = $a(me.field.wrapper, 'span', 'help', null,
						'values separated by comma');				
			} else {
				me.set_field(me.field.df.parent, me.field.df.fieldname, null, 
					me.$w.find('.condition').val());				
			}
		});
		
		// set the field
		if(me.fieldname) {
			// presents given (could be via tags!)
			this.set_values(me.tablename, me.fieldname, me.condition, me.value);
		} else {
			me.set_field(me.doctype, 'name');
		}	

	},
		
	set_values: function(tablename, fieldname, condition, value) {
		// presents given (could be via tags!)
		this.set_field(tablename, fieldname);
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
		} : {}

		var original_docfield = me.fieldselect.fields_by_name[doctype][fieldname];

		if(!original_docfield) {
			msgprint("Field " + df.label + " is not selectable.");
			return;
		}


		var df = copy_dict(me.fieldselect.fields_by_name[doctype][fieldname]);
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
		var f = wn.ui.form.make_control({
			df: df,
			parent: field_area,
			only_input: true,
		})
		f.refresh();
		
		me.field = f;
		if(old_text) 
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
		if(df.fieldtype=='Check') {
			df.fieldtype='Select';
			df.options='No\nYes';
		} else if(['Text','Small Text','Text Editor','Code','Tags','Comments'].indexOf(df.fieldtype)!=-1) {
			df.fieldtype = 'Data';				
		} else if(df.fieldtype=='Link' && this.$w.find('.condition').val()!="=") {
			df.fieldtype = 'Data';
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
		var me = this;
		var val = me.field.get_parsed_value();
		var cond = me.$w.find('.condition').val();
		
		if(me.field.df.original_type == 'Check') {
			val = (val=='Yes' ? 1 :0);
		}
		
		if(cond=='like') {
			// add % only if not there at the end
			if ((val.length === 0) || (val.lastIndexOf("%") !== (val.length - 1))) {
				val = (val || "") + '%';
			}
		} else if(val === '%') val = null;
		
		return [me.fieldselect.selected_doctype, 
			me.field.df.fieldname, me.$w.find('.condition').val(), val];
	}

});

// <select> widget with all fields of a doctype as options
wn.ui.FieldSelect = Class.extend({
	// opts parent, doctype, filter_fields, with_blank, select
	init: function(opts) {
		$.extend(this, opts);
		this.fields_by_name = {};
		this.options = [];
		this.$select = $('<input class="form-control">').appendTo(this.parent);
		var me = this;
		this.$select.autocomplete({
			source: me.options,
			minLength: 0,
			focus: function(event, ui) {
				me.$select.val(ui.item.label);
				return false;
			},
			select: function(event, ui) {
				me.selected_doctype = ui.item.doctype;
				me.selected_fieldname = ui.item.fieldname;
				me.$select.val(ui.item.label);
				if(me.select) me.select(ui.item.doctype, ui.item.fieldname);
				return false;
			}
		});
		
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
		var std_filters = $.map(wn.model.std_fields, function(d) {
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
		var main_table_fields = std_filters.concat(wn.meta.docfield_list[me.doctype]);
		$.each(wn.utils.sort(main_table_fields, "label", "string"), function(i, df) {
			if(wn.perm.has_perm(me.doctype, df.permlevel, "read"))
				me.add_field_option(df);
		});

		// child tables
		$.each(me.table_fields, function(i, table_df) {
			if(table_df.options) {
				var child_table_fields = [].concat(wn.meta.docfield_list[table_df.options]);
				$.each(wn.utils.sort(child_table_fields, "label", "string"), function(i, df) {
					if(wn.perm.has_perm(me.doctype, df.permlevel, "read"))
						me.add_field_option(df);
				});
			}
		});
	},

	add_field_option: function(df) {
		var me = this;
		if(me.doctype && df.parent==me.doctype) {
			var label = df.label;
			var table = me.doctype;
			if(df.fieldtype=='Table') me.table_fields.push(df);
		} else {
			var label = df.label + ' (' + df.parent + ')';
			var table = df.parent;
		}
		if(wn.model.no_value_type.indexOf(df.fieldtype)==-1 && 
			!(me.fields_by_name[df.parent] && me.fields_by_name[df.parent][df.fieldname])) {
				this.options.push({
					label: wn._(label),
					value: table + "." + df.fieldname,
					fieldname: df.fieldname,
					doctype: df.parent
				})
			if(!me.fields_by_name[df.parent]) me.fields_by_name[df.parent] = {};
			me.fields_by_name[df.parent][df.fieldname] = df;	
		}
	},
})