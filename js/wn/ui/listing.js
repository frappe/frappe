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

// new re-factored Listing object
// uses FieldGroup for rendering filters
// removed rarely used functionality
//
// opts:
//   parent

//   method (method to call on server)
//   args (additional args to method)
//   get_args (method to return args as dict)

//   show_filters [false]
//   doctype
//   filter_fields (if given, this list is rendered, else built from doctype)

//   query or get_query (will be deprecated)
//   query_max

//   no_result_message ("No result")

//   show_grid [false]

//   page_length (20)
//   hide_refresh (False)
//   new_doctype
//   [function] render_row(parent, data)
//   [function] onrun
//   no_loading (no ajax indicator)

wn.provide('wn.ui');
wn.ui.Listing = Class.extend({
	init: function(opts) {
		this.opts = opts || {};
		this.page_length = 20;
		this.start = 0;
		this.data = [];
		if(opts) {
			this.make();
		}
	},
	prepare_opts: function() {
		if(this.opts.new_doctype)
			this.opts.new_doctype = get_doctype_label(this.opts.new_doctype);
	},
	make: function(opts) {
		if(opts) {
			this.opts = opts;
		}
		$.extend(this, this.opts);
		this.prepare_opts();
		
		$(this.parent).html(repl('\
			<div class="wnlist">\
				<div class="btn-group hide select-view" style="float: right;">\
					<a class="btn btn-small btn-info btn-list">\
						<i class="icon-list icon-white"></i> List</a>\
					<a class="btn btn-small btn-grid">\
						<i class="icon-th"></i> Grid</a>\
				</div>\
				\
				<h3 class="title hide">%(title)s</h3>\
				<div style="height: 30px;">\
					<div class="list-toolbar" style="float: left;">\
						<a class="btn btn-small btn-refresh btn-info">\
							<i class="icon-refresh icon-white"></i> Refresh</a>\
						<a class="btn btn-small btn-new">\
							<i class="icon-plus"></i> New %(new_doctype)s</a>\
						<a class="btn btn-small btn-filter">\
							<i class="icon-search"></i> Filter</a>\
					</div>\
					<img src="lib/images/ui/button-load.gif" \
						class="img-load"/>\
				</div>\
				\
				<div style="clear: both; height: 11px;"></div>\
				<div class="list-filters hide">\
					<div class="show_filters well">\
						<div class="filter_area"></div>\
						<div>\
							<button class="btn btn-small add-filter-btn">\
								<i class="icon-plus"></i> Add Filter</button>\
						</div>\
					</div>\
				</div>\
				\
				<div class="no-result help hide">\
					%(no_result_message)s\
				</div>\
				\
				<div class="result">\
					<div class="result-list"></div>\
					<div class="result-grid hide"></div>\
				</div>\
				\
				<div class="paging-button">\
					<button class="btn btn-small btn-more hide">More...</div>\
				</div>\
			</div>\
		', this.opts));
		this.$w = $(this.parent).find('.wnlist');
		this.set_events();
		this.make_filters();
	},
	show_view: function($btn, $div, $btn_unsel, $div_unsel) {
		$btn_unsel.removeClass('btn-info');
		$btn_unsel.find('i').removeClass('icon-white');
		$div_unsel.toggle(false);

		$btn.addClass('btn-info');
		$btn.find('i').addClass('icon-white');
		$div.toggle(true);
	},
	set_events: function() {
		var me = this;
	
		// run
		this.$w.find('.btn-refresh').click(function() {
			me.run();
		});

		// next page
		this.$w.find('.btn-more').click(function() {
			me.run({append: true });
		});
		
		// show list view
		this.$w.find('.btn-list').click(function() {
			me.show_view($(this), me.$w.find('.result-list'),
				me.$w.find('.btn-grid'), me.$w.find('.result-grid'))
		});

		// show grid view
		this.$w.find('.btn-grid').click(function() {
			me.show_view($(this), me.$w.find('.result-grid'),
				me.$w.find('.btn-list'), me.$w.find('.result-list'))
		});
		
		// title
		if(this.title) {
			this.$w.find('h3').html(this.title).toggle(true);
		}
		
		// new
		if(this.new_doctype) {
			this.$w.find('.btn-new').toggle(true).click(function() {
				newdoc(me.new_doctype);
			})
		} else {
			this.$w.find('.btn-new').toggle(false).attr('hidden', 'hidden');
		}
		
		// hide-filter
		if(!me.show_filters) {
			this.$w.find('.btn-filter').toggle(false).attr('hidden', 'hidden');
		}
		
		// hide-refresh
		if(this.hide_refresh || this.no_refresh) {
			this.$w.find('.btn-refresh').toggle(false).attr('hidden', 'hidden');			
		}
		
		// toggle-view
		if(this.show_grid) {
			this.$w.find('.select-view').toggle(true);
		}
		
		// btn group only if more than 1 button
		if(this.$w.find('.list-toolbar a[hidden!="hidden"]').length>1) {
			this.$w.find('.list-toolbar').addClass('btn-group')
		}
	},
	make_filters: function() {
		this.filter_list = new wn.ui.FilterList({
			listobj: this, 
			$parent: this.$w.find('.list-filters').toggle(true),
			doctype: this.doctype,
			filter_fields: this.filter_fields
		});
	},

	clear: function() {
		this.data = [];
		this.$w.find('.result-list').empty();
		this.$w.find('.result').toggle(true);
		this.$w.find('.no-result').toggle(false);
		this.start = 0;
	},
	run: function() {
		// in old - arguments: 0 = callback, 1 = append
		var me = this;
		var a0 = arguments[0]; var a1 = arguments[1];
		
		if(a0 && typeof a0=='function')
			this.onrun = a0;
		if(a0 && a0.callback)
			this.onrun = a0.callback;
		if(!a1 && !(a0 && a0.append)) 
			this.start = 0;		

		me.$w.find('.img-load').toggle(true);
		wn.call({
			method: this.opts.method || 'webnotes.widgets.query_builder.runquery',
			args: this.get_call_args(),
			callback: function(r) { 
				me.$w.find('.img-load').toggle(false);
				me.render_results(r) 
			},
			no_spinner: this.opts.no_loading,
			btn: this.run_btn
		});
	},
	get_call_args: function() {
		// load query
		if(!this.method) {
			this.query = this.get_query ? this.get_query() : this.query;
			this.add_limits();
			var args={ 
				query_max: this.query_max,
				as_dict: 1
			}
			args.simple_query = this.query;
		} else {
			var args = {
				limit_start: this.start,
				limit_page_length: this.page_length
			}
		}
		
		// append user-defined arguments
		if(this.args)
			$.extend(args, this.args)
			
		if(this.get_args) {
			$.extend(args, this.get_args());
		}
		return args;		
	},
	render_results: function(r) {
		if(this.start==0) this.clear();
		
		this.$w.find('.btn-more').toggle(false);

		if(r.message) r.values = r.message;

		if(r.values && r.values.length) {
			this.data = this.data.concat(r.values);
			this.render_list(r.values);
			if(this.show_grid) {
				this.render_grid();				
			}
		} else {
			if(this.start==0) {
				this.$w.find('.result').toggle(false);
				this.$w.find('.no-result').toggle(true);
			}
		}
		
		// callbacks
		if(this.onrun) this.onrun();
		if(this.callback) this.callback(r);
	},
	render_grid: function() {
		//this.gridid = wn.dom.set_unique_id()
		if(this.columns[0].field!='_idx') {
			this.columns = [{field:'_idx', name: 'Sr.', width: 40}].concat(this.columns);
		}
		$.each(this.columns, function(i, c) {
			if(!c.id) c.id = c.field;
		})
		
		// add sr in data
		$.each(this.data, function(i, v) {
			v._idx = i+1;
		})
		
		wn.require('lib/js/lib/slickgrid/slick.grid.css');
		wn.require('lib/js/lib/slickgrid/slick-default-theme.css');
		wn.require('lib/js/lib/slickgrid/jquery.event.drag.min.js');
		wn.require('lib/js/lib/slickgrid/slick.core.js');
		wn.require('lib/js/lib/slickgrid/slick.grid.js');
		
		var options = {
			enableCellNavigation: true,
			enableColumnReorder: false
		};		
		grid = new Slick.Grid(this.$w.find('.result-grid')
			.css('border', '1px solid grey')
			.css('height', '500px')
			.get(0), this.data, 
			this.columns, options);
	    
	},
	render_list: function(values) {		
		var m = Math.min(values.length, this.page_length);
		
		// render the rows
		for(var i=0; i < m; i++) {
			this.render_row(this.add_row(), values[i], this, i);
		}
		
		// extend start
		this.start += m;
		
		// refreh more button
		if(values.length >= this.page_length) 
			this.$w.find('.btn-more').toggle(true);		
	},
	add_row: function() {
		return this.$w.find('.result-list').append('<div class="list-row">')
			.find('.list-row:last').get(0);
	},
	refresh: function() { 
		this.run(); 
	},
	add_limits: function() {
		this.query += ' LIMIT ' + this.start + ',' + (this.page_length+1);
	}	
});


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
		this.listobj.$w.find('.btn-filter').bind('click', function() {
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
			if(f.filter_field)
				values.push(f.get_value());
		})
		return values;
	},
	
	// remove hidden filters
	update_filters: function() {
		var fl = [];
		$.each(this.filters, function(i, f) {
			if(f.filter_field) fl.push(f);
		})
		this.filters = fl;
	}
});

wn.ui.Filter = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		this.doctype = this.flist.doctype;
		this.fields_by_name = {};
		this.make();
		this.make_options();
		this.set_events();
	},
	make: function() {
		this.flist.$w.find('.filter_area').append('<div class="list_filter">\
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
		this.$w = this.flist.$w.find('.list_filter:last-child');
		this.$select = this.$w.find('.fieldname_select');		
	},
	make_options: function() {
		if(this.filter_fields) {
			// filters specified explicitly
			for(var i in this.filter_fields)
				this.add_field_option(this.filter_fields[i])
		} else {
			// filters to be built from doctype
			this.render_field_select();			
		}		
	},
	set_events: function() {
		var me = this;
		
		// render fields
		
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
			}
			if(value) {
				me.flist.listobj.run();
			}
			me.flist.update_filters();
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
		me.table_fields = [];
		var std_filters = [
			{fieldname:'name', fieldtype:'Data', label:'ID', parent:me.doctype},
			{fieldname:'modified', fieldtype:'Date', label:'Last Modified', parent:me.doctype},
			{fieldname:'owner', fieldtype:'Data', label:'Created By', parent:me.doctype},
			{fieldname:'_user_tags', fieldtype:'Data', label:'Tags', parent:me.doctype}
		];
		
		// main table
		$.each(std_filters.concat(fields_list[me.doctype]), function(i, df) {
			me.add_field_option(df);
		});
		
		// child tables
		$.each(me.table_fields, function(i,table_df) {
			if(table_df.options) {
				$.each(fields_list[table_df.options], function(i, df) {
					me.add_field_option(df);
				});				
			}
		})
	},
	
	add_field_option: function(df) {
		var me = this;
		if(me.doctype && df.parent==me.doctype) {
			var label = df.label;
			var table = get_label_doctype(me.doctype);
			if(df.fieldtype=='Table') me.table_fields.push(df);					
		} else {
			var label = df.label + ' (' + df.parent + ')';
			var table = df.parent;
		}
		if(wn.model.no_value_type.indexOf(df.fieldtype)==-1 && 
			!me.fields_by_name[df.fieldname]) {
			this.$select.append($('<option>', {
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
		var field_area = me.$w.find('.filter_field').empty().get(0);

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
