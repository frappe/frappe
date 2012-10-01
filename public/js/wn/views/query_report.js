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

wn.provide("wn.views");

wn.views.QueryReport = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		// globalify for slickgrid
		this.appframe = this.parent.appframe;
		this.parent.query_report = this;
		this.make();
	},
	slickgrid_options: {
		enableColumnReorder: false,
	    showHeaderRow: true,
	    headerRowHeight: 30,
	    explicitInitialization: true,
	    multiColumnSort: true		
	},	
	make: function() {
		this.wrapper = $("<div>").appendTo($(this.parent).find(".layout-main"));
		$('<div class="query-edit" style="display: none;">\
			<div class="query-form" style="width: 60%; float: left;"></div>\
			<div class="help" style="width: 30%; float: left; margin-left: 15px;">\
				<b>Query Rules:</b><br>\
				<ol>\
					<li>Define column names as JSON objects to specifiy types and links:\
					<li>Labels are automatically defined from column headings.\
						To define for doctype, set `{"label": "Customer", "type": "Link", "options":"Customer"}`\
					<li>For DataTypes, use suffix: eg. `{"label":"Qty", "type":"Float"}`\
					<li>For Links, use suffix "link": eg. `customer:float`\
				</ol>\
			</div>\
			<hr style="clear: both;" />\
		</div>\
		<div class="result-area" style="height:400px; \
			border: 1px solid #aaa;"></div>').appendTo(this.wrapper);

		this.make_query_form();
		this.make_toolbar();
		this.import_slickgrid();
	},
	make_toolbar: function() {
		var me = this;
		this.appframe.add_button("Run", function() {
			// Run
			wn.call({
				method: "webnotes.widgets.query_report.run",
				args: {
					query: $(me.wrapper).find("textarea").val()
				},
				callback: function(r) {
					me.refresh(r.message.result, r.message.columns);
				}
			})
		}).addClass("btn-success");
		
		if(in_list(user_roles, "System Manager")) {
			// Edit
			this.appframe.add_button("Edit", function() {
				me.wrapper.find(".query-edit").slideToggle();
			});
			
			// Save
			this.appframe.add_button("Save", function() {
				var doc = me.query_form.get_values();
				if(!doc) return;
				doc.doctype = "Report"
				wn.call({
					method:"webnotes.client.save",
					args: {
						doclist: [doc],
					},
					callback: function(r) {
						//wn.set_route("query-form", doc.name);
					}
				})
			});
		}		
	},
	make_query_form: function() {
		this.query_form = new wn.ui.FieldGroup({
			parent: $(this.wrapper).find(".query-form").get(0),
			fields: [
				{label:"Report Name", reqd: 1, fieldname:"name"},
				{label:"Based on", fieldtype:"Link", options:"DocType",
					fieldname: "ref_doctype",
					reqd:1, description:"Permissions will be based on this DocType"},
				{label:"Query", fieldtype: "Text", reqd: 1}
			]
		});
		
		$(this.query_form.fields_dict.query.input).css({
			width: "100%", 
			height: "300px",
			"font-weight": "Normal", 
			"font-family": "Monaco, Courier, Fixed"
		});
	},
	import_slickgrid: function() {
		wn.require('lib/js/lib/slickgrid/slick.grid.css');
		wn.require('lib/js/lib/slickgrid/slick-default-theme.css');
		wn.require('lib/js/lib/slickgrid/jquery.event.drag.min.js');
		wn.require('lib/js/lib/slickgrid/slick.core.js');
		wn.require('lib/js/lib/slickgrid/slick.grid.js');
		wn.require('lib/js/lib/slickgrid/slick.dataview.js');
		wn.dom.set_style('.slick-cell { font-size: 12px; }\
		.slick-headerrow-column {\
	      background: #87ceeb;\
	      text-overflow: clip;\
	      -moz-box-sizing: border-box;\
	      box-sizing: border-box;\
	    }\
	    .slick-headerrow-column input {\
	      margin: 0;\
	      padding: 0;\
	      width: 100%;\
	      height: 100%;\
	      -moz-box-sizing: border-box;\
	      box-sizing: border-box;}');
	},
	refresh: function(result, columns) {
		this.make_data(result, columns);
		this.make_columns(columns);
		this.render(result, columns);		
	},
	render: function(result, columns) {
		this.columnFilters = {};
		this.make_dataview();
		this.id = wn.dom.set_unique_id($(this.wrapper.find(".result-area")).get(0));
		
		this.grid = new Slick.Grid("#"+this.id, this.dataView, this.columns, 
			this.slickgrid_options);
		this.setup_header_row();
		this.grid.init();
		this.setup_sort();
	},
	make_columns: function(columns) {
		this.columns = [{id: "_id", field: "_id", name: "Sr No", width: 60}]
			.concat($.map(columns, function(c) { 
			return {id: c, field: c, sortable: true,
				name: toTitle(c.replace(/_/g, " ")) }
		}));
	},
	make_data: function(result, columns) {
		this.data = $.map(result, function(row, row_idx) {
			var newrow = {};
			$.each(columns, function(i, col) {
				newrow[col] = row[i];
			});
			newrow._id = row_idx + 1;
			newrow.id = newrow.name ? newrow.name : ("_" + newrow._id);
			return newrow;
		});
	},
	make_dataview: function() {
		// initialize the model
		this.dataView = new Slick.Data.DataView({ inlineFilters: true });
		this.dataView.beginUpdate();
		this.dataView.setItems(this.data);
		this.dataView.setFilter(this.inline_filter);
		this.dataView.endUpdate();
		
		var me = this;
		this.dataView.onRowCountChanged.subscribe(function (e, args) {
			me.grid.updateRowCount();
			me.grid.render();
		});

		this.dataView.onRowsChanged.subscribe(function (e, args) {
			me.grid.invalidateRows(args.rows);
			me.grid.render();
		});
	},
	inline_filter: function (item) {
		var me = wn.container.page.query_report;
		for (var columnId in me.columnFilters) {
			if (columnId !== undefined && me.columnFilters[columnId] !== "") {
				var c = me.grid.getColumns()[me.grid.getColumnIndex(columnId)];
				if (!me.compare_values(item[c.field], me.columnFilters[columnId])) {
					return false;
				}
			}
		}
		return true;
	},
	compare_values: function(value, filter) {
		value = value + "";
		value = value.toLowerCase();
		filter = filter.toLowerCase();
		
		if(filter.length < value.length) {
			return filter==value.substr(0, filter.length)
		}
	},
	setup_header_row: function() {
		var me = this;
		
		$(this.grid.getHeaderRow()).delegate(":input", "change keyup", function (e) {
			var columnId = $(this).data("columnId");
			if (columnId != null) {
				me.columnFilters[columnId] = $.trim($(this).val());
				me.dataView.refresh();
			}
		});

		this.grid.onHeaderRowCellRendered.subscribe(function(e, args) {
			$(args.node).empty();
			$("<input type='text'>")
				.data("columnId", args.column.id)
				.val(me.columnFilters[args.column.id])
				.appendTo(args.node);
		});
	},
	setup_sort: function() {
		var me = this;
		this.grid.onSort.subscribe(function (e, args) {
			var cols = args.sortCols;

			me.data.sort(function (dataRow1, dataRow2) {
				for (var i = 0, l = cols.length; i < l; i++) {
					var field = cols[i].sortCol.field;
					var sign = cols[i].sortAsc ? 1 : -1;
					var value1 = dataRow1[field], value2 = dataRow2[field];
					var result = (value1 == value2 ? 0 : (value1 > value2 ? 1 : -1)) * sign;
					if (result != 0) {
						return result;
					}
				}
				return 0;
			});
			me.dataView.beginUpdate();
			me.dataView.setItems(me.data);
			me.dataView.endUpdate();
			me.dataView.refresh();
	    });
	}
})