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

wn.provide('wn.pages.doclistview');

wn.pages.doclistview.pages = {};
wn.pages.doclistview.show = function(doctype) {
	var pagename = doctype + ' List';
	if(!wn.pages.doclistview.pages[pagename]) {
		var page = page_body.add_page(pagename);
		page.doclistview = new wn.pages.DocListView(doctype, page);
		wn.pages.doclistview.pages[pagename] = page;
	}
	page_body.change_to(pagename);
}

wn.pages.DocListView = Class.extend({
	init: function(doctype, page) {
		this.doctype = doctype;
		this.wrapper = page;
		this.label = get_doctype_label(doctype);
		this.label = (this.label.toLowerCase().substr(-4) == 'list') ?
		 	this.label : (this.label + ' List')	
		
		this.make();
		this.load_doctype();
	},
	make: function() {
		$(this.wrapper).html('<div class="layout-wrapper layout-wrapper-background">\
			<div class="layout-main-section">\
				<a class="close" onclick="window.history.back();">&times;</a>\
				<h1>List</h1>\
				<hr>\
				<div id="list-filters"></div>\
				<button class="btn btn-small btn-info run-btn" style="margin-top: 11px">\
					<i class="icon-refresh icon-white"></i> Refresh</button>\
				<div id="list-body"></div>\
			</div>\
			<div class="layout-side-section">\
			</div>\
		</div>');
		// filter button
		$(this.wrapper).find('.run-btn').click(function() {
			me.list.run();
		});
	},
	load_doctype: function() {
		var me = this;
		wn.call({
			method: 'webnotes.widgets.form.load.getdoctype',
			args: {doctype:this.doctype},
			callback: function() {
				me.make_filters();
				me.make_list();
			}
		});
	},
	make_filters: function() {
		this.filter_list = new wn.ui.FilterList(this, $('#list-filters').get(0), this.doctype);
	},
	make_list: function() {
		var me = this;
		this.list = new wn.widgets.Listing({
			parent: $('#list-body').get(0),
			method: 'webnotes.widgets.doclistview.get',
			args: {
				doctype: this.doctype,
				subject: locals.DocType[this.doctype].subject,
			},
			get_args: function() {
				return {filters: JSON.stringify(me.filter_list.get_filters())}
			},
			render_row: function(row, data) {
				row.innerHTML = data;
			},
			hide_refresh: true
		});
		this.list.run();
	}
});

wn.require('lib/css/ui/filter.css');

wn.ui.FilterList = Class.extend({
	init: function(list_obj, parent, doctype) {
		this.filters = [];
		this.list_obj = list_obj;
		this.doctype = doctype;
		this.make(parent);
		this.set_events();
	},
	make: function(parent) {
		$(parent).html('<div>\
			<span class="link_type set_filters">Filter this list</span>\
		</div>\
		<div class="show_filters well">\
			<div class="filter_area"></div>\
			<div>\
				<button class="btn btn-small add-filter-btn">\
					<i class="icon-plus"></i> Add Filter</button>\
			</div>\
		</div>');
		
		this.$w = $(parent);
	},
	set_events: function() {
		var me = this;
		// show filters
		this.$w.find('.set_filters').bind('click', function() {
			me.$w.find('.show_filters').slideToggle();
			if(!me.filters.length)
				me.add_filter();
		});

		// show filters
		this.$w.find('.add-filter-btn').bind('click', function() {
			me.add_filter();
		});
			
	},
	
	add_filter: function(fieldname, condition, value) {
		this.filters.push(new wn.ui.Filter(this, this.doctype, fieldname, condition, value));
	},
	
	get_filters: function() {
		// get filter values as dict
		var values = [];
		$.each(this.filters, function(i, f) {
			if(f.filter_field)
				values.push(f.get_value());
		})
		return values;
	}
});

wn.ui.Filter = Class.extend({
	init: function(flist, doctype, fieldname, condition, value) {
		flist.$w.find('.filter_area').append('<div class="list_filter">\
		<select class="fieldname_select"></select>\
		<select class="condition">\
			<option value="=">Equals</option>\
			<option value="like">Like</option>\
			<option value=">=">Greater or equals</option>\
			<option value=">=">Less or equals</option>\
			<option value=">">Greater than</option>\
			<option value="<">Less than</option>\
			<option value="!=">Not equals</option>\
		</select>\
		<span class="filter_field"></span>\
		<a class="close">&times;</a>\
		</div>');
		this.fields_by_name = {};
		this.flist = flist;
		this.$w = this.flist.$w.find('.list_filter:last-child');
		this.doctype = doctype;
		this.fieldname = fieldname;
		this.condition = condition;
		this.value = value;
		this.set_events();
	},
	set_events: function() {
		var me = this;
		
		// render fields
		this.render_field_select();
		
		this.$w.find('.fieldname_select').bind('change', function() {
			me.set_field(this.value);
		});

		this.$w.find('a.close').bind('click', function() { 
			me.$w.css('display','none');
			var value = me.filter_field.get_value();
			me.filter_field = null;
			if(!me.flist.get_filters().length) {
				me.flist.$w.find('.set_filters').toggle(true);
				me.flist.$w.find('.show_filters').toggle(false);
				me.list_obj.list.run();
			}
			if(value) {
				me.list_obj.list.run();
			}
			return false;
		});
		
		// set the field
		if(me.fieldname) {
			// presents given (could be via tags!)
			me.set_field(me.fieldname);
			if(me.condition) me.$w.find('.condition').val(me.condition)
			if(me.value) me.filter_field.set_input(me.value)
		} else {
			me.set_field('name');
		}

	},
	
	render_field_select: function() {
		var me = this;
		var $fs = me.$w.find('.fieldname_select');
		me.table_fields = [];
		var std_filters = [
			{fieldname:'name', fieldtype:'Data', label:'ID', parent:me.doctype},
			{fieldname:'modified', fieldtype:'Date', label:'Last Modified', parent:me.doctype},
			{fieldname:'owner', fieldtype:'Data', label:'Created By', parent:me.doctype},
			{fieldname:'_user_tags', fieldtype:'Data', label:'Tags', parent:me.doctype}
		];
		
		// main table
		$.each(std_filters.concat(fields_list[me.doctype]), function(i, df) {
			me.add_field_option(df, $fs);
		});
		
		// child tables
		$.each(me.table_fields, function(i,table_df) {
			if(table_df.options) {
				$.each(fields_list[table_df.options], function(i, df) {
					me.add_field_option(df, $fs);
				});				
			}
		})
	},
	
	add_field_option: function(df, $fs) {
		var me = this;
		if(df.parent==me.doctype) {
			var label = df.label;
			var table = get_label_doctype(me.doctype);
			if(df.fieldtype=='Table') me.table_fields.push(df);					
		} else {
			var label = df.label + ' (' + df.parent + ')';
			var table = df.parent;
		}
		if(wn.model.no_value_type.indexOf(df.fieldtype)==-1 && 
			!me.fields_by_name[df.fieldname]) {
			$fs.append($('<option>', {
				value: df.fieldname,
				table: table
			}).text(label));
			me.fields_by_name[df.fieldname] = df;						
		}
	},
	
	set_field: function(fieldname) {
		var me = this;
		// set in fieldname (again)
		me.$w.find('.fieldname_select').val(fieldname);

		wn.require('lib/js/legacy/widgets/form/fields.js');
		var field_area = me.$w.find('.filter_field').get(0);
		field_area.innerHTML = '';

		var df = me.fields_by_name[fieldname];
		df.original_type = df.fieldtype;
		df.description = '';
		if(df.fieldtype=='Check') {
			df.fieldtype='Select';
			df.options='No\nYes';
		} else if(['Text','Text Editor','Code','Link'].indexOf(df.fieldtype)!=-1) {
			df.fieldtype = 'Data';				
		}

		f = make_field(me.fields_by_name[fieldname], null, field_area, null, 0, 1);
		f.df.single_select = 1;
		f.not_in_form = 1;
		f.with_label = 0;
		f.refresh();
		
		me.filter_field = f;
		
		// set as "like" for data fields
		if(df.fieldtype=='Data') {
			me.$w.find('.condition').val('like');
		} else {
			me.$w.find('.condition').val('=');
		}
	},
	
	get_value: function() {
		var me = this;
		var val = me.filter_field.get_value();
		var cond = me.$w.find('.condition').val();
		
		if(me.filter_field.df.original_type == 'Check') {
			val = (val=='Yes' ? 1 :0);
		}
		
		if(cond=='like') {
			val = val + '%';
		}
		
		return [me.$w.find('.fieldname_select option:selected').attr('table'), 
			me.filter_field.df.fieldname, me.$w.find('.condition').val(), val];
	}

});
