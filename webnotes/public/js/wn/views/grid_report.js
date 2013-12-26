// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide("wn.report_dump");

$.extend(wn.report_dump, {
	data: {},
	last_modified: {},
	with_data: function(doctypes, callback, progress_bar) {
		var pre_loaded = keys(wn.report_dump.last_modified);
		return wn.call({
			method: "webnotes.widgets.report_dump.get_data",
			type: "GET",
			args: {
				doctypes: doctypes,
				last_modified: wn.report_dump.last_modified
			},
			callback: function(r) {
				// creating map of data from a list
				$.each(r.message, function(doctype, doctype_data) {
					wn.report_dump.set_data(doctype, doctype_data);
				});
				
				// reverse map names
				$.each(r.message, function(doctype, doctype_data) {
					// only if not pre-loaded
					if(!in_list(pre_loaded, doctype)) {
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
					}
				});
				
				callback();
			},
			progress_bar: progress_bar
		})
	},
	set_data: function(doctype, doctype_data) {
		var data = [];
		var replace_dict = {};
		var make_row = function(d) {
			var row = {};
			$.each(doctype_data.columns, function(idx, col) {
				row[col] = d[idx];
			});
			row.id = row.name;
			row.doctype = doctype;
			return row;
		}
		if(wn.report_dump.last_modified[doctype]) {
			// partial loading, make a name dict
			$.each(doctype_data.data, function(i, d) {
				var row = make_row(d);
				replace_dict[row.name] = row;
			});
			
			// replace old data
			$.each(wn.report_dump.data[doctype], function(i, d) {
				if(replace_dict[d.name]) {
					data.push(replace_dict[d.name]);
					delete replace_dict[d.name];
				} else if(doctype_data.modified_names.indexOf(d.name)!==-1) {
					// if modified but not in replace_dict, then assume it as cancelled
					// don't push in data
				} else {
					data.push(d);
				}
			});
			
			// add new records
			$.each(replace_dict, function(name, d) {
				data.push(d);
			})
		} else {
			
			// first loading
			$.each(doctype_data.data, function(i, d) {
				data.push(make_row(d));
			});
		}
		wn.report_dump.last_modified[doctype] = doctype_data.last_modified;
		wn.report_dump.data[doctype] = data;
	}
});

wn.provide("wn.views");
wn.views.GridReport = Class.extend({
	init: function(opts) {
		wn.require("assets/js/slickgrid.min.js");
		
		this.filter_inputs = {};
		this.preset_checks = [];
		this.tree_grid = {show: false};
		var me = this;
		$.extend(this, opts);
		
		this.wrapper = $('<div>').appendTo(this.parent);
		
		if(this.filters) {
			this.make_filters();
		}
		this.make_waiting();
		
		this.get_data_and_refresh();
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
			me.get_data_and_refresh();
		});
		
	},
	get_data_and_refresh: function() {
		var me = this;
		this.get_data(function() {
			me.apply_filters_from_route();
			me.refresh();
		});
	},
	get_data: function(callback) {
		var me = this;
		var progress_bar = null;
		if(!this.setup_filters_done)
			progress_bar = this.wrapper.find(".progress .progress-bar");
			
		wn.report_dump.with_data(this.doctypes, function() {
			if(!me.setup_filters_done) {
				me.setup_filters();
				me.setup_filters_done = true;
			}
			callback();
		}, progress_bar);
	},
	setup_filters: function() {
		var me = this;
		$.each(me.filter_inputs, function(i, v) {
			var opts = v.get(0).opts;
			if(opts.fieldtype == "Select" && inList(me.doctypes, opts.link)) {
				$(v).add_options($.map(wn.report_dump.data[opts.link],
					function(d) { return d.name; }));
			} else if(opts.fieldtype == "Link" && inList(me.doctypes, opts.link)) {
				opts.list = $.map(wn.report_dump.data[opts.link],
					function(d) { return d.name; });
				me.set_autocomplete(v, opts.list);
			}
		});	

		// refresh
		this.filter_inputs.refresh && this.filter_inputs.refresh.click(function() { 
			me.get_data(function() {
				me.refresh();
			});
		});
		
		// reset filters
		this.filter_inputs.reset_filters && this.filter_inputs.reset_filters.click(function() { 
			me.init_filter_values(); 
			me.refresh();
		});
		
		// range
		this.filter_inputs.range && this.filter_inputs.range.on("change", function() {
			me.refresh();
		});
		
		// plot check
		if(this.setup_plot_check) 
			this.setup_plot_check();
	},
	set_filter: function(key, value) {
		var filters = this.filter_inputs[key];
		if(filters) {
			var opts = filters.get(0).opts;
			if(opts.fieldtype === "Check") {
				filters.prop("checked", cint(value) ? true : false);
			} if(opts.fieldtype=="Date") {
				filters.val(wn.datetime.str_to_user(value));
			} else {
				filters.val(value);
			}
		} else {
			msgprint("Invalid Filter: " + key)
		}
	},
	set_autocomplete: function($filter, list) {
		var me = this;
		$filter.autocomplete({
			source: list,
			select: function(event, ui) {
				$filter.val(ui.item.value);
				me.refresh();
			}
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
			} else if(opts.fieldtype=="Link") {
				filter.val("");
			}
		});
		
		this.set_default_values();
	},

	set_default_values: function() {
		var values = {
			from_date: dateutil.str_to_user(sys_defaults.year_start_date),
			to_date: dateutil.str_to_user(sys_defaults.year_end_date)
		}
		
		var me = this;
		$.each(values, function(i, v) {
			if(me.filter_inputs[i] && !me.filter_inputs[i].val())
				me.filter_inputs[i].val(v);
		})
	},

	make_filters: function() {
		var me = this;
		$.each(this.filters, function(i, v) {
			v.fieldname = v.fieldname || v.label.replace(/ /g, '_').toLowerCase();
			var input = null;
			if(v.fieldtype=='Select') {
				input = me.appframe.add_select(v.label, v.options || [v.default_value]);
			} else if(v.fieldtype=="Link") {
				input = me.appframe.add_data(v.label);
				input.autocomplete({
					source: v.list || [],
				});
			} else if(v.fieldtype=='Button') {
				input = me.appframe.add_primary_action(v.label, null, v.icon);
			} else if(v.fieldtype=='Date') {
				input = me.appframe.add_date(v.label);
			} else if(v.fieldtype=='Label') {
				input = me.appframe.add_label(v.label);
			} else if(v.fieldtype=='Data') {
				input = me.appframe.add_data(v.label);
			} else if(v.fieldtype=='Check') {
				input = me.appframe.add_check(v.label);
			}

			if(input) {
				input && (input.get(0).opts = v);
				if(v.cssClass) {
					input.addClass(v.cssClass);
				}
				input.keypress(function(e) {
					if(e.which==13) {
						me.refresh();
					}
				})
			}
			me.filter_inputs[v.fieldname] = input;
		});
	},
	make_waiting: function() {
		this.waiting = wn.messages.waiting(this.wrapper, wn._("Loading Report")+"...", '10');			
	},
	load_filter_values: function() {
		var me = this;
		$.each(this.filter_inputs, function(i, f) {
			var opts = f.get(0).opts;
			if(opts.fieldtype=='Check') {
				me[opts.fieldname] = f.prop('checked') ? 1 : 0;
			} else if(opts.fieldtype!='Button') {
				me[opts.fieldname] = f.val();
				if(opts.fieldtype=="Date") {
					me[opts.fieldname] = dateutil.user_to_str(me[opts.fieldname]);
				} else if (opts.fieldtype == "Select") {
					me[opts.fieldname+'_default'] = opts.default_value;
				}
			}
		});
		
		if(this.filter_inputs.from_date && this.filter_inputs.to_date && (this.to_date < this.from_date)) {
			msgprint(wn._("From Date must be before To Date"));
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
				item[col.id] = 0.0;
			}
		});
	},
	
	round_item_values: function(item) {
		var me = this;
		$.each(this.columns, function(i, col) {
			if (col.formatter==me.currency_formatter) {
				item[col.id] = flt(item[col.id], wn.defaults.get_default("float_precision") || 3);
			}
		});
	},
	
	round_off_data: function() {
		var me = this;
		$.each(this.data, function(i, d) {
			me.round_item_values(d);
		});
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
		this.round_off_data();
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
			<div class="processing" style="background-color: #fec; display: none; \
				float: left; margin: 2px">Updated! </div> \
			<a href="#" class="grid-report-export"> \
				<i class="icon icon-download-alt"></i> Export</a> \
		</div>').appendTo(this.wrapper);
		
		this.wrapper.find(".grid-report-export").click(function() { return me.export(); });
		
		// grid wrapper
		this.grid_wrapper = $("<div style='height: 500px; border: 1px solid #aaa; \
			background-color: #eee; margin-top: 15px;'>")
			.appendTo(this.wrapper);
		this.id = wn.dom.set_unique_id(this.grid_wrapper.get(0));

		// zero-value check
		$('<div style="margin: 10px 0px; display: none" class="show-zero">\
				<input type="checkbox"> '+wn._('Show rows with zero values')
			+'</div>').appendTo(this.wrapper);

		this.bind_show();
		
		wn.cur_grid_report = this;
		$(this.wrapper).trigger('make');
		
	},
	apply_filters_from_route: function() {
		var me = this;
		if(wn.route_options) {
			$.each(wn.route_options, function(key, value) {
				me.set_filter(key, value);
			});
			wn.route_options = null;
		} else {
			this.init_filter_values();
		}
		this.set_default_values();

		$(this.wrapper).trigger('apply_filters_from_route');
	},
	options: {
		editable: false,
		enableColumnReorder: false
	},
	render: function() {
		// new slick grid
		this.grid = new Slick.Grid("#"+this.id, this.dataView, this.dataview_columns, this.options);
		var me = this;

		this.grid.setSelectionModel(new Slick.CellSelectionModel());
		this.grid.registerPlugin(new Slick.CellExternalCopyManager({
			dataItemColumnValueExtractor: function(item, columnDef, value) {
				return item[columnDef.field];
			}
		}));

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
		wn.tools.downloadify(wn.slickgrid_tools.get_view_data(this.columns, this.dataView),
			["Report Manager", "System Manager"], this);
		return false;
	},
	apply_filters: function(item) {
		// generic filter: apply filter functiions
		// from all filter_inputs
		var filters = this.filter_inputs;
		if(item._show) return true;
		
		for (i in filters) {
			if(!this.apply_filter(item, i)) {
				return false;
			}
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
			value: ((value==null || value==="") ? "" : format_number(value))
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
		return repl('<input type="checkbox" data-id="%(id)s" \
			class="plot-check" %(checked)s>', {
				"id": dataContext.id,
				"checked": dataContext.checked ? 'checked="checked"' : ""
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
							onclick="wn.cur_grid_report.set_filter(\'%(col_name)s\', \'%(value)s\'); \
								wn.cur_grid_report.refresh(); return false;">\
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
			for(var i=0; i <= date_diff; i++) {
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
	trigger_refresh_on_change: function(filters) {
		var me = this;
		$.each(filters, function(i, f) {
			me.filter_inputs[f] && me.filter_inputs[f].on("change", function() {
				me.refresh();
			});
		});
	}
});

wn.views.GridReportWithPlot = wn.views.GridReport.extend({
	render_plot: function() {
		var plot_data = this.get_plot_data ? this.get_plot_data() : null;
		if(!plot_data) {
			this.plot_area.toggle(false);
			return;
		}
		wn.require('assets/webnotes/js/lib/flot/jquery.flot.js');
		wn.require('assets/webnotes/js/lib/flot/jquery.flot.downsample.js');
		
		this.plot = $.plot(this.plot_area.toggle(true), plot_data,
			this.get_plot_options());
		
		this.setup_plot_hover();
	},
	setup_plot_check: function() {
		var me = this;
		me.wrapper.bind('make', function() {
			me.wrapper.on("click", ".plot-check", function() {
				var checked = $(this).prop("checked");
				var id = $(this).attr("data-id");
				if(me.item_by_name) {
					if(me.item_by_name[id]) {
						me.item_by_name[id].checked = checked ? true : false;
					}
				} else {
					$.each(me.data, function(i, d) {
						if(d.id==id) d.checked = checked;
					});
				}
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
	 	var value = format_number(y);
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
				max: dateutil.str_to_obj(this.to_date).getTime() },
			series: { downsample: { threshold: 1000 } }
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
		if (!this.tl) this.tl = {};
		if (!this.tl[parent_doctype]) this.tl[parent_doctype] = [];
		
		$.each(wn.report_dump.data[parent_doctype], function(i, parent) {
			if(tmap[parent.name]) {
				$.each(tmap[parent.name], function(i, d) {
					me.tl[parent_doctype].push($.extend(copy_dict(parent), d));
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
	
	export: function() {
		var msgbox = msgprint('<p>Select To Download:</p>\
			<p><input type="checkbox" name="with_groups" checked="checked"> With Groups</p>\
			<p><input type="checkbox" name="with_ledgers" checked="checked"> With Ledgers</p>\
			<p><button class="btn btn-info">Download</button>');

		var me = this;

		$(msgbox.body).find("button").click(function() {
			var with_groups = $(msgbox.body).find("[name='with_groups']").prop("checked");
			var with_ledgers = $(msgbox.body).find("[name='with_ledgers']").prop("checked");

			var data = wn.slickgrid_tools.get_view_data(me.columns, me.dataView, 
				function(row, item) {
					if(with_groups) {
						// add row
						for(var i=0; i<item.indent; i++) row[0] = "   " + row[0];
					}
					if(with_groups && (item.group_or_ledger == "Group" || item.is_group)) {
						return true;
					}
					if(with_ledgers && (item.group_or_ledger != "Group" && !item.is_group)) {
						return true;
					}
				
					return false;
			});
			
			wn.tools.downloadify(data, ["Report Manager", "System Manager"], me);
			return false;
		})

		return false;
	},
	
});