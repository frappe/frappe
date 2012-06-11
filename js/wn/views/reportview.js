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

wn.views.reportview = {
	show: function(dt, rep_name) {
		wn.require('js/report-legacy.js');
		dt = get_label_doctype(dt);

		if(!_r.rb_con) {
			// first load
			_r.rb_con = new _r.ReportContainer();
		}

		_r.rb_con.set_dt(dt, function(rb) { 
			if(rep_name) {
				var t = rb.current_loaded;
				rb.load_criteria(rep_name);

				// if loaded, then run
				if((rb.dt) && (!rb.dt.has_data() || rb.current_loaded!=t)) {
					rb.dt.run();
				}
			}

			// show
			if(!rb.forbidden) {
				wn.container.change_to('Report Builder');
			}
		} );
	}
}

// Routing Rules
// --------------
// `Report` shows list of all pages from which you can start a report + all saved reports
// (module wise)
// `Report/[doctype]` shows report for that doctype
// `Report/[doctype]/[report_name]` loads report with that name

wn.views.reportview2 = {
	show: function(dt) {
		var page_name = wn.get_route_str();
		if(wn.pages[page_name]) {
			wn.container.change_to(wn.pages[page_name]);
		} else {
			var route = wn.get_route();
			if(route[1]) {
				new wn.views.ReportViewPage(route[1], route[2]);				
			} else {
				wn.set_route('404');
			}
		}
	}
}

wn.views.ReportViewPage = Class.extend({
	init: function(doctype, docname) {
		this.doctype = doctype;
		this.docname = docname;
		this.page_name = wn.get_route_str();
		this.make_page();

		var me = this;
		wn.model.with_doctype(doctype, function() {
			me.make_report_view();
			if(docname) {
				wn.model.with_doc('Report', docname, function(r) {
					me.reportview.set_columns_and_filters(JSON.parse(locals['Report'][docname].json));
					me.reportview.run();
				});
			} else {
				me.reportview.run();
			}
		});

	},
	make_page: function() {
		this.page = wn.container.add_page(this.page_name);
		wn.ui.make_app_page({parent:this.page, 
			single_column:true});
		wn.container.change_to(this.page_name);
	},
	make_report_view: function() {
		// add breadcrumbs
		wn.views.breadcrumbs($('<span>').appendTo(this.page.appframe.$titlebar), 
			locals.DocType[this.doctype].module);
			
		this.reportview = new wn.views.ReportView(this.doctype, this.docname, this.page)
	}
})

wn.views.ReportView = wn.ui.Listing.extend({
	init: function(doctype, docname, page) {
		var me = this;
		$(page).find('.layout-main').html('Loading Report...');
		this.import_slickgrid();
		$(page).find('.layout-main').empty();
		this.doctype = doctype;
		this.docname = docname;
		this.page = page;
		this.tab_name = '`tab'+doctype+'`';
		this.setup();
	},
	import_slickgrid: function() {
		wn.require('js/lib/slickgrid/slick.grid.css');
		wn.require('js/lib/slickgrid/slick-default-theme.css');
		wn.require('js/lib/slickgrid/jquery.event.drag.min.js');
		wn.require('js/lib/slickgrid/slick.core.js');
		wn.require('js/lib/slickgrid/slick.grid.js');
		wn.dom.set_style('.slick-cell { font-size: 12px; }');
	},

	set_init_columns: function() {
		// pre-select mandatory columns
		var columns = [['name'], ['owner']];
		$.each(wn.meta.docfield_list[this.doctype], function(i, df) {
			if(df.in_filter && df.fieldname!='naming_series' && df.fieldtype!='Table') {
				columns.push([df.fieldname]);
			}
		});
		this.columns = columns;
	},
	setup: function() {
		var me = this;
		this.make({
			title: 'Report: ' + (this.docname ? (this.doctype + ' - ' + this.docname) : this.doctype),
			appframe: this.page.appframe,
			method: 'webnotes.widgets.doclistview.get',
			get_args: this.get_args,
			parent: $(this.page).find('.layout-main'),
			start: 0,
			page_length: 20,
			show_filters: true,
			new_doctype: this.doctype,
			allow_delete: true,
		});	
		this.make_column_picker();
		this.make_sorter();
		this.make_export();
		this.set_init_columns();
		this.make_save();
	},
	
	// preset columns and filters from saved info
	set_columns_and_filters: function(opts) {
		var me = this;
		if(opts.columns) this.columns = opts.columns;
		if(opts.filters) $.each(opts.filters, function(i, f) {
			// fieldname, condition, value
			me.filter_list.add_filter(f[1], f[2], f[3]);
		});
		
		// first sort
		if(opts.sort_by) this.sort_by_select.val(opts.sort_by);
		if(opts.sort_order) this.sort_order_select.val(opts.sort_order);
		
		// second sort
		if(opts.sort_by_next) this.sort_by_next_select.val(opts.sort_by_next);
		if(opts.sort_order_next) this.sort_order_next_select.val(opts.sort_order_next);
	},
	
	// build args for query
	get_args: function() {
		var me = this;
		return {
			doctype: this.doctype,
			fields: $.map(this.columns, function(v) { return me.get_full_column_name(v) }),
			order_by: this.get_order_by(),
			filters: this.filter_list.get_filters(),
			docstatus: ['0','1','2']
		}
	},
	
	get_order_by: function() {
		// first 
		var order_by = this.get_full_column_name([this.sort_by_select.val()]) 
			+ ' ' + this.sort_order_select.val()
		
		// second
		if(this.sort_by_next_select.val()) {
			order_by += ', ' + this.get_full_column_name([this.sort_by_next_select.val()]) 
				+ ' ' + this.sort_order_next_select.val()
		}
		
		return order_by;
	},
	
	// get table_name.column_name
	get_full_column_name: function(v) {
		return (v[1] ? ('`tab' + v[1] + '`') : this.tab_name) + '.' + v[0];
	},

	// build columns for slickgrid
	build_columns: function() {
		var me = this;
		return $.map(this.columns, function(c) {
			var docfield = wn.meta.docfield_map[c[1] || me.doctype][c[0]];
			coldef = {
				id: c[0],
				field: c[0],
				docfield: docfield,
				name: (docfield ? docfield.label : toTitle(c[0])),
				width: (docfield ? cint(docfield.width) : 120) || 120
			}
						
			if(c[0]=='name') {
				coldef.formatter = function(row, cell, value, columnDef, dataContext) {
					return repl("<a href='#!Form/%(doctype)s/%(name)s'>%(name)s</a>", {
						doctype: me.doctype,
						name: value
					});
				}
			} else if(docfield && docfield.fieldtype=='Link') {
				coldef.formatter = function(row, cell, value, columnDef, dataContext) {
					if(value) {
						return repl("<a href='#!Form/%(doctype)s/%(name)s'>%(name)s</a>", {
							doctype: columnDef.docfield.options,
							name: value
						});						
					} else {
						return '';
					}
				}				
			}
			
			return coldef;
		});
	},
	
	// render data
	render_list: function() {
		var me = this;
		//this.gridid = wn.dom.set_unique_id()
		var columns = [{id:'_idx', field:'_idx', name: 'Sr.', width: 40}].concat(this.build_columns());

		// add sr in data
		$.each(this.data, function(i, v) {
			// add index
			v._idx = i+1;
		});

		var options = {
			enableCellNavigation: true,
			enableColumnReorder: false
		};
		
		var grid = new Slick.Grid(this.$w.find('.result-list')
			.css('border', '1px solid grey')
			.css('height', '500px')
			.get(0), this.data, 
			columns, options);
	},
	
	// setup column picker
	make_column_picker: function() {
		var me = this;
		this.column_picker = new wn.ui.ColumnPicker(this);
		this.page.appframe.add_button('Pick Columns', function() {
			me.column_picker.show(me.columns);
		}, 'icon-th-list');
	},
	
	// setup sorter
	make_sorter: function() {
		var me = this;
		this.sort_dialog = new wn.ui.Dialog({title:'Sorting Preferences'});
		$(this.sort_dialog.body).html('<p class="help">Sort By</p>\
			<div class="sort-column"></div>\
			<div><select class="sort-order" style="margin-top: 10px; width: 60%;">\
				<option value="asc">Ascending</option>\
				<option value="desc">Descending</option>\
			</select></div>\
			<hr><p class="help">Then By (optional)</p>\
			<div class="sort-column-1"></div>\
			<div><select class="sort-order-1" style="margin-top: 10px; width: 60%;">\
				<option value="asc">Ascending</option>\
				<option value="desc">Descending</option>\
			</select></div><hr>\
			<div><button class="btn btn-small btn-info">Update</div>');
		
		// first
		this.sort_by_select = new wn.ui.FieldSelect($(this.sort_dialog.body).find('.sort-column'), 
			this.doctype).$select;
		this.sort_by_select.css('width', '60%');
		this.sort_order_select = $(this.sort_dialog.body).find('.sort-order');
		
		// second
		this.sort_by_next_select = new wn.ui.FieldSelect($(this.sort_dialog.body).find('.sort-column-1'), 
			this.doctype, null, true).$select;
		this.sort_by_next_select.css('width', '60%');
		this.sort_order_next_select = $(this.sort_dialog.body).find('.sort-order-1');
		
		// initial values
		this.sort_by_select.val('modified');
		this.sort_order_select.val('desc');
		
		this.sort_by_next_select.val('');
		this.sort_order_next_select.val('desc');
		
		// button actions
		this.page.appframe.add_button('Sort By', function() {
			me.sort_dialog.show();
		}, 'icon-arrow-down');
		
		$(this.sort_dialog.body).find('.btn-info').click(function() { 
			me.sort_dialog.hide();
			me.run();
		});
	},
	
	// setup export
	make_export: function() {
		var me = this;
		if(wn.user.is_report_manager()) {
			this.page.appframe.add_button('Export', function() {
				var args = me.get_args();
				args.cmd = 'webnotes.widgets.doclistview.export_query'
				open_url_post(wn.request.url, args);
			}, 'icon-download-alt');
		}
	},
	
	// save
	make_save: function() {
		var me = this;
		if(wn.user.is_report_manager()) {
			this.page.appframe.add_button('Save', function() {
				// name
				if(me.docname) {
					var name = me.docname
				} else {
					var name = prompt('Select Report Name');
					if(!name) {
						return;
					}
				}
				
				// callback
				wn.call({
					method: 'webnotes.widgets.doclistview.save_report',
					args: {
						name: name,
						doctype: me.doctype,
						json: JSON.stringify({
							filters: me.filter_list.get_filters(),
							columns: me.columns,
							sort_by: me.sort_by_select.val(),
							sort_order: me.sort_order_select.val(),
							sort_by_next: me.sort_by_next_select.val(),
							sort_order_next: me.sort_order_next_select.val()							
						})
					},
					callback: function(r) {
						if(r.exc) return;
						if(r.message != me.docname)
							wn.set_route('Report2', me.doctype, r.message);
					}
				});
			}, 'icon-upload');
		}
	}
});

wn.ui.ColumnPicker = Class.extend({
	init: function(list) {
		this.list = list;
		this.doctype = list.doctype;
		this.selects = {};
	},
	show: function(columns) {
		wn.require('js/lib/jquery/jquery.ui.sortable.js');
		var me = this;
		if(!this.dialog) {
			this.dialog = new wn.ui.Dialog({
				title: 'Pick Columns',
				width: '400'
			});
		}
		$(this.dialog.body).html('<div class="help">Drag to sort columns</div>\
			<div class="column-list"></div>\
			<div><button class="btn btn-small btn-add"><i class="icon-plus"></i>\
				Add Column</button></div>\
			<hr>\
			<div><button class="btn btn-small btn-info">Update</div>');
		
		// show existing	
		$.each(columns, function(i, c) {
			me.add_column(c);
		});
		
		$(this.dialog.body).find('.column-list').sortable();
		
		// add column
		$(this.dialog.body).find('.btn-add').click(function() {
			me.add_column('name');
		});
		
		// update
		$(this.dialog.body).find('.btn-info').click(function() {
			me.dialog.hide();
			// selected columns as list of [column_name, table_name]
			me.list.columns = [];
			$(me.dialog.body).find('select').each(function() {
				me.list.columns.push([$(this).val(), 
					$(this).find('option:selected').attr('table')]);
			})
			me.list.run();
		});
		
		this.dialog.show();
	},
	add_column: function(c) {
		var w = $('<div style="padding: 5px 5px 5px 35px; background-color: #eee; width: 70%; \
			margin-bottom: 10px; border-radius: 3px; cursor: move;">\
			<a class="close" style="margin-top: 5px;">&times</a>\
			</div>')
			.appendTo($(this.dialog.body).find('.column-list'));
		var fieldselect = new wn.ui.FieldSelect(w, this.doctype);
		fieldselect.$select.css('width', '90%').val(c);
		w.find('.close').click(function() {
			$(this).parent().remove();
		});
	}
});