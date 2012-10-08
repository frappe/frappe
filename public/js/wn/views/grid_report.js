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

wn.provide("wn.report_dump");

$.extend(wn.report_dump, {
	data: {},
	with_data: function(doctypes, callback, progress_bar) {
		var missing = [];
		$.each(doctypes, function(i, v) {
			if(!wn.report_dump.data[v]) missing.push(v);
		})
		if(missing.length) {
			wn.call({
				method: "webnotes.widgets.report_dump.get_data",
				args: {
					doctypes: doctypes,
					missing: missing
				},
				callback: function(r) {
					// creating map of data from a list
					$.each(r.message, function(doctype, doctype_data) {
						var data = [];
						$.each(doctype_data.data, function(i, d) {
							var row = {};
							$.each(doctype_data.columns, function(idx, col) {
								row[col] = d[idx];
							});
							row.id = row.name || doctype + "-" + i;
							row.doctype = doctype;
							data.push(row);
						});
						wn.report_dump.data[doctype] = data;
					});
					
					// reverse map names
					$.each(r.message, function(doctype, doctype_data) {
						if(doctype_data.links) {
							$.each(wn.report_dump.data[doctype], function(row_idx, row) {
								$.each(doctype_data.links, function(link_key, link) {
									if(wn.report_dump.data[link[0]][row[link_key]]) {
										row[link_key] = wn.report_dump.data[link[0]][row[link_key]][link[1]];
									} else {
										row[link_key] = null;
									}
								})
							})
						}
					});
					
					callback();
				},
				progress_bar: progress_bar
			})
		} else {
			callback();
		}
	}
});

wn.provide("wn.views");
wn.views.GridReport = Class.extend({
	init: function(opts) {
		this.filter_inputs = {};
		this.preset_checks = [];
		this.tree_grid = {show: false};
		$.extend(this, opts);
		
		this.wrapper = $('<div>').appendTo(this.parent);
		
		if(this.filters) {
			this.make_filters();
		}
		this.make_waiting();
		this.import_slickgrid();
		
		var me = this;
		this.get_data();
	},
	bind_show: function() {
		// bind show event to reset cur_report_grid
		// and refresh filters from url
		// this must be called after init
		// because "wn.container.page" will only be set
		// once "load" event is over.
		
		var me = this;
		$(this.page).bind('show', function() {
			// reapply filters on show
			wn.cur_grid_report = me;
			me.apply_filters_from_route();
			me.refresh();
		});
		
	},
	get_data: function() {
		var me = this;
		wn.report_dump.with_data(this.doctypes, function() {
			// setup filters
			me.setup_filters();
			me.init_filter_values();
			me.refresh();
		}, this.wrapper.find(".progress .bar"));
	},
	setup_filters: function() {
		var me = this;
		$.each(me.filter_inputs, function(i, v) {
			var opts = v.get(0).opts;
			if (opts.fieldtype == "Select" && inList(me.doctypes, opts.link)) {
				$(v).add_options($.map(wn.report_dump.data[opts.link], function(d) {
					return d.name;
				}));
			}
		});	

		// refresh
		this.filter_inputs.refresh && this.filter_inputs.refresh.click(function() { 
			me.set_route(); 
		});
		
		// reset filters
		this.filter_inputs.reset_filters && this.filter_inputs.reset_filters.click(function() { 
			me.init_filter_values(); 
			me.set_route(); 
		});
		
		this.filter_inputs.range && this.filter_inputs.range.change(function() {
			me.set_route();
		});
	},
	init_filter_values: function() {
		var me = this;
		$.each(this.filter_inputs, function(key, filter) {
			var opts = filter.get(0).opts;
			if(sys_defaults[key]) {
				filter.val(sys_defaults[key]);
			} else if(opts.fieldtype=='Select') {
				filter.get(0).selectedIndex = 0;
			} else if(opts.fieldtype=='Data') {
				filter.val("");
			}
		})
		if(this.filter_inputs.from_date)
			this.filter_inputs.from_date.val(dateutil.str_to_user(sys_defaults.year_start_date));
		if(this.filter_inputs.to_date)
			this.filter_inputs.to_date.val(dateutil.str_to_user(sys_defaults.year_end_date));
	},

	make_filters: function() {
		var me = this;
		$.each(this.filters, function(i, v) {
			v.fieldname = v.fieldname || v.label.replace(/ /g, '_').toLowerCase();
			var input = null;
			if(v.fieldtype=='Select') {
				input = me.appframe.add_select(v.label, v.options || [v.default_value]);
			} else if(v.fieldtype=='Button') {
				input = me.appframe.add_button(v.label);
				if(v.icon) {
					$('<i class="icon '+ v.icon +'"></i>').prependTo(input);
				}
			} else if(v.fieldtype=='Date') {
				input = me.appframe.add_date(v.label);
			} else if(v.fieldtype=='Label') {
				input = me.appframe.add_label(v.label);
			} else if(v.fieldtype=='Data') {
				input = me.appframe.add_data(v.label);
			}

			if(input) {
				input && (input.get(0).opts = v);
				if(v.cssClass) {
					input.addClass(v.cssClass);
				}
				input.keypress(function(e) {
					if(e.which==13) {
						me.set_route();
					}
				})
			}
			me.filter_inputs[v.fieldname] = input;
		});
	},
	make_waiting: function() {
		this.waiting = wn.messages.waiting(this.wrapper, "Loading Report...", '10');			
	},
	load_filter_values: function() {
		var me = this;
		$.each(this.filter_inputs, function(i, f) {
			var opts = f.get(0).opts;
			if(opts.fieldtype!='Button') {
				me[opts.fieldname] = f.val();
				if(opts.fieldtype=="Date") {
					me[opts.fieldname] = dateutil.user_to_str(me[opts.fieldname]);
				} else if (opts.fieldtype == "Select") {
					me[opts.fieldname+'_default'] = opts.default_value;
				}
			}
		});
		
		if(this.filter_inputs.from_date && this.filter_inputs.to_date && (this.to_date < this.from_date)) {
			msgprint("From Date must be before To Date");
			return;
		}
		
	},
	make_name_map: function(data, key) {
		var map = {};
		key = key || "name";
		$.each(data, function(i, v) {
			map[v[key]] = v;
		})
		return map;
	},
	
	reset_item_values: function(item) {
		var me = this;
		$.each(this.columns, function(i, col) {
			if (col.formatter==me.currency_formatter) {
				item[col.id] = 0;
			}
		});		
	},
	
 	import_slickgrid: function() {
		wn.require('lib/js/lib/slickgrid/slick.grid.css');
		wn.require('lib/js/lib/slickgrid/slick-default-theme.css');
		wn.require('lib/js/lib/slickgrid/jquery.event.drag.min.js');
		wn.require('lib/js/lib/slickgrid/slick.core.js');
		wn.require('lib/js/lib/slickgrid/slick.grid.js');
		wn.require('lib/js/lib/slickgrid/slick.dataview.js');
		wn.dom.set_style('.slick-cell { font-size: 12px; }');
		if(this.tree_grid.show) wn.require("app/js/tree_grid.css");	
	},
	refresh: function() {
		this.waiting.toggle(false);
		if(!this.grid_wrapper) 
			this.make();
		this.show_zero = $('.show-zero input:checked').length;
		this.load_filter_values();
		this.setup_columns();
		this.setup_dataview_columns();
		this.apply_link_formatters();
		this.prepare_data();
		this.prepare_data_view();
		// plot might need prepared data
		this.wrapper.find(".processing").toggle(true);
		this.wrapper.find(".processing").delay(2000).fadeOut(300);
		this.render();
		this.render_plot && this.render_plot();
	},
	setup_dataview_columns: function() {
		this.dataview_columns = $.map(this.columns, function(col) {
			return !col.hidden ? col : null;
		});	
	},
	make: function() {
		var me = this;
		
		// plot wrapper
		this.plot_area = $('<div class="plot" style="margin-bottom: 15px; display: none; \
			height: 300px; width: 100%;"></div>').appendTo(this.wrapper);
		
		// print / export
		$('<div style="text-align: right;"> \
			<div class="processing" style="background-color: #fec; display: none; float: left; margin: 2px"> \
				Updated! </div>\
			<a href="#" class="grid-report-print"><i class="icon icon-print"></i> Print</a> \
			<span style="color: #aaa; margin: 0px 10px;"> | </span> \
			<a href="#" class="grid-report-export"><i class="icon icon-download-alt"></i> Export</a> \
		</div>').appendTo(this.wrapper);
		
		this.wrapper.find(".grid-report-export").click(function() { return me.export(); });
		this.wrapper.find(".grid-report-print").click(function() { msgprint("Coming Soon"); return false; });
		
		// grid wrapper
		this.grid_wrapper = $("<div style='height: 500px; border: 1px solid #aaa; \
			background-color: #eee; margin-top: 15px;'>")
			.appendTo(this.wrapper);
		this.id = wn.dom.set_unique_id(this.grid_wrapper.get(0));

		// zero-value check
		$('<div style="margin: 10px 0px; text-align: right; display: none" class="show-zero">\
				<input type="checkbox"> Show rows with zero values\
			</div>').appendTo(this.wrapper);

		this.bind_show();
		
		wn.cur_grid_report = this;
		this.apply_filters_from_route();
		$(this.wrapper).trigger('make');
		
	},
	apply_filters_from_route: function() {
		var hash = decodeURIComponent(window.location.hash);
		var me = this;
		if(hash.indexOf('/') != -1) {
			$.each(hash.split('/').splice(1).join('/').split('&'), function(i, f) {
				var f = f.split("=");
				if(me.filter_inputs[f[0]]) {
					me.filter_inputs[f[0]].val(decodeURIComponent(f[1]));
				} else {
					console.log("Invalid filter: " +f[0]);
				}
			});
		} else {
			this.init_filter_values();
		}
	},
	set_route: function() {
		wn.set_route(wn.container.page.page_name, $.map(this.filter_inputs, function(v) {
			var val = v.val();
			var opts = v.get(0).opts;
			if(val && val != opts.default_value)
				return encodeURIComponent(opts.fieldname) 
					+ '=' + encodeURIComponent(val);
		}).join('&'))
	},
	options: {
		editable: false,
		enableColumnReorder: false
	},
	render: function() {
		// new slick grid
		this.grid = new Slick.Grid("#"+this.id, this.dataView, this.dataview_columns, this.options);
		var me = this;

		// bind events
		this.dataView.onRowsChanged.subscribe(function (e, args) {
			me.grid.invalidateRows(args.rows);
			me.grid.render();
		});
		
		this.dataView.onRowCountChanged.subscribe(function (e, args) {
			me.grid.updateRowCount();
			me.grid.render();
		});
		
		this.tree_grid.show && this.add_tree_grid_events();
	},
	prepare_data_view: function() {
		// initialize the model
		this.dataView = new Slick.Data.DataView({ inlineFilters: true });
		this.dataView.beginUpdate();
		this.dataView.setItems(this.data);
		if(this.dataview_filter) this.dataView.setFilter(this.dataview_filter);
		if(this.tree_grid.show) this.dataView.setFilter(this.tree_dataview_filter);
		this.dataView.endUpdate();
	},
	export: function() {
		wn.downloadify(wn.slickgrid_tools.get_view_data(this.columns, this.dataView),
			["Report Manager", "System Manager"]);
		return false;
	},
	apply_filters: function(item) {
		// generic filter: apply filter functiions
		// from all filter_inputs
		var filters = this.filter_inputs;
		if(item._show) return true;
		
		for (i in filters) {
			if(!this.apply_filter(item, i)) return false;
		}
		
		return true;
	},
	apply_filter: function(item, fieldname) {
		var filter = this.filter_inputs[fieldname].get(0);
		if(filter.opts.filter) {
			if(!filter.opts.filter(this[filter.opts.fieldname], item, filter.opts, this)) {
				return false;
			}
		}
		return true;
	},
	apply_zero_filter: function(val, item, opts, me) {
		// show only non-zero values
		if(!me.show_zero) {
			for(var i=0, j=me.columns.length; i<j; i++) {
				var col = me.columns[i];
				if(col.formatter==me.currency_formatter && !col.hidden) {
					if(flt(item[col.field]) > 0.001 ||  flt(item[col.field]) < -0.001) {
						return true;
					} 
				}
			}
			return false;
		} 
		return true;
	},
	show_zero_check: function() {
		var me = this;
		this.wrapper.bind('make', function() {
			me.wrapper.find('.show-zero').toggle(true).find('input').click(function(){
				me.refresh();
			});	
		});
	},
	is_default: function(fieldname) {
		return this[fieldname]==this[fieldname + "_default"];
	},
	date_formatter: function(row, cell, value, columnDef, dataContext) {
		return dateutil.str_to_user(value);
	},
	currency_formatter: function(row, cell, value, columnDef, dataContext) {
		return repl('<div style="text-align: right; %(_style)s">%(value)s</div>', {
			_style: dataContext._style || "",
			value: fmt_money(value)
		});
	},
	text_formatter: function(row, cell, value, columnDef, dataContext) {
		return repl('<span style="%(_style)s" title="%(esc_value)s">%(value)s</span>', {
			_style: dataContext._style || "",
			esc_value: cstr(value).replace(/"/g, '\"'),
			value: cstr(value)
		});
	},
	check_formatter: function(row, cell, value, columnDef, dataContext) {					
		return repl("<input type='checkbox' data-id='%(id)s' \
			class='plot-check' %(checked)s>", {
				"id": dataContext.id,
				"checked": dataContext.checked ? "checked" : ""
			})
	},
	apply_link_formatters: function() {
		var me = this;
		$.each(this.dataview_columns, function(i, col) {
			if(col.link_formatter) {
				col.formatter = function(row, cell, value, columnDef, dataContext) {
					// added link and open button to links
					// link_formatter must have
					// filter_input, open_btn (true / false), doctype (will be eval'd)
					if(!value) return "";
					
					var me = wn.cur_grid_report;
										
					if(dataContext._show) {
						return repl('<span style="%(_style)s">%(value)s</span>', {
							_style: dataContext._style || "",
							value: value
						});
					}
					
					// make link to add a filter
					var link_formatter = me.dataview_columns[cell].link_formatter;
					if (link_formatter.filter_input) {
						var html = repl('<a href="#" \
							onclick="wn.cur_grid_report.filter_inputs \
								.%(col_name)s.val(\'%(value)s\'); \
								wn.cur_grid_report.set_route(); return false;">\
							%(value)s</a>', {
								value: value,
								col_name: link_formatter.filter_input,
								page_name: wn.container.page.page_name
							});
					} else {
						var html = value;
					}

					// make icon to open form
					if(link_formatter.open_btn) {
						var doctype = link_formatter.doctype 
							? eval(link_formatter.doctype) 
							: dataContext.doctype;
						html += me.get_link_open_icon(doctype, value);
					}
					return html;
				}
			}
		})
	},
	get_link_open_icon: function(doctype, name) {
		return repl(' <a href="#Form/%(doctype)s/%(name)s">\
			<i class="icon icon-share" style="cursor: pointer;"></i></a>', {
			doctype: doctype,
			name: encodeURIComponent(name)			
		});
	},
	make_date_range_columns: function() {
		this.columns = [];
		
		var me = this;
		var range = this.filter_inputs.range.val();
		this.from_date = dateutil.user_to_str(this.filter_inputs.from_date.val());
		this.to_date = dateutil.user_to_str(this.filter_inputs.to_date.val());
		var date_diff = dateutil.get_diff(this.to_date, this.from_date);
			
		me.column_map = {};
		
		var add_column = function(date) {
			me.columns.push({
				id: date,
				name: dateutil.str_to_user(date),
				field: date,
				formatter: me.currency_formatter,
				width: 100
			});
		}
		
		var build_columns = function(condition) {
			// add column for each date range
			for(var i=0; i < date_diff; i++) {
				var date = dateutil.add_days(me.from_date, i);
				if(!condition) condition = function() { return true; }
				
				if(condition(date)) add_column(date);
				me.last_date = date;
				
				if(me.columns.length) {
					me.column_map[date] = me.columns[me.columns.length-1];
				}
			}
		}
		
		// make columns for all date ranges
		if(range=='Daily') {
			build_columns();
		} else if(range=='Weekly') {
			build_columns(function(date) {
				if(!me.last_date) return true;
				return !(dateutil.get_diff(date, me.from_date) % 7)
			});		
		} else if(range=='Monthly') {
			build_columns(function(date) {
				if(!me.last_date) return true;
				return dateutil.str_to_obj(me.last_date).getMonth() != dateutil.str_to_obj(date).getMonth()
			});
		} else if(range=='Quarterly') {
			build_columns(function(date) {
				if(!me.last_date) return true;
				return dateutil.str_to_obj(date).getDate()==1 && in_list([0,3,6,9], dateutil.str_to_obj(date).getMonth())
			});			
		} else if(range=='Yearly') {
			build_columns(function(date) {
				if(!me.last_date) return true;
				return $.map(wn.report_dump.data['Fiscal Year'], function(v) { 
						return date==v.year_start_date ? true : null;
					}).length;
			});
		}
		
		// set label as last date of period
		$.each(this.columns, function(i, col) {
			col.name = me.columns[i+1]
				? dateutil.str_to_user(dateutil.add_days(me.columns[i+1].id, -1))
				: dateutil.str_to_user(me.to_date);				
		});		
	},
});

wn.views.GridReportWithPlot = wn.views.GridReport.extend({
	render_plot: function() {
		var plot_data = this.get_plot_data ? this.get_plot_data() : null;
		if(!plot_data) {
			this.plot_area.toggle(false);
			return;
		}
		wn.require('lib/js/lib/flot/jquery.flot.js');
		
		this.plot = $.plot(this.plot_area.toggle(true), plot_data,
			this.get_plot_options());
		
		this.setup_plot_hover();
	},
	setup_plot_check: function() {
		var me = this;
		me.wrapper.bind('make', function() {
			me.wrapper.on("click", ".plot-check", function() {
				var checked = $(this).attr("checked");
				me.item_by_name[$(this).attr("data-id")].checked = checked ? true : false;
				me.render_plot();			
			});	
		});
	},
	setup_plot_hover: function() {
		var me = this;
		this.tooltip_id = wn.dom.set_unique_id();
		function showTooltip(x, y, contents) {
			$('<div id="' + me.tooltip_id + '">' + contents + '</div>').css( {
				position: 'absolute',
				display: 'none',
				top: y + 5,
				left: x + 5,
				border: '1px solid #fdd',
				padding: '2px',
				'background-color': '#fee',
				opacity: 0.80
			}).appendTo("body").fadeIn(200);
		}

		this.previousPoint = null;
		this.wrapper.find('.plot').bind("plothover", function (event, pos, item) {
			if (item) {
				if (me.previousPoint != item.dataIndex) {
					me.previousPoint = item.dataIndex;

					$("#" + me.tooltip_id).remove();
					showTooltip(item.pageX, item.pageY, 
						me.get_tooltip_text(item.series.label, item.datapoint[0], item.datapoint[1]));
				}
			}
			else {
				$("#" + me.tooltip_id).remove();
				me.previousPoint = null;            
			}
	    });
		
	},
	get_tooltip_text: function(label, x, y) {
		var date = dateutil.obj_to_user(new Date(x));
	 	var value = fmt_money(y);
		return value + " on " + date;
	},
	get_plot_data: function() {
		var data = [];
		var me = this;
		$.each(this.data, function(i, item) {
			if (item.checked) {
				data.push({
					label: item.name,
					data: $.map(me.columns, function(col, idx) {
						if(col.formatter==me.currency_formatter && !col.hidden && col.plot!==false) {
							return me.get_plot_points(item, col, idx)
						}
					}),
					points: {show: true},
					lines: {show: true, fill: true},
				});
				
				// prepend opening 
				data[data.length-1].data = [[dateutil.str_to_obj(me.from_date).getTime(), 
					item.opening]].concat(data[data.length-1].data);
			}
		});
	
		return data.length ? data : false;
	},
	get_plot_options: function() {
		return {
			grid: { hoverable: true, clickable: true },
			xaxis: { mode: "time", 
				min: dateutil.str_to_obj(this.from_date).getTime(),
				max: dateutil.str_to_obj(this.to_date).getTime() }
		}
	}
});


wn.views.TreeGridReport = wn.views.GridReportWithPlot.extend({
	make_transaction_list: function(parent_doctype, doctype) {
		var me = this;
		var tmap = {};
		$.each(wn.report_dump.data[doctype], function(i, v) {
			if(!tmap[v.parent]) tmap[v.parent] = [];
			tmap[v.parent].push(v);
		});
		this.tl = [];
		$.each(wn.report_dump.data[parent_doctype], function(i, parent) {
			if(tmap[parent.name]) {
				$.each(tmap[parent.name], function(i, d) {
					me.tl.push($.extend(copy_dict(parent), d));
				});
			}
		});
	},
	add_tree_grid_events: function() {
		var me = this;
		this.grid.onClick.subscribe(function (e, args) {
			if ($(e.target).hasClass("toggle")) {
				var item = me.dataView.getItem(args.row);
				if (item) {
					if (!item._collapsed) {
						item._collapsed = true;
					} else {
						item._collapsed = false;
					}

					me.dataView.updateItem(item.id, item);
				}
				e.stopImmediatePropagation();
			}
		});
	},
	tree_formatter: function (row, cell, value, columnDef, dataContext) {
		var me = wn.cur_grid_report;
		value = value.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
		var data = me.data;
		var spacer = "<span style='display:inline-block;height:1px;width:" + 
			(15 * dataContext["indent"]) + "px'></span>";
		var idx = me.dataView.getIdxById(dataContext.id);
		var link = me.tree_grid.formatter(dataContext);
		
		if(dataContext.doctype) {
			link += me.get_link_open_icon(dataContext.doctype, dataContext.name);	
		}
			
		if (data[idx + 1] && data[idx + 1].indent > data[idx].indent) {
			if (dataContext._collapsed) {
				return spacer + " <span class='toggle expand'></span>&nbsp;" + link;
			} else {
				return spacer + " <span class='toggle collapse'></span>&nbsp;" + link;
			}
		} else {
			return spacer + " <span class='toggle'></span>&nbsp;" + link;
		}
	},
	tree_dataview_filter: function(item) {
		var me = wn.cur_grid_report;
		if(!me.apply_filters(item)) return false;
		
		var parent = item[me.tree_grid.parent_field];
		while (parent) {
			if (me.item_by_name[parent]._collapsed) {
				return false;
			}
			parent = me.parent_map[parent];
		}
		return true;
	},
	prepare_tree: function(item_dt, group_dt) {
		var group_data = wn.report_dump.data[group_dt];
		var item_data = wn.report_dump.data[item_dt];
		
		// prepare map with child in respective group
		var me = this;
		var item_group_map = {};
		var group_ids = $.map(group_data, function(v) { return v.id; });
		$.each(item_data, function(i, item) {
			var parent = item[me.tree_grid.parent_field];
			if(!item_group_map[parent]) item_group_map[parent] = [];
			if(group_ids.indexOf(item.name)==-1) {
				item_group_map[parent].push(item);				
			} else {
				msgprint("Ignoring Item "+ item.name.bold() + 
					", because a group exists with the same name!");
			}
		});
		
		// arrange items besides their parent item groups
		var items = [];
		$.each(group_data, function(i, group){
			group.is_group = true;
			items.push(group);
			items = items.concat(item_group_map[group.name] || []);
		});
		return items;
	},
	set_indent: function() {
		var me = this;
		$.each(this.data, function(i, d) {
			var indent = 0;
			var parent = me.parent_map[d.name];
			if(parent) {
				while(parent) {
					indent++;
					parent = me.parent_map[parent];
				}
			}
			d.indent = indent;
		});
	},
});