// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views");
frappe.provide("frappe.query_reports");
frappe.provide("frappe.ui.graphs");

frappe.standard_pages["query-report"] = function() {
	var wrapper = frappe.container.add_page('query-report');

	frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Query Report'),
		single_column: true,
	});

	frappe.query_report = new frappe.views.QueryReport({
		parent: wrapper,
	});

	$(wrapper).bind("show", function() {
		frappe.query_report.load();
	});
}

frappe.views.QueryReport = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.flags = {};
		// globalify for slickgrid
		this.page = this.parent.page;
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
		var me = this;
		this.wrapper = $("<div>").appendTo(this.page.main);
		$('<div class="waiting-area" style="display: none;"></div>\
		<div class="no-report-area msg-box no-border" style="display: none;"></div>\
		<div class="chart_area" style="border-bottom: 1px solid #d1d8dd; padding: 0px 5%"></div>\
		<div class="results" style="display: none;">\
			<div class="result-area" style="height:70vh;"></div>\
			<button class="btn btn-secondary btn-default btn-xs expand-all hidden" style="margin: 10px;">'+__('Expand All')+'</button>\
			<button class="btn btn-secondary btn-default btn-xs collapse-all hidden" style="margin: 10px; margin-left: 0px;">'+__('Collapse All')+'</button>\
			<p class="help-msg alert alert-warning text-center" style="margin: 15px; margin-top: 0px;"></p>\
			<p class="msg-box small">\
				'+__('For comparative filters, start with')+' ">" or "<" or "!", e.g. >5 or >01-02-2012 or !0\
				<br>'+__('For ranges')+' ('+__('values and dates')+') use ":", \
					e.g. "5:10"  (' + __("to filter values between 5 & 10") + ')</p>\
		</div>').appendTo(this.wrapper);
		this.wrapper.find(".expand-all").on("click", function() { me.toggle_all(false);});
		this.wrapper.find(".collapse-all").on("click", function() { me.toggle_all(true);});
		this.chart_area = this.wrapper.find(".chart_area");
		this.make_toolbar();
	},
	toggle_expand_collapse_buttons: function(show) {
		this.wrapper.find(".expand-all, .collapse-all").toggleClass('hidden', !!!show);
	},
	make_toolbar: function() {
		var me = this;
		this.page.set_secondary_action(__('Refresh'), function() { me.refresh(); });

		// Edit
		this.page.add_menu_item(__('Edit'), function() {
			if(!frappe.user.is_report_manager()) {
				frappe.msgprint(__("You are not allowed to create / edit reports"));
				return false;
			}
			frappe.set_route("Form", "Report", me.report_name);
		}, true);

		this.page.add_menu_item(__("Print"), function() {
			frappe.ui.get_print_settings(false, function(print_settings) {
				me.print_settings = print_settings;
				me.print_report();
			}, me.report_doc.letter_head);
		}, true);

		this.page.add_menu_item(__("PDF"), function() {
			frappe.ui.get_print_settings(true, function(print_settings) {
				me.print_settings = print_settings;
				me.pdf_report();
			}, me.report_doc.letter_head);
		}, true);

		this.page.add_menu_item(__('Export'), function() {
			me.make_export();
		}, true);

		this.page.add_menu_item(__("Setup Auto Email"), function() {
			frappe.set_route('List', 'Auto Email Report', {'report' : me.report_name});
		}, true);

		if(frappe.model.can_set_user_permissions("Report")) {
			this.page.add_menu_item(__("User Permissions"), function() {
				frappe.route_options = {
					doctype: "Report",
					name: me.report_name
				};
				frappe.set_route('List', 'User Permission');
			}, true);
		}

		// add to desktop
		this.page.add_menu_item(__("Add to Desktop"), function() {
			frappe.add_to_desktop(me.report_name, null, me.report_name);
		}, true);
	},
	load: function() {
		// load from route
		var route = frappe.get_route();
		var me = this;
		if(route[1]) {
			if((me.report_name!=route[1]) || frappe.route_options) {
				me.report_name = route[1];
				this.wrapper.find(".no-report-area").toggle(false);
				me.page.set_title(__(me.report_name));

				frappe.model.with_doc("Report", me.report_name, function() {

					me.report_doc = frappe.get_doc("Report", me.report_name);

					frappe.model.with_doctype(me.report_doc.ref_doctype, function() {
						var module = locals.DocType[me.report_doc.ref_doctype].module;
						frappe.breadcrumbs.add(module)

						if(!frappe.query_reports[me.report_name]) {
							return frappe.call({
								method:"frappe.desk.query_report.get_script",
								args: {
									report_name: me.report_name
								},
								callback: function(r) {
									frappe.dom.eval(r.message.script || "");

									frappe.after_ajax(function() {
										var report_settings = frappe.query_reports[me.report_name];
										me.html_format = r.message.html_format;
										report_settings["html_format"] = r.message.html_format;

										me.setup_report();
									});
								}
							});
						} else {
							me.setup_report();
						}
					});
				});
			}
		} else {
			var msg = __("No Report Loaded. Please use query-report/[Report Name] to run a report.")
			this.wrapper.find(".no-report-area").html(msg).toggle(true);
		}
	},
	setup_report: function() {
		var me = this;
		this.page.set_title(__(this.report_name));
		this.page.clear_inner_toolbar();
		this.setup_filters();
		this.chart_area.toggle(false);
		this.toggle_expand_collapse_buttons(false);
		this.is_tree_report = false;

		var report_settings = frappe.query_reports[this.report_name];

		$.when(function() {
			if (report_settings.onload) {
				return report_settings.onload(me);
			}

		}()).then(function() {
			me.refresh();
		});
	},
	print_report: function() {
		if(!frappe.model.can_print(this.report_doc.ref_doctype)) {
			frappe.msgprint(__("You are not allowed to print this report"));
			return false;
		}
		if(this.html_format) {
			var content = frappe.render(this.html_format, {
				data: frappe.slickgrid_tools.get_filtered_items(this.dataView),
				filters: this.get_values(),
				report: this,
				data_to_be_printed: this.data_to_be_printed
			});

			frappe.render_grid({
				content: content,
				title: __(this.report_name),
				print_settings: this.print_settings,
			});
		} else {
			frappe.render_grid({
				grid: this.grid,
				report: this,
				title: __(this.report_name),
				print_settings: this.print_settings,
			});
		}
	},
	pdf_report: function() {
		var me = this;
		var base_url = frappe.urllib.get_base_url();
		var print_css = frappe.boot.print_css;

		if(!frappe.model.can_print(this.report_doc.ref_doctype)) {
			frappe.msgprint(__("You are not allowed to make PDF for this report"));
			return false;
		}

		var orientation = this.print_settings.orientation;
		var landscape = orientation == "Landscape" ? true: false
		var columns = this.grid.getColumns();
		if(this.html_format) {
			var content = frappe.render(this.html_format, {
				data: frappe.slickgrid_tools.get_filtered_items(this.dataView),
				filters:this.get_values(),
				report:this,
				data_to_be_printed: this.data_to_be_printed
			});

			//Render Report in HTML
			var html = frappe.render_template("print_template", {
				content:content,
				title:__(this.report_name),
				base_url: base_url,
				print_css: print_css,
				print_settings: this.print_settings,
				landscape: landscape,
				columns: columns
			});
		} else {
			// rows filtered by inline_filter of slickgrid
			var visible_idx = frappe.slickgrid_tools
				.get_view_data(this.columns, this.dataView)
				.map(row => row[0]).filter(idx => idx !== 'Sr No');

			var data = this.grid.getData().getItems();
			data = data.filter(d => visible_idx.includes(d._id));

			var content = frappe.render_template("print_grid", {
				columns:columns,
				data:data,
				title:__(this.report_name)
			})

			//Render Report in HTML
			var html = frappe.render_template("print_template",{
				content:content,
				title:__(this.report_name),
				base_url: base_url,
				print_css: print_css,
				print_settings: this.print_settings,
				landscape: landscape,
				columns: columns
			});
		}

		var orientation = this.print_settings.orientation;
		this.open_pdf_report(html, orientation)
	},
	open_pdf_report: function(html, orientation) {
		//Create a form to place the HTML content
		var formData = new FormData();

		//Push the HTML content into an element
		formData.append("html", html);
		formData.append("orientation", orientation);
		var blob = new Blob([], { type: "text/xml"});
		//formData.append("webmasterfile", blob);
		formData.append("blob", blob);

		var xhr = new XMLHttpRequest();
		xhr.open("POST", '/api/method/frappe.utils.print_format.report_to_pdf');
		xhr.setRequestHeader("X-Frappe-CSRF-Token", frappe.csrf_token);
		xhr.responseType = "arraybuffer";

		xhr.onload = function(success) {
			if (this.status === 200) {
				var blob = new Blob([success.currentTarget.response], {type: "application/pdf"});
				var objectUrl = URL.createObjectURL(blob);

				//Open report in a new window
				window.open(objectUrl);
			}
		};
		xhr.send(formData);
	},
	setup_filters: function() {
		if(this.setting_filters) return;

		this.clear_filters();
		var me = this;
		$.each(frappe.query_reports[this.report_name].filters || [], function(i, df) {
			if(df.fieldtype==="Break") {
				me.page.add_break();
			} else {
				var f = me.page.add_field(df);
				$(f.wrapper).addClass("filters pull-left");
				me.filters.push(f);

				if(df["default"]) {
					f.set_input(df["default"]);
				}
				if(df.fieldtype=="Check") {
					$(f.wrapper).find("input[type='checkbox']");
				}

				if(df.get_query) f.get_query = df.get_query;
				if(df.on_change) f.on_change = df.on_change;
				df.onchange = () => {
					if(!me.flags.filters_set) {
						// don't trigger change while setting filters
						return;
					}
					if (f.on_change) {
						f.on_change(me);
					} else {
						me.trigger_refresh();
					}
				}
				df.ignore_link_validation = true;
			}
		});

		// hide page form if no filters
		var $filters = $(this.parent).find('.page-form .filters');
		$(this.parent).find('.page-form').toggle($filters.length ? true : false);

		this.setting_filters = true;
		this.set_route_filters();
		this.setting_filters = false;

		this.set_filters_by_name();
		this.flags.filters_set = true;
	},
	clear_filters: function() {
		this.filters = [];
		$(this.parent).find('.page-form .filters').remove();
	},
	set_route_filters: function() {
		var me = this;
		if(frappe.route_options) {
			$.each(this.filters || [], function(i, f) {
				if(frappe.route_options[f.df.fieldname]!=null) {
					f.set_value(frappe.route_options[f.df.fieldname]);
				}
			});
		}
		frappe.route_options = null;
	},
	set_filters_by_name: function() {
		frappe.query_report_filters_by_name = {};

		for(var i in this.filters) {
			frappe.query_report_filters_by_name[this.filters[i].df.fieldname] = this.filters[i];
		}
	},
	refresh: function() {
		// throttle
		// stop refresh from being called multiple times (from triggers ?)
		if (!this.request_refresh) {
			this.request_refresh = setTimeout(() => {
				this._refresh();
				this.request_refresh = null;
			}, 300);
		}
	},
	_refresh: function() {
		// Run
		var me = this;

		this.wrapper.find(".results").toggle(false);
		try {
			var filters = this.get_values(true);
		} catch(e) {
			// don't run report
			return;
		}

		this.waiting = frappe.messages.waiting(this.wrapper.find(".waiting-area").empty().toggle(true),
			__("Loading Report") + "...");
		this.wrapper.find(".no-report-area").toggle(false);

		if (this.report_ajax) {
			// abort previous request
			this.report_ajax.abort();
		}

		this.chart_area.toggle(false);

		this.report_ajax = frappe.call({
			method: "frappe.desk.query_report.run",
			type: "GET",
			args: {
				"report_name": me.report_name,
				filters: filters
			},
			callback: function(r) {
				me.report_ajax = undefined;
				me.make_results(r.message);
			}
		});

		return this.report_ajax;
	},
	trigger_refresh: function() {
		var me = this;
		var filters = me.get_values();

		// check if required filters are not missing
		var missing = false;
		$.each(me.filters, function(k, _f) {
			if (_f.df.reqd && !filters[_f.df.fieldname]) {
				missing = true;
				return;
			}
		});

		if (!missing) {
			me.refresh();
		}
	},
	get_values: function(raise) {
		var filters = {};
		var mandatory_fields = [];
		$.each(this.filters || [], function(i, f) {
			var v = f.get_value();
			// TODO: hidden fields dont have $input
			if(f.df.hidden) v = f.value;
			if(v === '%') v = null;
			if(f.df.reqd && !v) mandatory_fields.push(f.df.label);
			if(v) filters[f.df.fieldname] = v;
		})
		if(raise && mandatory_fields.length) {
			this.chart_area.hide();
			this.wrapper.find(".waiting-area").empty().toggle(false);
			this.wrapper.find(".no-report-area").html(__("Please set filters")).toggle(true);
			if(raise) {
				console.log('filter missing: ' + mandatory_fields);
				throw "Filters required";
			}
		}

		return filters;
	},
	make_results: function(res) {
		this.wrapper.find(".waiting-area, .no-report-area").empty().toggle(false);
		this.wrapper.find(".results").toggle(true);
		this.make_columns(res.columns);
		this.make_data(res.result, res.columns);
		this.filter_hidden_columns();
		this.render(res);
	},
	render: function(res) {
		this.columnFilters = {};
		this.make_dataview();
		this.id = frappe.dom.set_unique_id(this.wrapper.find(".result-area").addClass("slick-wrapper").get(0));

		this.grid = new Slick.Grid("#"+this.id, this.dataView, this.columns,
			this.slickgrid_options);

		if (!frappe.dom.is_touchscreen()) {
			this.grid.setSelectionModel(new Slick.CellSelectionModel());
			this.grid.registerPlugin(new Slick.CellExternalCopyManager({
				dataItemColumnValueExtractor: function(item, columnDef, value) {
					return item[columnDef.field];
				}
			}));
		}

		this.setup_header_row();
		this.grid.init();
		this.setup_sort();

		// further setup of grid like click subscription for tree
		if (this.get_query_report_opts().tree) {
			this.setup_tree();
		}

		this.set_message(res.message);
		this.setup_chart(res);
		this.set_print_data(res.data_to_be_printed);

		this.toggle_expand_collapse_buttons(this.is_tree_report);
	},

	make_columns: function(columns) {
		var me = this;
		var formatter = this.get_formatter();

		this.columns = [{id: "_id", field: "_id", name: __("Sr No"), width: 60}]
			.concat($.map(columns, function(c, i) {
				if ($.isPlainObject(c)) {
					var df = c;
				} else if (c.indexOf(":")!==-1) {
					var opts = c.split(":");
					var df = {
						label: opts.length<=2 ? opts[0] : opts.slice(0, opts.length - 2).join(":"),
						fieldtype: opts.length<=2 ? opts[1] : opts[opts.length - 2],
						width: opts.length<=2 ? opts[2] : opts[opts.length - 1]
					};
					if (df.fieldtype.indexOf("/")!==-1) {
						var tmp = df.fieldtype.split("/");
						df.fieldtype = tmp[0];
						df.options = tmp[1];
					}
					df.width = cint(df.width);
				} else {
					var df = {
						label: c,
						fieldtype: "Data"
					};
				}

				if (!df.fieldtype) df.fieldtype = "Data";
				if (!cint(df.width)) df.width = 80;

				var col = $.extend({}, df, {
					label: df.label || (df.fieldname && __(toTitle(df.fieldname.replace(/_/g, " ")))) || "",
					sortable: true,
					df: df,
					formatter: formatter
				});

				col.field = df.fieldname || df.label;
				df.label = __(df.label);
				col.name = col.id = col.label = df.label;

				if(df.width < 0) {
					col.hidden = true;
				}

				return col
			}));
	},
	filter_hidden_columns: function() {
		this.columns = $.map(this.columns, function(c, i) {
			return (c.hidden==1 ? null : c);
		});
	},
	get_query_report_opts: function() {
		return frappe.query_reports[this.report_name] || {};
	},
	get_formatter: function() {
		var formatter = function(row, cell, value, columnDef, dataContext, for_print) {
			var value = frappe.format(value, columnDef.df, {for_print: for_print, always_show_decimals: true}, dataContext);

			if (columnDef.df.is_tree) {
				value = frappe.query_report.tree_formatter(row, cell, value, columnDef, dataContext);
			}

			return value;
		};

		var query_report_opts = this.get_query_report_opts();
		if (query_report_opts.formatter) {
			var default_formatter = formatter;

			// custom formatter
			formatter = function(row, cell, value, columnDef, dataContext) {
				return query_report_opts.formatter(row, cell, value, columnDef, dataContext, default_formatter);
			}
		}

		return formatter;
	},
	make_data: function(result, columns) {
		var me = this;
		this.data = [];
		for(var row_idx=0, l=result.length; row_idx < l; row_idx++) {
			var row = result[row_idx];
			if ($.isPlainObject(row)) {
				var newrow = row;
			} else {
				var newrow = {};
				for(var i=1, j=this.columns.length; i<j; i++) {
					newrow[this.columns[i].field] = row[i-1];
				}
			}
			newrow._id = row_idx + 1;
			newrow.id = newrow.name ? newrow.name : ("_" + newrow._id);
			this.data.push(newrow);
		}
		if(this.data.length && this.report_doc.add_total_row) {
			this.total_row_id = this.data[this.data.length - 1].id;
		}
	},
	make_dataview: function() {
		// initialize the model
		this.dataView = new Slick.Data.DataView({ inlineFilters: true });
		this.dataView.beginUpdate();

		if (this.get_query_report_opts().tree) {
			this.setup_item_by_name();
			this.dataView.setFilter(this.tree_filter);
		} else {
			this.dataView.setFilter(this.inline_filter);
		}

		this.dataView.setItems(this.data);
		this.dataView.endUpdate();

		var me = this;
		this.dataView.onRowCountChanged.subscribe(function (e, args) {
			me.update_totals_row();
			me.grid.updateRowCount();
			me.grid.render();
		});

		this.dataView.onRowsChanged.subscribe(function (e, args) {
			me.grid.invalidateRows(args.rows);
			me.grid.render();
		});
	},
	update_totals_row: function() {
		if(!this.report_doc.add_total_row) return;

		const number_fields = ['Currency', 'Float', 'Int'];
		const fields = this.columns
			.filter(col => number_fields.includes(col.fieldtype))
			.map(col => col.field);

		// reset numeric fields
		let updated_totals = Object.assign({}, this.dataView.getItemById(this.total_row_id));
		fields.map(field => {
			updated_totals[field] = 0.0;
		});

		const data_length = this.dataView.getLength();
		// loop all the rows except the last Total row
		for (let i = 0; i < data_length - 1; i++) {
			const item = this.dataView.getItem(i);
			fields.map(field => {
				updated_totals[field] += item[field];
			});
		}
		this.dataView.updateItem(updated_totals.id, updated_totals);
	},
	inline_filter: function (item) {
		var me = frappe.container.page.query_report;
		if(me.report_doc.add_total_row) {
			// always show totals row
			if(item.id === me.total_row_id) return true;
		}
		for (var columnId in me.columnFilters) {
			if (columnId !== undefined && me.columnFilters[columnId] !== "") {
				var c = me.grid.getColumns()[me.grid.getColumnIndex(columnId)];
				if (!me.compare_values(item[c.field], me.columnFilters[columnId],
						me.columns[me.grid.getColumnIndex(columnId)])) {
					return false;
				}
			}
		}
		return true;
	},
	setup_item_by_name: function() {
		this.item_by_name = {};
		this.name_field = this.get_query_report_opts().name_field;
		this.parent_field = this.get_query_report_opts().parent_field;
		var initial_depth = this.get_query_report_opts().initial_depth;
		for (var i=0, l=this.data.length; i<l; i++) {
			var item = this.data[i];

			// only if name field has value
			if (item[this.name_field]) {
				this.item_by_name[item[this.name_field]] = item;
			}

			// set collapsed if initial depth is specified
			if (initial_depth && item.indent && item.indent>=(initial_depth - 1)) {
				item._collapsed = true;
			}
		}

	},
	toggle_all: function(collapse) {
		var me = this;
		for(var i=0, l=this.data.length; i<l; i++) {
			var item = this.data[i];
			item._collapsed = collapse;
			me.dataView.updateItem(item.id, item);
		}
	},
	tree_filter: function(item) {
		var me = frappe.query_report;

		// apply inline filters
		if (!me.inline_filter(item)) return false;

		try {
			var parent_name = item[me.parent_field];
			while (parent_name) {
				if (!me.item_by_name[parent_name] || me.item_by_name[parent_name]._collapsed) {
					return false;
				}
				parent_name = me.item_by_name[parent_name][me.parent_field];
			}
			return true;
		} catch (e) {
			if (e.message.indexOf("[parent_name] is undefined")!==-1) {
				frappe.msgprint(__("Unable to display this tree report, due to missing data. Most likely, it is being filtered out due to permissions."));
			}

			throw e;
		}
	},
	tree_formatter: function(row, cell, value, columnDef, dataContext) {
		var me = frappe.query_report;
		me.is_tree_report = true;
		var $span = $("<span></span>")
			.css("padding-left", (cint(dataContext.indent) * 21) + "px")
			.html(value);

		var idx = me.dataView.getIdxById(dataContext.id);
		var show_toggle = me.data[idx + 1] && (me.data[idx + 1].indent > me.data[idx].indent)

		if (dataContext[me.name_field] && show_toggle) {
			$('<span class="toggle"></span>')
				.addClass(dataContext._collapsed ? "expand" : "collapse")
				.css("margin-right", "7px")
				.prependTo($span);
		}

		return $span.wrap("<p></p>").parent().html();
	},
	compare_values: function(value, filter, columnDef) {
		var invert = false;

		// check if invert
		if(filter[0]=="!") {
			invert = true;
			filter = filter.substr(1);
		}

		var out = false;
		var cond = "=="

		// parse condition
		if(filter[0]==">") {
			filter = filter.substr(1);
			cond = ">"
		} else if(filter[0]=="<") {
			filter = filter.substr(1);
			cond = "<"
		}

		if(in_list(['Float', 'Currency', 'Int', 'Date'], columnDef.df.fieldtype)) {
			// non strings
			if(filter.indexOf(":")==-1) {
				if(columnDef.df.fieldtype=="Date") {
					filter = frappe.datetime.user_to_str(filter);
				}

				if(in_list(["Float", "Currency", "Int"], columnDef.df.fieldtype)) {
					value = flt(value);
					filter = flt(filter);
				}

				out = eval("value" + cond + "filter");
			} else {
				// range
				filter = filter.split(":");
				if(columnDef.df.fieldtype=="Date") {
					filter[0] = frappe.datetime.user_to_str(filter[0]);
					filter[1] = frappe.datetime.user_to_str(filter[1]);
				}

				if(in_list(["Float", "Currency", "Int"], columnDef.df.fieldtype)) {
					value = flt(value);
					filter[0] = flt(filter[0]);
					filter[1] = flt(filter[1]);
				}

				out = value >= filter[0] && value <= filter[1];
			}
		} else {
			// string
			value = value + "";
			value = value.toLowerCase();
			filter = filter.toLowerCase();
			out = value.indexOf(filter) != -1;
		}

		if(invert)
			return !out;
		else
			return out;
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
				// Totals row should always be last
				if(me.report_doc.add_total_row) {
					if(dataRow1.id === me.total_row_id) {
						return 1;
					}
					if(dataRow2.id === me.total_row_id) {
						return -1;
					}
				}

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
	},
	setup_tree: function() {
		// set these in frappe.query_reports[report_name]
		// "tree": true,
		// "name_field": "account",
		// "parent_field": "parent_account",
		// "initial_depth": 3

		// also set "is_tree" true for ColumnDef

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

	make_export: function() {

		var me = this;
		this.title = this.report_name;

		if(!frappe.model.can_export(this.report_doc.ref_doctype)) {
			frappe.msgprint(__("You are not allowed to export this report"));
			return false;
		}

		frappe.prompt({fieldtype:"Select", label: __("Select File Type"), fieldname:"file_format_type",
			options:"Excel\nCSV", default:"Excel", reqd: 1},
			function(data) {
				var view_data = frappe.slickgrid_tools.get_view_data(me.columns, me.dataView);
				var result = view_data.map(row => row.splice(1));

				// to download only visible rows
				var visible_idx = view_data.map(row => row[0]).filter(sr_no => sr_no !== 'Sr No');

				if (data.file_format_type == "CSV") {
					frappe.tools.downloadify(result, null, me.title);
				}

				else if (data.file_format_type == "Excel") {
					try {
						var filters = me.get_values(true);
					} catch(e) {
						return;
					}
					var args = {
						cmd: 'frappe.desk.query_report.export_query',
						report_name: me.report_name,
						file_format_type: data.file_format_type,
						filters: filters,
						visible_idx: visible_idx,
					}

					open_url_post(frappe.request.url, args);
				}
			}, __("Export Report: "+ me.title), __("Download"));

		return false;
	},

	set_message: function(msg) {
		if(msg) {
			this.wrapper.find(".help-msg").html(msg).toggle(true);
		} else {
			this.wrapper.find(".help-msg").empty().toggle(false);
		}
	},

	setup_chart: function(res) {
		this.chart_area.toggle(false);

		if (this.get_query_report_opts().get_chart_data) {
			var opts = this.get_query_report_opts().get_chart_data(res.columns, res.result);
		} else if (res.chart) {
			var opts = res.chart;
		} else {
			return;
		}

		$.extend(opts, {
			wrapper: this.chart_area,
		});

		this.chart = new frappe.ui.Chart(opts);
		if(this.chart && opts.data && opts.data.rows && opts.data.rows.length) {
			this.chart_area.toggle(true);
		}
	},

	set_print_data: function(data_to_be_printed) {
		this.data_to_be_printed = data_to_be_printed;
	}
})
