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
							row.id = doctype + "-" + i;
							data.push(row);
						});
						wn.report_dump.data[doctype] = data;
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
		$.extend(this, opts);
		
		this.wrapper = $('<div>').appendTo(this.parent);
		
		if(this.filters) {
			this.make_filters();
		}
		this.make_waiting();
		this.import_slickgrid();
		
		var me = this;
		this.get_data();
		wn.cur_grid_report = this;
	},
	get_data: function() {
		var me = this;
		wn.report_dump.with_data(this.doctypes, function() {
			// setup filters
			$.each(me.filter_inputs, function(i, v) {
				var opts = v.get(0).opts;
				if (opts.fieldtype == "Select" && inList(me.doctypes, opts.options)) {
					$(v).add_options($.map(wn.report_dump.data[opts.options], function(d) {
						return d.name;
					}));
				}
			});
			
			me.setup();
			me.refresh();
		}, this.wrapper.find(".progress .bar"));
	},
	make_waiting: function() {
		this.waiting = $('<div class="well" style="width: 63%; margin: 30px auto;">\
			<p style="text-align: center;">Loading Report...</p>\
			<div class="progress progress-striped active">\
				<div class="bar" style="width: 10%"></div></div>')
			.appendTo(this.wrapper);
	},
	make_grid_wrapper: function() {
		$('<div style="text-align: right;"> \
			<a href="#" class="grid-report-print"><i class="icon icon-print"></i> Print</a> \
			<span style="color: #aaa; margin: 0px 10px;"> | </span> \
			<a href="#" class="grid-report-export"><i class="icon icon-download-alt"></i> Export</a> \
		</div>').appendTo(this.wrapper);
		
		this.wrapper.find(".grid-report-export").click(function() { return me.export(); });
		
		this.grid_wrapper = $("<div style='height: 500px; border: 1px solid #aaa; \
			background-color: #eee; margin-top: 15px;'>")
			.appendTo(this.wrapper);
		this.id = wn.dom.set_unique_id(this.grid_wrapper.get(0));

		var me = this;
		// bind show event to reset cur_report_grid
		// and refresh filters from url
		// this must be called after init
		// because "wn.container.page" will only be set
		// once "load" event is over.
		
		$(wn.container.page).bind('show', function() {
			// reapply filters on show
			wn.cur_grid_report = me;
			me.apply_filters_from_route();
			me.refresh();
		});

		this.apply_filters_from_route();
	},
	load_filters: function(callback) {
		// override
		callback();
	},
	make_filters: function() {
		var me = this;
		$.each(this.filters, function(i, v) {
			v.fieldname = v.fieldname || v.label.replace(/ /g, '_').toLowerCase();
			var input = null;
			if(v.fieldtype=='Select') {
				input = me.appframe.add_select(v.label, [v.default_value]);
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
						me.refresh();
					}
				})
			}
			me.filter_inputs[v.fieldname] = input;
		});
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
		this.render();
	},
	apply_filters_from_route: function() {
		var hash = window.location.hash;
		var me = this;
		if(hash.indexOf('/') != -1) {
			$.each(hash.split('/').splice(1).join('/').split('&'), function(i, f) {
				var f = f.split("=");
				me.filter_inputs[f[0]].val(decodeURIComponent(f[1]));
			});
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
		this.waiting.toggle(false);
		
		if(!this.grid_wrapper) this.make_grid_wrapper();
		
		this.apply_link_formatters();
		this.prepare_data();
		
		this.grid = new Slick.Grid("#"+this.id, this.dataView, this.columns, this.options);

		// bind events
		this.dataView.onRowsChanged.subscribe(function (e, args) {
			grid.invalidateRows(args.rows);
			grid.render();
		});
		
		this.dataView.onRowCountChanged.subscribe(function (e, args) {
			grid.updateRowCount();
			grid.render();
		});
	},
	prepare_data_view: function(items) {
		// initialize the model
		this.dataView = new Slick.Data.DataView({ inlineFilters: true });
		this.dataView.beginUpdate();
		this.dataView.setItems(items);
		this.dataView.setFilter(this.dataview_filter);
		this.dataView.endUpdate();
	},
	export: function() {
		var me = this;
		var res = [$.map(this.columns, function(v) { return v.name; })];
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
	options: {
		editable: false,
		enableColumnReorder: false
	},
	dataview_filter: function(item) {
		var filters = wn.cur_grid_report.filter_inputs;
		for (i in filters) {
			var filter = filters[i].get(0);
			if(filter.opts.filter && !filter.opts.filter($(filter).val(), item, filter.opts)) {
				return false;
			}
		}
		return true;
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
	apply_link_formatters: function() {
		var me = this;
		$.each(this.columns, function(i, col) {
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
					var link_formatter = wn.cur_grid_report.columns[cell].link_formatter;	
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