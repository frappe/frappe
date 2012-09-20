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
				args: {doctypes: missing},
				callback: function(r) {
					// creating map of data from a list
					$.each(r.message, function(doctype, doctype_data) {
						var data = [];
						$.each(doctype_data.data, function(i, d) {
							var row = {};
							$.each(doctype_data.columns, function(idx, col) {
								row[col] = d[idx];
							});
							row.id = row.name || doctype + "-" + i
							data.push(row);
						});
						wn.report_dump.data[doctype] = data;
					});
					
					// reverse map names
					$.each(r.message, function(doctype, doctype_data) {
						if(doctype_data.links) {
							$.each(wn.report_dump.data[doctype], function(row_idx, row) {
								$.each(doctype_data.links, function(link_key, link) {
									row[link_key] = wn.report_dump.data[link[0]][row[link_key]][link[1]];
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

			
	},
	make_waiting: function() {
		this.waiting = $('<div class="well" style="width: 63%; margin: 30px auto;">\
			<p style="text-align: center;">Loading Report...</p>\
			<div class="progress progress-striped active">\
				<div class="bar" style="width: 10%"></div></div>')
			.appendTo(this.wrapper);
			
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
	},
	make_name_map: function(data, key) {
		var map = {};
		key = key || "name";
		$.each(data, function(i, v) {
			map[v[key]] = v;
		})
		return map;
	},
 	import_slickgrid: function() {
		wn.require('js/lib/slickgrid/slick.grid.css');
		wn.require('js/lib/slickgrid/slick-default-theme.css');
		wn.require('js/lib/slickgrid/jquery.event.drag.min.js');
		wn.require('js/lib/slickgrid/slick.core.js');
		wn.require('js/lib/slickgrid/slick.grid.js');
		wn.require('js/lib/slickgrid/slick.dataview.js');
		wn.dom.set_style('.slick-cell { font-size: 12px; }');		
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
		// plot might need prepared data
		this.render();
		this.render_plot();
	},
	setup_dataview_columns: function() {
		this.dataview_columns = $.map(this.columns, function(col) {
			return !col.hidden ? col : null;
		});	
	},
	make: function() {
		
		// plot wrapper
		$('<div class="plot" style="margin-bottom: 15px; display: none; \
			height: 300px; width: 100%;"></div>').appendTo(this.wrapper);
		
		// print / export
		$('<div style="text-align: right;"> \
			<a href="#" class="grid-report-print"><i class="icon icon-print"></i> Print</a> \
			<span style="color: #aaa; margin: 0px 10px;"> | </span> \
			<a href="#" class="grid-report-export"><i class="icon icon-download-alt"></i> Export</a> \
		</div>').appendTo(this.wrapper);
		
		this.wrapper.find(".grid-report-export").click(function() { return me.export(); });
		
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
		
		this.add_grid_events && this.add_grid_events();
	},
	prepare_data_view: function(items) {
		// initialize the model
		this.dataView = new Slick.Data.DataView({ inlineFilters: true });
		this.dataView.beginUpdate();
		this.dataView.setItems(items);
		if(this.dataview_filter) this.dataView.setFilter(this.dataview_filter);
		this.dataView.endUpdate();
	},
	export: function() {
		var me = this;
		var res = [$.map(this.columns, function(v) { return v.name; })].concat(this.get_view_data());
		
		wn.require("js/lib/downloadify/downloadify.min.js");
		wn.require("js/lib/downloadify/swfobject.js");
		
		var id = wn.dom.set_unique_id();
		var msgobj = msgprint('<p id="'+ id +'">You must have Flash 10 installed to download this file.</p>');
		
		Downloadify.create(id ,{
			filename: function(){
				return me.title + '.csv';
			},
			data: function(){ 
				return wn.to_csv(res);
			},
			swf: 'js/lib/downloadify/downloadify.swf',
			downloadImage: 'js/lib/downloadify/download.png',
			onComplete: function(){ msgobj.hide(); },
			onCancel: function(){ msgobj.hide(); },
			onError: function(){ msgobj.hide(); },
			width: 100,
			height: 30,
			transparent: true,
			append: false			
		});
		
		return false;
	},
	render_plot: function() {
		var plot_data = this.get_plot_data ? this.get_plot_data() : null;
		if(!plot_data) {
			this.wrapper.find('.plot').toggle(false);
			return;
		}
		wn.require('js/lib/flot/jquery.flot.js');
		
		this.plot = $.plot(this.wrapper.find('.plot').toggle(true), plot_data,
			this.get_plot_options());
		
		this.setup_plot_hover();
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
	get_view_data: function() {
		var res = [];
		var col_map = $.map(this.columns, function(v) { return v.field; });

		for (var i=0, len=this.dataView.getLength(); i<len; i++) {
			var d = this.dataView.getItem(i);
			var row = [];
			$.each(col_map, function(i, col) {
				var val = d[col];
				if(val===null || val===undefined) {
					val = ""
				}
				row.push(val);
			})
			
			res.push(row);
		}
		return res;
	},
	options: {
		editable: false,
		enableColumnReorder: false
	},
	apply_filters: function(item) {
		// generic filter: apply filter functiions
		// from all filter_inputs
		var filters = this.filter_inputs;
		if(item._show) return true;
		
		for (i in filters) {
			if(!this.apply_filter(item, i)) return false;
		}
		
		// hand over to additional filters (if applicable)
		if(this.custom_dataview_filter) {
			return this.custom_dataview_filter(item);
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
				if(col.formatter==me.currency_formatter) {
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
										
					if(dataContext._show) {
						return repl('<span style="%(_style)s">%(value)s</span>', {
							_style: dataContext._style || "",
							value: value
						});
					}
					
					// make link to add a filter
					var link_formatter = wn.cur_grid_report.dataview_columns[cell].link_formatter;	
					var html = repl('<a href="#" \
						onclick="wn.cur_grid_report.filter_inputs.%(col_name)s.val(\'%(value)s\'); \
							wn.cur_grid_report.set_route(); return false;">\
						%(value)s</a>', {
							value: value,
							col_name: link_formatter.filter_input,
							page_name: wn.container.page.page_name
						})

					// make icon to open form
					if(link_formatter.open_btn) {
						html += repl(' <i class="icon icon-share" style="cursor: pointer;"\
							onclick="wn.set_route(\'Form\', \'%(doctype)s\', \'%(value)s\');">\
						</i>', {
							value: value,
							doctype: eval(link_formatter.doctype)
						});
					}
					return html;
				}
			}
		})
	}
})