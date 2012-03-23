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
		if(this.opts.new_doctype) {
			if(wn.boot.profile.can_read.indexOf(this.opts.new_doctype)==-1) {
				this.opts.new_doctype = null;
			} else {
				this.opts.new_doctype = get_doctype_label(this.opts.new_doctype);				
			}
		}
		if(!this.opts.no_result_message) {
			this.opts.no_result_message = 'Nothing to show'
		}
	},
	make: function(opts) {
		if(opts) {
			this.opts = opts;
		}
		this.prepare_opts();
		$.extend(this, this.opts);
		
		$(this.parent).html(repl('\
			<div class="wnlist">\
				<h3 class="title hide">%(title)s</h3>\
				\
				<div class="list-filters hide">\
					<div class="show_filters well">\
						<div>\
							<button class="btn btn-small add-filter-btn">\
								<i class="icon-plus"></i> Add Filter</button>\
						</div>\
						<div class="filter_area"></div>\
					</div>\
				</div>\
				\
				<div style="height: 37px; margin-bottom:9px" class="list-toolbar-wrapper">\
					<div class="list-toolbar btn-group" style="display:inline-block; margin-right: 10px;">\
						<a class="btn btn-small btn-refresh btn-info">\
							<i class="icon-refresh icon-white"></i> Refresh</a>\
						<a class="btn btn-small btn-new">\
							<i class="icon-plus"></i> New</a>\
						<a class="btn btn-small btn-filter">\
							<i class="icon-search"></i> Filter</a>\
					</div>\
					<div style="display:inline-block; width: 24px; margin-left: 4px">\
						<img src="lib/images/ui/button-load.gif" \
						class="img-load"/></div>\
				</div><div style="clear:both"></div>\
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
		
		if(this.show_filters) {
			this.make_filters();			
		}
	},
	add_button: function(html, onclick, before) {
		$(html).click(onclick).insertBefore(this.$w.find('.list-toolbar ' + before));
		this.btn_groupify();
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
			this.$w.find('.btn-new').remove();
		}
		
		// hide-filter
		if(!me.show_filters) {
			this.$w.find('.btn-filter').remove();
		}
		
		// hide-refresh
		if(this.hide_refresh || this.no_refresh) {
			this.$w.find('.btn-refresh').remove();			
		}
			
		// btn group only if more than 1 button
		this.btn_groupify();
	},
	btn_groupify: function() {
		var nbtns = this.$w.find('.list-toolbar a').length;

		if(nbtns == 0) {
			this.$w.find('.list-toolbar-wrapper').toggle(false);
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

		me.set_working(true);
		wn.call({
			method: this.opts.method || 'webnotes.widgets.query_builder.runquery',
			args: this.get_call_args(),
			callback: function(r) { 
				me.set_working(false);
				me.render_results(r) 
			},
			no_spinner: this.opts.no_loading
		});
	},
	set_working: function(flag) {
		this.$w.find('.img-load').toggle(flag);
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
		wn.require('lib/js/legacy/widgets/form/fields.js');
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
		
		// list must be expanded
		if(fieldname) {
			this.$w.find('.show_filters').slideDown();
		}
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
			<option value="in">In</option>\
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
	
	set_field: function(fieldname, fieldtype) {
		var me = this;
		
		// set in fieldname (again)
		var cur = me.field ? {
			fieldname: me.field.df.fieldname,
			fieldtype: me.field.df.fieldtype
		} : {}

		var df = me.fields_by_name[fieldname];
		this.set_fieldtype(df, fieldtype);
			
		// called when condition is changed, 
		// don't change if all is well
		if(me.field && cur.fieldname == fieldname && df.fieldtype == cur.fieldtype) {
			return;
		}
		
		// clear field area and make field
		me.$w.find('.fieldname_select').val(fieldname);
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
		
		return [me.$w.find('.fieldname_select option:selected').attr('table'), 
			me.field.df.fieldname, me.$w.find('.condition').val(), cstr(val)];
	}

});
