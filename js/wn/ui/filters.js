// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//

wn.ui.FilterList = Class.extend({
	init: function(opts) {
		wn.require('js/fields.js');
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
	
	add_filter: function(fieldname, condition, value) {		
		this.push_new_filter(fieldname, condition, value);
		// list must be expanded
		if(fieldname) {
			this.$w.find('.show_filters').toggle(true);
		}
	},
	
	push_new_filter: function(fieldname, condition, value) {
		this.filters.push(new wn.ui.Filter({
			flist: this,
			fieldname: fieldname,
			condition: condition,
			value: value
        }));
	},
	
	get_filters: function() {
		// get filter values as dict
		var values = [];
		$.each(this.filters, function(i, f) {
			if(f.field)
				values.push(f.get_value());
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
			if(this.filters[i].field.df.fieldname==fieldname)
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
		this.flist.$w.find('.filter_area').append('<div class="list_filter">\
		<span class="fieldname_select_area"></span>\
		<select class="condition">\
			<option value="=">Equals</option>\
			<option value="like">Like</option>\
			<option value=">=">Greater or equals</option>\
			<option value="<=">Less or equals</option>\
			<option value=">">Greater than</option>\
			<option value="<">Less than</option>\
			<option value="in">In</option>\
			<option value="!=">Not equals</option>\
		</select>\
		<span class="filter_field"></span>\
		<a class="close">&times;</a>\
		</div>');
		this.$w = this.flist.$w.find('.list_filter:last-child');
	},
	make_select: function() {
		this.fieldselect = new wn.ui.FieldSelect(this.$w.find('.fieldname_select_area'), 
			this.doctype, this.filter_fields);
	},
	set_events: function() {
		var me = this;
		
		// render fields		
		this.fieldselect.$select.bind('change', function() {
			me.set_field(this.value);
		});

		this.$w.find('a.close').bind('click', function() { 
			me.$w.css('display','none');
			var value = me.field.get_value();
			me.field = null;
			if(!me.flist.get_filters().length) {
				me.flist.$w.find('.set_filters').toggle(true);
				me.flist.$w.find('.show_filters').toggle(false);
			}
			if(value) {
				me.flist.listobj.run();
			}
			me.flist.update_filters();
			return false;
		});

		// add help for "in" codition
		me.$w.find('.condition').change(function() {
			if($(this).val()=='in') {
				me.set_field(me.field.df.fieldname, 'Data');
				if(!me.field.desc_area)
					me.field.desc_area = $a(me.field.wrapper, 'span', 'help', null,
						'values separated by comma');				
			} else {
				me.set_field(me.field.df.fieldname);				
			}
		});
		
		// set the field
		if(me.fieldname) {
			// presents given (could be via tags!)
			this.set_values(me.fieldname, me.condition, me.value);
		} else {
			me.set_field('name');
		}	

	},
	
	set_values: function(fieldname, condition, value) {
		// presents given (could be via tags!)
		this.set_field(fieldname);
		if(condition) this.$w.find('.condition').val(condition).change();
		if(value) this.field.set_input(value)
		
	},
	
	set_field: function(fieldname, fieldtype) {
		var me = this;
		
		// set in fieldname (again)
		var cur = me.field ? {
			fieldname: me.field.df.fieldname,
			fieldtype: me.field.df.fieldtype
		} : {}

		var df = me.fieldselect.fields_by_name[fieldname];
		this.set_fieldtype(df, fieldtype);
			
		// called when condition is changed, 
		// don't change if all is well
		if(me.field && cur.fieldname == fieldname && df.fieldtype == cur.fieldtype) {
			return;
		}
		
		// clear field area and make field
		me.fieldselect.$select.val(fieldname);
		var field_area = me.$w.find('.filter_field').empty().get(0);
		f = make_field(df, null, field_area, null, 0, 1);
		f.df.single_select = 1;
		f.not_in_form = 1;
		f.with_label = 0;
		f.refresh();
		me.field = f;
		
		this.set_default_condition(df, fieldtype);
		
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
		} else if(['Text','Text Editor','Code','Link'].indexOf(df.fieldtype)!=-1) {
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
		var val = me.field.get_value();
		var cond = me.$w.find('.condition').val();
		
		if(me.field.df.original_type == 'Check') {
			val = (val=='Yes' ? 1 :0);
		}
		
		if(cond=='like') {
			val = val + '%';
		}
		
		return [me.fieldselect.$select.find('option:selected').attr('table'), 
			me.field.df.fieldname, me.$w.find('.condition').val(), cstr(val)];
	}

});

// <select> widget with all fields of a doctype as options
wn.ui.FieldSelect = Class.extend({
	init: function(parent, doctype, filter_fields, with_blank) {
		this.doctype = doctype;
		this.fields_by_name = {};
		this.with_blank = with_blank;
		this.$select = $('<select>').appendTo(parent);
		if(filter_fields) {
			for(var i in filter_fields)
				this.add_field_option(this.filter_fields[i])			
		} else {
			this.build_options();
		}
	},
	build_options: function() {
		var me = this;
		me.table_fields = [];
		var std_filters = [
			{fieldname:'name', fieldtype:'Data', label:'ID', parent:me.doctype},
			{fieldname:'modified', fieldtype:'Date', label:'Last Modified',
				parent:me.doctype},
			{fieldname:'owner', fieldtype:'Data', label:'Created By',
				parent:me.doctype},
			{fieldname:'creation', fieldtype:'Date', label:'Created On',
				parent:me.doctype},
			{fieldname:'_user_tags', fieldtype:'Data', label:'Tags',
				parent:me.doctype},
			{fieldname:'docstatus', fieldtype:'Int', label:'Doc Status',
				parent:me.doctype},
		];
		
		// add parenttype column
		var doctype_obj = locals['DocType'][me.doctype];
		if(doctype_obj && cint(doctype_obj.istable)) {
			std_filters = std_filters.concat([{
				fieldname: 'parent',
				fieldtype: 'Data',
				label: 'Parent',
				parent: me.doctype
			}]);
		}
		
		// blank
		if(this.with_blank) {
			this.$select.append($('<option>', {
				value: ''
			}).text(''));
		}

		// main table
		$.each(std_filters.concat(wn.meta.docfield_list[me.doctype]), function(i, df) {
			me.add_field_option(df);
		});

		// child tables
		$.each(me.table_fields, function(i,table_df) {
			if(table_df.options) {
				$.each(wn.meta.docfield_list[table_df.options], function(i, df) {
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
			!(me.fields_by_name[df.fieldname] && me.fields_by_name[df.fieldname]['parent'] == df.parent)) {
			this.$select.append($('<option>', {
				value: df.fieldname,
				table: table
			}).text(label));
			me.fields_by_name[df.fieldname] = df;						
		}
	}
})