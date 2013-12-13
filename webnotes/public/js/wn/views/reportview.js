// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.views.ReportFactory = wn.views.Factory.extend({
	make: function(route) {
		new wn.views.ReportViewPage(route[1], route[2]);
	}
});

wn.views.ReportViewPage = Class.extend({
	init: function(doctype, docname) {
		if(!wn.model.can_get_report(doctype)) {
			wn.show_not_permitted(wn.get_route_str());
			return;
		};

		wn.require("assets/js/slickgrid.min.js");
		
		this.doctype = doctype;
		this.docname = docname;
		this.page_name = wn.get_route_str();
		this.make_page();
		
		var me = this;
		wn.model.with_doctype(this.doctype, function() {
			me.make_report_view();
			if(me.docname) {
				wn.model.with_doc('Report', me.docname, function(r) {
					me.page.reportview.set_columns_and_filters(
						JSON.parse(wn.model.get("Report", me.docname)[0].json));
					me.page.reportview.set_route_filters();
					me.page.reportview.run();
				});
			} else {
				me.page.reportview.set_route_filters();
				me.page.reportview.run();
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
		var module = locals.DocType[this.doctype].module;
		this.page.appframe.set_title(wn._(this.doctype));
		this.page.appframe.add_module_icon(module, this.doctype)
		this.page.appframe.set_views_for(this.doctype, "report");

		this.page.reportview = new wn.views.ReportView({
			doctype: this.doctype, 
			docname: this.docname, 
			page: this.page,
			wrapper: $(this.page).find(".layout-main")
		});
	}
});

wn.views.ReportView = wn.ui.Listing.extend({
	init: function(opts) {
		var me = this;
		$(this.page).find('.layout-main').html(wn._('Loading Report')+'...');
		$(this.page).find('.layout-main').empty();
		$.extend(this, opts);
		this.can_delete = wn.model.can_delete(me.doctype);
		this.tab_name = '`tab'+this.doctype+'`';
		this.setup();
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
		this.page_title = wn._('Report')+ ': ' + wn._(this.docname ? (this.doctype + ' - ' + this.docname) : this.doctype);
		this.page.appframe.set_title(this.page_title)
		this.make({
			appframe: this.page.appframe,
			method: 'webnotes.widgets.reportview.get',
			get_args: this.get_args,
			parent: $(this.page).find('.layout-main'),
			start: 0,
			page_length: 20,
			show_filters: true,
			new_doctype: this.doctype,
			allow_delete: true,
		});
		this.make_delete();
		this.make_column_picker();
		this.make_sorter();
		this.make_export();
		this.set_init_columns();
		this.make_save();
		this.set_tag_and_status_filter();
	},

	set_init_columns: function() {
		// pre-select mandatory columns
		var columns = wn.defaults.get_default("_list_settings:" + this.doctype);
		if(!columns) {
			var columns = [['name', this.doctype],];
			$.each(wn.meta.docfield_list[this.doctype], function(i, df) {
				if(df.in_filter && df.fieldname!='naming_series'
					&& !in_list(wn.model.no_value_type, df.fieldname)) {
					columns.push([df.fieldname, df.parent]);
				}
			});
		}
		
		this.columns = columns;
	},
	
	// preset columns and filters from saved info
	set_columns_and_filters: function(opts) {
		var me = this;
		if(opts.columns) this.columns = opts.columns;
		if(opts.filters) $.each(opts.filters, function(i, f) {
			// fieldname, condition, value
			if (wn.meta.get_docfield(f[0], f[1]).fieldtype == "Check")
				value = f[3] ? "Yes" : "No";
			else
				value = f[3];
			me.filter_list.add_filter(f[0], f[1], f[2], value);
		});

		// first sort
		if(opts.sort_by) this.sort_by_select.val(opts.sort_by);
		if(opts.sort_order) this.sort_order_select.val(opts.sort_order);
		
		// second sort
		if(opts.sort_by_next) this.sort_by_next_select.val(opts.sort_by_next);
		if(opts.sort_order_next) this.sort_order_next_select.val(opts.sort_order_next);
	},

	set_route_filters: function() {
		var me = this;
		if(wn.route_options) {
			$.each(wn.route_options, function(key, value) {
				me.filter_list.add_filter(me.doctype, key, "=", value);
			});
			wn.route_options = null;
		}
	},
	
	// build args for query
	get_args: function() {
		var me = this;
		return {
			doctype: this.doctype,
			fields: $.map(this.columns, function(v) { return me.get_full_column_name(v) }),
			order_by: this.get_order_by(),
			filters: this.filter_list.get_filters(),
			docstatus: ['0','1','2'],
			with_childnames: 1
		}
	},
	
	get_order_by: function() {
		// first 
		var order_by = this.get_selected_table_and_column(this.sort_by_select) 
			+ ' ' + this.sort_order_select.val();
			
		// second
		if(this.sort_by_next_select.val()) {
			order_by += ', ' + this.get_selected_table_and_column(this.sort_by_next_select) 
				+ ' ' + this.sort_order_next_select.val();
		}
		
		return order_by;
	},
	get_selected_table_and_column: function($select) {
		return this.get_full_column_name([$select.find('option:selected').attr('fieldname'), 
			$select.find('option:selected').attr('table')]) 
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
			if(!docfield) {
				var docfield = wn.model.get_std_field(c[0]);
				if(c[0]=="name") { 
					docfield.options = me.doctype;
				}
			}
			coldef = {
				id: c[0],
				field: c[0],
				docfield: docfield,
				name: wn._(docfield ? docfield.label : toTitle(c[0])),
				width: (docfield ? cint(docfield.width) : 120) || 120,
				formatter: function(row, cell, value, columnDef, dataContext) {
					var docfield = columnDef.docfield;
					if(docfield.fieldname==="_user_tags") docfield.fieldtype = "Tag";
					if(docfield.fieldname==="_comments") docfield.fieldtype = "Comment";
					return wn.format(value, docfield, null, dataContext);
				}
			}
			return coldef;
		});
	},
	
	// render data
	render_list: function() {
		var me = this;
		var columns = this.get_columns();

		// add sr in data
		$.each(this.data, function(i, v) {
			// add index
			v._idx = i+1;
			v.id = v._idx;
		});

		var options = {
			enableCellNavigation: true,
			enableColumnReorder: false,
		};

		if(this.slickgrid_options) {
			$.extend(options, this.slickgrid_options);
		}

		this.col_defs = columns;
		this.dataView = new Slick.Data.DataView();
		this.set_data(this.data);

		var grid_wrapper = this.$w.find('.result-list');

		// set height if not auto
		if(!options.autoHeight) 
			grid_wrapper.css('height', '500px');
		
		this.grid = new Slick.Grid(grid_wrapper
			.css('border', '1px solid #ccc')
			.css('border-top', '0px')
			.get(0), this.dataView, 
			columns, options);
		
		this.grid.setSelectionModel(new Slick.CellSelectionModel());
		this.grid.registerPlugin(new Slick.CellExternalCopyManager({
			dataItemColumnValueExtractor: function(item, columnDef, value) {
				return item[columnDef.field];
			}
		}));
		wn.slickgrid_tools.add_property_setter_on_resize(this.grid);
		if(this.start!=0 && !options.autoHeight) {
			this.grid.scrollRowIntoView(this.data.length-1);
		}
		
		this.grid.onDblClick.subscribe(function(e, args) {
			var row = me.dataView.getItem(args.row);
			var cell = me.grid.getColumns()[args.cell];
			me.edit_cell(row, cell.docfield);
		});
		
		this.dataView.onRowsChanged.subscribe(function (e, args) {
			me.grid.invalidateRows(args.rows);
			me.grid.render();
		});
	},
	
	edit_cell: function(row, docfield) {
		if(wn.model.std_fields_list.indexOf(docfield.fieldname)!==-1) {
			wn.throw(wn._("Cannot edit standard fields"));
		} else if(wn.boot.profile.can_write.indexOf(this.doctype)===-1) {
			wn.throw(wn._("No permission to edit"));
		}
		var me = this;
		var d = new wn.ui.Dialog({
			title: wn._("Edit") + " " + wn._(docfield.label),
			fields: [docfield, {"fieldtype": "Button", "label": "Update"}],
		});
		d.get_input(docfield.fieldname).val(row[docfield.fieldname]);
		d.get_input("update").on("click", function() {
			wn.call({
				method: "webnotes.client.set_value",
				args: {
					doctype: docfield.parent,
					name: row[docfield.parent===me.doctype ? "name" : docfield.parent+":name"],
					fieldname: docfield.fieldname,
					value: d.get_value(docfield.fieldname)
				},
				callback: function(r) {
					if(!r.exc) {
						d.hide();
						var doclist = r.message;
						$.each(me.dataView.getItems(), function(i, item) {
							if (item.name === doclist[0].name) {
								var new_item = $.extend({}, item, doclist[0]);
								$.each(doclist, function(i, doc) {
									if(item[doc.doctype + ":name"]===doc.name) {
										$.each(doc, function(k, v) {
											if(wn.model.std_fields_list.indexOf(k)===-1) {
												new_item[k] = v;
											}
										})
									}
								});
								me.dataView.updateItem(item.id, new_item);
							}
						});
					}
				}
			});
		});
		d.show();
	},
	
	set_data: function() {
		this.dataView.beginUpdate();
		this.dataView.setItems(this.data);
		this.dataView.endUpdate();
	},
	
	get_columns: function() {
		var std_columns = [{id:'_idx', field:'_idx', name: 'Sr.', width: 40, maxWidth: 40}];
		if(this.can_delete) {
			std_columns = std_columns.concat([{
				id:'_check', field:'_check', name: "", width: 30, maxWidth: 30, 
					formatter: function(row, cell, value, columnDef, dataContext) {
						return repl("<input type='checkbox' \
							data-row='%(row)s' %(checked)s>", {
								row: row,
								checked: (dataContext._checked ? "checked=\"checked\"" : "")
							});
					}
			}]);
		}
		return std_columns.concat(this.build_columns());		
	},
	
	// setup column picker
	make_column_picker: function() {
		var me = this;
		this.column_picker = new wn.ui.ColumnPicker(this);
		this.page.appframe.add_button(wn._('Pick Columns'), function() {
			me.column_picker.show(me.columns);
		}, 'icon-th-list');
	},

	set_tag_and_status_filter: function() {
		var me = this;
		this.$w.find('.result-list').on("click", ".label-info", function() {
			if($(this).attr("data-label")) {
				me.set_filter("_user_tags", $(this).attr("data-label"));
			}
		});
		this.$w.find('.result-list').on("click", "[data-workflow-state]", function() {
			if($(this).attr("data-workflow-state")) {
				me.set_filter(me.state_fieldname, 
					$(this).attr("data-workflow-state"));
			}
		});
	},
		
	// setup sorter
	make_sorter: function() {
		var me = this;
		this.sort_dialog = new wn.ui.Dialog({title:'Sorting Preferences'});
		$(this.sort_dialog.body).html('<p class="help">Sort By</p>\
			<div class="sort-column"></div>\
			<div><select class="sort-order form-control" style="margin-top: 10px; width: 60%;">\
				<option value="asc">'+wn._('Ascending')+'</option>\
				<option value="desc">'+wn._('Descending')+'</option>\
			</select></div>\
			<hr><p class="help">'+wn._('Then By (optional)')+'</p>\
			<div class="sort-column-1"></div>\
			<div><select class="sort-order-1 form-control" style="margin-top: 10px; width: 60%;">\
				<option value="asc">'+wn._('Ascending')+'</option>\
				<option value="desc">'+wn._('Descending')+'</option>\
			</select></div><hr>\
			<div><button class="btn btn-info">'+wn._('Update')+'</div>');
		
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
		this.sort_by_select.val(this.doctype + '.modified');
		this.sort_order_select.val('desc');
		
		this.sort_by_next_select.val('');
		this.sort_order_next_select.val('desc');
		
		// button actions
		this.page.appframe.add_button(wn._('Sort By'), function() {
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
		var export_btn = this.page.appframe.add_button(wn._('Export'), function() {
			var args = me.get_args();
			args.cmd = 'webnotes.widgets.reportview.export_query'
			open_url_post(wn.request.url, args);
		}, 'icon-download-alt');
		wn.utils.disable_export_btn(export_btn);
	},

	// save
	make_save: function() {
		var me = this;
		if(wn.user.is_report_manager()) {
			this.page.appframe.add_button(wn._('Save'), function() {
				// name
				if(me.docname) {
					var name = me.docname
				} else {
					var name = prompt(wn._('Select Report Name'));
					if(!name) {
						return;
					}
				}
				
				// callback
				return wn.call({
					method: 'webnotes.widgets.reportview.save_report',
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
						if(r.exc) {
							msgprint(wn._("Report was not saved (there were errors)"));
							return;
						}
						if(r.message != me.docname)
							wn.set_route('Report', me.doctype, r.message);
					}
				});
			}, 'icon-upload');
		}
	},

	make_delete: function() {
		var me = this;
		if(this.can_delete) {
			$(this.page).on("click", "input[type='checkbox'][data-row]", function() {
				me.data[$(this).attr("data-row")]._checked 
					= this.checked ? true : false;
			});
			
			this.page.appframe.add_button(wn._("Delete"), function() {
				var delete_list = []
				$.each(me.data, function(i, d) {
					if(d._checked) {
						if(d.name)
							delete_list.push(d.name);
					}
				});
				
				if(!delete_list.length) 
					return;
				if(wn.confirm(wn._("This is PERMANENT action and you cannot undo. Continue?"),
					function() {
						return wn.call({
							method: 'webnotes.widgets.reportview.delete_items',
							args: {
								items: delete_list,
								doctype: me.doctype
							},
							callback: function() {
								me.refresh();
							}
						});
					}));
				
			}, 'icon-remove');
		}
	},
});

wn.ui.ColumnPicker = Class.extend({
	init: function(list) {
		this.list = list;
		this.doctype = list.doctype;
		this.selects = {};
	},
	show: function(columns) {
		wn.require('assets/webnotes/js/lib/jquery/jquery.ui.interactions.min.js');
		var me = this;
		if(!this.dialog) {
			this.dialog = new wn.ui.Dialog({
				title: wn._("Pick Columns"),
				width: '400'
			});
		}
		$(this.dialog.body).html('<div class="help">'+wn._("Drag to sort columns")+'</div>\
			<div class="column-list"></div>\
			<div><button class="btn btn-default btn-add"><i class="icon-plus"></i>\
				'+wn._("Add Column")+'</button></div>\
			<hr>\
			<div><button class="btn btn-info">'+wn._("Update")+'</div>');
		
		// show existing	
		$.each(columns, function(i, c) {
			me.add_column(c);
		});
		
		$(this.dialog.body).find('.column-list').sortable();
		
		// add column
		$(this.dialog.body).find('.btn-add').click(function() {
			me.add_column(['name']);
		});
		
		// update
		$(this.dialog.body).find('.btn-info').click(function() {
			me.dialog.hide();
			// selected columns as list of [column_name, table_name]
			var columns = [];
			$(me.dialog.body).find('select').each(function() {
				var $selected = $(this).find('option:selected');
				columns.push([$selected.attr('fieldname'), 
					$selected.attr('table')]);
			});
			wn.defaults.set_default("_list_settings:" + me.doctype, columns);
			me.list.columns = columns;
			me.list.run();
		});
		
		this.dialog.show();
	},
	add_column: function(c) {
		var w = $('<div style="padding: 5px; background-color: #eee; \
			width: 90%; margin-bottom: 10px; border-radius: 3px; cursor: move;">\
			<img src="assets/webnotes/images/ui/drag-handle.png" style="margin-right: 10px;">\
			<a class="close" style="margin-top: 5px;">&times</a>\
			</div>')
			.appendTo($(this.dialog.body).find('.column-list'));
		
		var fieldselect = new wn.ui.FieldSelect(w, this.doctype);
		
		fieldselect.$select.css({"display": "inline"});
		
		fieldselect.$select
			.css({width: '70%', 'margin-top':'5px'})
			.val((c[1] || this.doctype) + "." + c[0]);
		w.find('.close').click(function() {
			$(this).parent().remove();
		});
	}
});