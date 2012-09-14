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
				input = me.appframe.add_select(v.label, ["Select "+v.options]);
			} else if(v.fieldtype=='Button') {
				input = me.appframe.add_button(v.label);
			} else if(v.fieldtype=='Date') {
				input = me.appframe.add_date(v.label);
			} else if(v.fieldtype=='Label') {
				input = me.appframe.add_label(v.label);
			}
			input && (input.get(0).opts = v);
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
		this.prepare_data();
		this.render();
	},
	render: function() {
		// new slick grid
		this.waiting.toggle(false);
		this.grid_wrapper = $("<div style='height: 500px; border: 1px solid #aaa;'>")
			.appendTo(this.wrapper);
		this.id = wn.dom.set_unique_id(this.grid_wrapper.get(0));
		
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
	options: {
		editable: false,
		enableColumnReorder: false
	},
	dataview_filter: function(item) {
		return true;
	},
	date_formatter: function(row, cell, value, columnDef, dataContext) {
		return dateutil.str_to_user(value);
	},
	currency_formatter: function(row, cell, value, columnDef, dataContext) {
		return "<div style='text-align: right;'>" + fmt_money(value) + "</div>";
	}
})