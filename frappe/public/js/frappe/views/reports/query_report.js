// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import DataTable from 'frappe-datatable';

frappe.provide('frappe.views');
frappe.provide('frappe.query_reports');

frappe.standard_pages['query-report'] = function() {
	var wrapper = frappe.container.add_page('query-report');

	frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Query Report'),
		single_column: true,
	});

	frappe.query_report = new frappe.views.QueryReport({
		parent: wrapper,
	});

	$(wrapper).bind('show', function() {
		frappe.query_report.show();
	});
};

frappe.views.QueryReport = class QueryReport extends frappe.views.BaseList {
	show() {
		this.init().then(() => this.load());
	}

	init() {
		if (this.init_promise) {
			return this.init_promise;
		}

		let tasks = [
			this.setup_defaults,
			this.setup_page,
			this.setup_report_wrapper,
			this.setup_events
		].map(fn => fn.bind(this));
		this.init_promise = frappe.run_serially(tasks);
		return this.init_promise;
	}

	setup_defaults() {
		this.route = frappe.get_route();
		this.page_name = frappe.get_route_str();

		// Setup buttons
		this.primary_action = null;
		this.secondary_action = {
			label: __('Refresh'),
			action: () => {
				this.setup_progress_bar();
				this.refresh();
			}
		};

		// throttle refresh for 300ms
		this.refresh = frappe.utils.throttle(this.refresh, 300);

		this.menu_items = [];
	}

	setup_events() {
		frappe.realtime.on("report_generated", (data) => {
			if(data.report_name) {
				this.prepared_report_action = "Rebuild";
				// If generated report and currently active Prepared Report has same fiters
				// then refresh the Prepared Report
				// Otherwise show alert with the link to the Prepared Report
				if(data.name == this.prepared_report_doc_name) {
					this.refresh();
				} else {
					let alert_message = `Report ${this.report_name} generated.
						<a href="#query-report/${this.report_name}/?prepared_report_name=${data.name}">View</a>`;
					frappe.show_alert({message: alert_message, indicator: 'orange'});
				}
			}
		});
		this.page.wrapper.on('click', '[data-action]', (e) => {
			let action_name = $(e.currentTarget).data('action');
			let action = this[action_name];
			if (action.call) {
				action.call(this, e);
			}
		});
	}

	load() {
		if (frappe.get_route().length < 2) {
			this.toggle_nothing_to_show(true);
			return;
		}

		if (this.report_name !== frappe.get_route()[1]) {
			// this.toggle_loading(true);
			// different report
			this.load_report();
		}
		else if (frappe.has_route_options()) {
			// filters passed through routes
			// so refresh report again
			this.refresh_report();
		} else {
			// same report
			// don't do anything to preserve state
			// like filters and datatable column widths
		}
	}

	load_report() {
		this.page.clear_inner_toolbar();
		this.route = frappe.get_route();
		this.page_name = frappe.get_route_str();
		this.report_name = this.route[1];
		this.page_title = __(this.report_name);
		this.show_save = false;
		this.menu_items = this.get_menu_items();
		this.datatable = null;
		this.prepared_report_action = "New";


		frappe.run_serially([
			() => this.get_report_doc(),
			() => this.get_report_settings(),
			() => this.setup_progress_bar(),
			() => this.setup_page_head(),
			() => this.refresh_report(),
			() => this.add_make_chart_button()
		]);
	}

	add_make_chart_button(){
		this.page.add_inner_button(__("Set Chart"), () => {
			this.get_possible_chart_options();
		});
	}

	refresh_report() {
		this.toggle_message(true);

		return frappe.run_serially([
			() => this.setup_filters(),
			() => this.set_route_filters(),
			() => this.report_settings.onload && this.report_settings.onload(this),
			() => this.get_user_settings(),
			() => this.refresh()
		]);
	}

	get_report_doc() {
		return frappe.model.with_doc('Report', this.report_name)
			.then(doc => {
				this.report_doc = doc;
			})
			.then(() => frappe.model.with_doctype(this.report_doc.ref_doctype));
	}

	get_report_settings() {
		return new Promise((resolve, reject) => {
			if (frappe.query_reports[this.report_name]) {
				this.report_settings = frappe.query_reports[this.report_name];
				resolve();
			} else {
				frappe.xcall('frappe.desk.query_report.get_script', {
					report_name: this.report_name
				}).then(settings => {
					frappe.dom.eval(settings.script || '');
					frappe.after_ajax(() => {
						this.report_settings = this.get_local_report_settings();
						this.report_settings.html_format = settings.html_format;
						this.report_settings.execution_time = settings.execution_time || 0;
						frappe.query_reports[this.report_name] = this.report_settings;
						resolve();
					});
				}).catch(reject);
			}
		});
	}

	get_local_report_settings() {
		let report_script_name = this.report_doc.report_type === 'Custom Report'
			? this.report_doc.reference_report
			: this.report_name;
		return frappe.query_reports[report_script_name] || {};
	}

	setup_progress_bar() {
		let seconds_elapsed = 0;
		const execution_time = this.report_settings.execution_time || 0;

		if (execution_time < 5) return;

		this.interval = setInterval(function()  {
			seconds_elapsed += 1;
			frappe.show_progress(__('Preparing Report'), seconds_elapsed, execution_time);
		}, 1000);
	}

	setup_filters() {
		this.clear_filters();
		const { filters = [] } = this.report_settings;

		this.filters = filters.map(df => {
			if (df.fieldtype === 'Break') return;

			let f = this.page.add_field(df);

			if (df.default) {
				f.set_input(df.default);
			}

			if (df.get_query) f.get_query = df.get_query;
			if (df.on_change) f.on_change = df.on_change;

			df.onchange = () => {
				let current_filters = this.get_filter_value();
				if (this.previous_filters
					&& (JSON.stringify(this.previous_filters) === JSON.stringify(current_filters))) {
					// filter values have not changed
					return;
				}

				// clear previous_filters after 10 seconds, to allow refresh for new data
				this.previous_filters = current_filters;
				setTimeout(() => this.previous_filters = null, 10000);

				if (f.on_change) {
					f.on_change(this);
				} else {
					if (this.prepared_report) {
						this.reset_report_view();
					}
					else if (!this._no_refresh) {
						this.refresh();
					}
				}
			};

			f = Object.assign(f, df);

			return f;

		}).filter(Boolean);

		if (this.filters.length === 0) {
			// hide page form if no filters
			this.page.hide_form();
		} else {
			this.page.show_form();
		}
	}

	set_filters(filters) {
		this.filters.map(f => {
			f.set_input(filters[f.fieldname]);
		});
	}

	set_route_filters() {
		if(frappe.route_options) {
			const fields = Object.keys(frappe.route_options);

			const filters_to_set = this.filters.filter(f => fields.includes(f.df.fieldname));

			const promises = filters_to_set.map(f => {
				return () => {
					const value = frappe.route_options[f.df.fieldname];
					f.set_value(value);
				};
			});
			promises.push(() => {
				frappe.route_options = null;
			});

			return frappe.run_serially(promises);
		}
	}

	clear_filters() {
		this.page.clear_fields();
	}

	refresh() {
		this.toggle_message(true);
		let filters = this.get_filter_values(true);

		// only one refresh at a time
		if (this.last_ajax) {
			this.last_ajax.abort();
		}

		const query_params = this.get_query_params();

		if (query_params.prepared_report_name) {
			filters.prepared_report_name = query_params.prepared_report_name;
		}

		return new Promise(resolve => {
			this.last_ajax = frappe.call({
				method: 'frappe.desk.query_report.run',
				type: 'GET',
				args: {
					report_name: this.report_name,
					filters: filters,
				},
				callback: resolve,
				always: () => this.page.btn_secondary.prop('disabled', false)
			});
		}).then(r => {
			let data = r.message;
			this.hide_status();
			clearInterval(this.interval);

			this.execution_time = data.execution_time || 0.1;

			if (data.prepared_report) {
				this.prepared_report = true;
				// If query_string contains prepared_report_name then set filters
				// to match the mentioned prepared report doc and disable editing
				if (query_params.prepared_report_name) {
					this.prepared_report_action = "Edit";
					const filters_from_report = JSON.parse(data.doc.filters);
					Object.values(this.filters).forEach(function(field) {
						if (filters_from_report[field.fieldname]) {
							field.set_input(filters_from_report[field.fieldname]);
						}
						if (field.input) {
							field.input.disabled = true;
						}
					});
				}
				this.add_prepared_report_buttons(data.doc);
			}
			this.toggle_message(false);
			if (data.result && data.result.length) {
				this.prepare_report_data(data);

				const chart_options = this.get_chart_options(data);
				this.$chart.empty();
				if(chart_options) {
					this.render_chart(chart_options);
				}
				else {
					this.$chart.empty();
					if (this.chart_fields) {
						const chart_options = this.make_chart_options(this.chart_fields);
						chart_options && this.render_chart(chart_options);
					}
				}

				this.render_datatable();
			} else {
				this.data = [];
				this.toggle_nothing_to_show(true);
			}

			this.show_footer_message();
			frappe.hide_progress();
		});
	}

	get_query_params() {
		const query_string = frappe.utils.get_query_string(frappe.get_route_str());
		const query_params = frappe.utils.get_query_params(query_string);
		return query_params;
	}

	add_prepared_report_buttons(doc) {
		if(doc){
			this.page.add_inner_button(__("Download Report"), function (){
				window.open(
					frappe.urllib.get_full_url(
						"/api/method/frappe.core.doctype.prepared_report.prepared_report.download_attachment?"
						+"dn="+encodeURIComponent(doc.name)));
			});

			const part1 = __('This report was generated {0}.', [frappe.datetime.comment_when(doc.report_end_time)]);
			const part2 = __('To get the updated report, click on {0}.', [__('Rebuild')]);
			const part3 = __('See all past reports.');

			this.show_status(`
				<span class="indicator orange">
					${part1}
					${part2}
					<a href="#List/Prepared%20Report?report_name=${this.report_name}">${part3}</a>
				</span>
			`);
		};

		// Three cases
		// 1. First time with given filters, no data.
		// 2. Showing data from specific report
		// 3. Showing data from an old report without specific report name
		if(this.prepared_report_action == "New") {
			this.page.set_primary_action(
				__("Generate New Report"),
				() => {
					this.generate_background_report();
				}
			);
		} else if(this.prepared_report_action == "Edit") {
			this.page.set_primary_action(
				__("Edit"),
				() => {
					frappe.set_route(frappe.get_route());
				}
			);
		} else if(this.prepared_report_action == "Rebuild"){
			this.page.set_primary_action(
				__("Rebuild"),
				this.generate_background_report.bind(this)
			);
		}
	}

	generate_background_report() {
		let mandatory = this.filters.filter(f => f.df.reqd);
		let missing_mandatory = mandatory.filter(f => !f.get_value());
		if (!missing_mandatory.length){
			let filters = this.get_filter_values(true);
			return new Promise(resolve => frappe.call({
				method: 'frappe.desk.query_report.background_enqueue_run',
				type: 'GET',
				args: {
					report_name: this.report_name,
					filters: filters
				},
				callback: resolve
			})).then(r => {
				const data = r.message;
				// Rememeber the name of Prepared Report doc
				this.prepared_report_doc_name = data.name;
				let alert_message = `Report initiated. You can track its status
					<a class='text-info' href='#Form/Prepared Report/${data.name}'>here</a>`;
				frappe.show_alert({message: alert_message, indicator: 'orange'});
				this.toggle_nothing_to_show(true);
			});
		}
	}

	prepare_report_data(data) {
		this.raw_data = data;
		this.columns = this.prepare_columns(data.columns);
		this.custom_columns = [];
		this.data = this.prepare_data(data.result);
		this.linked_doctypes = this.get_linked_doctypes();
		this.tree_report = this.data.some(d => 'indent' in d);
	}

	render_datatable() {
		let data = this.data;
		let columns = this.columns.filter((col) => !col.hidden);

		if (this.raw_data.add_total_row) {
			data = data.slice();
			data.splice(-1, 1);
		}

		if (this.datatable && this.datatable.options
			&& (this.datatable.options.showTotalRow ===this.raw_data.add_total_row)) {
			this.datatable.options.treeView = this.tree_report;
			this.datatable.refresh(data, columns);
		} else {
			let datatable_options = {
				columns: columns,
				data: data,
				inlineFilters: true,
				treeView: this.tree_report,
				layout: 'fixed',
				cellHeight: 33,
				showTotalRow: this.raw_data.add_total_row,
				direction: frappe.utils.is_rtl() ? 'rtl' : 'ltr',
				hooks: {
					columnTotal: frappe.utils.report_column_total
				}
			};

			if (this.report_settings.get_datatable_options) {
				datatable_options = this.report_settings.get_datatable_options(datatable_options);
			}
			this.datatable = new DataTable(this.$report[0], datatable_options);
		}

		if (typeof this.report_settings.initial_depth == "number") {
			this.datatable.rowmanager.setTreeDepth(this.report_settings.initial_depth);
		}
		if (this.report_settings.after_datatable_render) {
			this.report_settings.after_datatable_render(this.datatable);
		}
	}

	get_chart_options(data) {
		let options = this.report_settings.get_chart_data
			? this.report_settings.get_chart_data(data.columns, data.result)
			: data.chart
				? data.chart
				: undefined;

		if (!(options && options.data && options.data.labels && options.data.labels.length > 0)) return;

		if (options.fieldtype) {
			options.tooltipOptions = {
				formatTooltipY: d => frappe.format(d, {
					fieldtype: options.fieldtype,
					options: options.options
				})
			};
		}
		options.axisOptions = {
			shortenYAxisNumbers: 1
		};

		return options;
	}

	render_chart(options) {
		this.$chart.empty();
		this.chart = new frappe.Chart(this.$chart[0], options);
		this.$chart.show();
	}

	make_chart_options({ y_field, x_field, chart_type, color }) {
		const type = chart_type.toLowerCase();
		const colors = color ? [color] : undefined;

		let columns = this.columns;
		let rows =  this.raw_data.result.filter(value => Object.keys(value).length);

		let labels = get_column_values(x_field);

		let dataset_values = get_column_values(y_field).map(d => Number(d));

		if(this.raw_data.add_total_row) {
			labels = labels.slice(0, -1);
			dataset_values = dataset_values.slice(0, -1);
		}

		return {
			data: {
				labels: labels,
				datasets: [
					{ values: dataset_values }
				]
			},
			truncateLegends: 1,
			type: type,
			colors: colors,
			axisOptions: {
				shortenYAxisNumbers: 1
			}
		};

		function get_column_values(column_name) {
			if (Array.isArray(rows[0])) {
				let column_index = columns.findIndex(column => column.fieldname == column_name);
				return rows.map(row => row[column_index]);
			} else {
				return rows.map(row => row[column_name]);
			}
		}
	}

	get_possible_chart_options() {
		const columns = this.columns;
		const rows =  this.raw_data.result.filter(value => Object.keys(value).length);
		const first_row = Array.isArray(rows[0]) ? rows[0] : columns.map(col => rows[0][col.fieldname]);
		const me = this

		const indices = first_row.reduce((accumulator, current_value, current_index) => {
			if (Number.isFinite(current_value)) {
				accumulator.push(current_index);
			}
			return accumulator;
		}, []);

		function preview_chart() {
			const wrapper = $(dialog.fields_dict["chart_preview"].wrapper);
			const values = dialog.get_values(true);
			if (values.x_field && values.y_field) {
				let options = me.make_chart_options(values);
				wrapper.empty();
				new frappe.Chart(wrapper[0], options);
				wrapper.find('.chart-container .title, .chart-container .sub-title').hide();
				wrapper.show();
			}
			else {
				wrapper[0].innerHTML = `<div class="flex justify-center align-center text-muted" style="height: 120px; display: flex;">
					<div>Please select X and Y fields</div>
				</div>`;
			}
		}

		function get_options(fields) {
			return fields.map((field) => {
				return {label: field.label, value: field.fieldname};
			});
		}

		const numeric_fields = columns.filter((col, i) => indices.includes(i));
		const non_numeric_fields = columns.filter((col, i) => !indices.includes(i))

		const dialog = new frappe.ui.Dialog({
			title: __('Create Chart'),
			fields: [
				{
					fieldname: 'y_field',
					label: 'Y Field',
					fieldtype: 'Select',
					options: get_options(numeric_fields),
					onchange: preview_chart
				},
				{
					fieldname: 'x_field',
					label: 'X Field',
					fieldtype: 'Select',
					options: get_options(non_numeric_fields),
					onchange: preview_chart
				},
				{
					fieldname: 'cb_1',
					fieldtype: 'Column Break'
				},
				{
					fieldname: 'chart_type',
					label: 'Type of Chart',
					fieldtype: 'Select',
					options: ['Bar', 'Line', 'Percentage', 'Pie', 'Donut'],
					default: 'Bar',
					onchange: preview_chart
				},
				{
					fieldname: 'color',
					label: 'Color',
					fieldtype: 'Color',
					depends_on: doc => ['Bar', 'Line'].includes(doc.chart_type),
					onchange: preview_chart,
				},
				{
					fieldname: 'sb_1',
					fieldtype: 'Section Break',
					label: 'Chart Preview'
				},
				{
					fieldname: 'chart_preview',
					label: 'Chart Preview',
					fieldtype: 'HTML',
				}
			],
			primary_action_label: __('Create'),
			primary_action: (values) => {
				let options = me.make_chart_options(values);
				me.chart_fields = values

				let x_field_label = numeric_fields.filter((field) => field.fieldname == values.y_field)[0].label;
				let y_field_label = non_numeric_fields.filter((field) => field.fieldname == values.x_field)[0].label;

				options.title = __(`${this.report_name}: ${x_field_label} vs ${y_field_label}`);

				this.render_chart(options);

				dialog.hide();
			}
		});

		dialog.show();

		// load preview after dialog animation
		setTimeout(preview_chart, 500);
	}

	get_user_settings() {
		return frappe.model.user_settings.get(this.report_name)
			.then(user_settings => {
				this.user_settings = user_settings;
			});
	}

	prepare_columns(columns) {
		return columns.map(column => {
			if (typeof column === 'string') {
				if (column.includes(':')) {
					let [label, fieldtype, width] = column.split(':');
					let options;

					if (fieldtype.includes('/')) {
						[fieldtype, options] = fieldtype.split('/');
					}

					column = {
						label,
						fieldname: label,
						fieldtype,
						width,
						options
					};
				} else {
					column = {
						label: column,
						fieldname: column,
						fieldtype: 'Data'
					};
				}
			}

			const format_cell = (value, row, column, data) => {
				if (column.isHeader && !data && this.data) {
					// totalRow doesn't have a data object
					// proxy it using the first data object
					// this is needed only for currency formatting
					data = this.data[0];
				}
				return frappe.format(value, column,
					{for_print: false, always_show_decimals: true}, data);
			};

			let compareFn = null;
			if (column.fieldtype === 'Date') {
				compareFn = (cell, keyword) => {
					if (!cell.content) return null;
					if (keyword.length !== 'YYYY-MM-DD'.length) return null;

					const keywordValue = frappe.datetime.user_to_obj(keyword);
					const cellValue = frappe.datetime.str_to_obj(cell.content);
					return [+cellValue, +keywordValue];
				};
			}

			return Object.assign(column, {
				id: column.fieldname,
				name: __(column.label),
				width: parseInt(column.width) || null,
				editable: false,
				compareValue: compareFn,
				format: (value, row, column, data) => {
					if (this.report_settings.formatter) {
						return this.report_settings.formatter(value, row, column, data, format_cell);
					}
					return format_cell(value, row, column, data);
				}
			});
		});
	}

	prepare_data(data) {
		return data.map(row => {
			let row_obj = {};
			if (Array.isArray(row)) {
				this.columns.forEach((column, i) => {
					row_obj[column.id] = row[i];
				});

				return row_obj;
			}
			return row;
		});
	}

	get_visible_columns() {
		const visible_column_ids = this.datatable.datamanager.getColumns(true).map(col => col.id);

		return visible_column_ids
			.map(id => this.columns.find(col => col.id === id))
			.filter(Boolean);
	}

	get_filter_values(raise) {
		const mandatory = this.filters.filter(f => f.df.reqd);
		const missing_mandatory = mandatory.filter(f => !f.get_value());
		if (raise && missing_mandatory.length > 0) {
			let message = __('Please set filters');
			this.toggle_message(raise, message);
			throw "Filter missing";
		}

		const filters = this.filters
			.filter(f => f.get_value())
			.map(f => {
				var v = f.get_value();
				// hidden fields dont have $input
				if(f.df.hidden) v = f.value;
				if(v === '%') v = null;
				return {
					[f.df.fieldname]: v
				};
			})
			.reduce((acc, f) => {
				Object.assign(acc, f);
				return acc;
			}, {});
		return filters;
	}

	get_filter(fieldname) {
		const field = (this.filters || []).find(f => f.df.fieldname === fieldname);
		if (!field) {
			console.warn(`[Query Report] Invalid filter: ${fieldname}`);
		}
		return field;
	}

	get_filter_value(fieldname) {
		const field = this.get_filter(fieldname);
		return field ? field.get_value() : null;
	}

	set_filter_value(fieldname, value) {
		let field_value_map = {};
		if (typeof fieldname === 'string') {
			field_value_map[fieldname] = value;
		} else {
			field_value_map = fieldname;
		}

		this._no_refresh = true;
		Object.keys(field_value_map)
			.forEach((fieldname, i, arr) => {
				const value = field_value_map[fieldname];

				if (i === arr.length - 1) {
					this._no_refresh = false;
				}

				this.get_filter(fieldname).set_value(value);
			});
	}

	set_breadcrumbs() {
		if (!this.report_doc || !this.report_doc.ref_doctype) return;
		const ref_doctype = frappe.get_meta(this.report_doc.ref_doctype);
		frappe.breadcrumbs.add(ref_doctype.module);
	}

	make_access_log (method, file_format) {
		frappe.call("frappe.core.doctype.access_log.access_log.make_access_log",
			{
				doctype: this.doctype || '',
				report_name: this.report_name,
				filters: this.get_filter_values(),
				file_type: file_format,
				method: method
			});
	}

	print_report(print_settings) {
		const custom_format = this.report_settings.html_format || null;
		const filters_html = this.get_filters_html_for_print();
		const landscape = print_settings.orientation == 'Landscape';

		this.make_access_log('Print', 'PDF');
		frappe.render_grid({
			template: print_settings.columns ? 'print_grid' : custom_format,
			title: __(this.report_name),
			subtitle: filters_html,
			print_settings: print_settings,
			landscape: landscape,
			filters: this.get_filter_values(),
			data: this.get_data_for_print(),
			columns: this.get_columns_for_print(print_settings, custom_format),
			original_data: this.data,
			report: this
		});
	}

	pdf_report(print_settings) {
		const base_url = frappe.urllib.get_base_url();
		const print_css = frappe.boot.print_css;
		const landscape = print_settings.orientation == 'Landscape';

		const custom_format = this.report_settings.html_format || null;
		const columns = this.get_columns_for_print(print_settings, custom_format);
		const data = this.get_data_for_print();
		const applied_filters = this.get_filter_values();

		const filters_html = this.get_filters_html_for_print();
		const template =
			print_settings.columns || !custom_format ? 'print_grid' : custom_format;
		const content = frappe.render_template(template, {
			title: __(this.report_name),
			subtitle: filters_html,
			filters: applied_filters,
			data: data,
			original_data: this.data,
			columns: columns,
			report: this
		});

		// Render Report in HTML
		const html = frappe.render_template('print_template', {
			title: __(this.report_name),
			content: content,
			base_url: base_url,
			print_css: print_css,
			print_settings: print_settings,
			landscape: landscape,
			columns: columns
		});

		frappe.render_pdf(html, print_settings);
	}

	get_filters_html_for_print() {
		const applied_filters = this.get_filter_values();
		return Object.keys(applied_filters)
			.map(fieldname => {
				const label = frappe.query_report.get_filter(fieldname).df.label;
				const value = applied_filters[fieldname];
				return `<h6>${__(label)}: ${value}</h6>`;
			})
			.join('');
	}

	export_report() {
		if (this.export_dialog) {
			this.export_dialog.clear();
			this.export_dialog.show();
			return;
		}

		this.export_dialog = frappe.prompt([
			{
				label: __('Select File Format'),
				fieldname: 'file_format',
				fieldtype: 'Select',
				options: ['Excel', 'CSV'],
				default: 'Excel',
				reqd: 1
			},
			{
				label: __("Include indentation"),
				fieldname: "include_indentation",
				fieldtype: "Check",
			}
		], ({ file_format, include_indentation }) => {
			this.make_access_log('Export', file_format);
			if (file_format === 'CSV') {
				const column_row = this.columns.reduce((acc, col) => {
					if (!col.hidden) {
						acc.push(col.label);
					}
					return acc;
				}, []);
				const data = this.get_data_for_csv(include_indentation);
				const out = [column_row].concat(data);

				frappe.tools.downloadify(out, null, this.report_name);
			} else {
				let filters = this.get_filter_values(true);
				if (frappe.urllib.get_dict("prepared_report_name")) {
					filters = Object.assign(frappe.urllib.get_dict("prepared_report_name"), filters);
				}

				const visible_idx = this.datatable.bodyRenderer.visibleRowIndices;
				if (visible_idx.length + 1 === this.data.length) {
					visible_idx.push(visible_idx.length);
				}

				const args = {
					cmd: 'frappe.desk.query_report.export_query',
					report_name: this.report_name,
					custom_columns: this.custom_columns.length? this.custom_columns: [],
					file_format_type: file_format,
					filters: filters,
					visible_idx,
					include_indentation,
				};

				open_url_post(frappe.request.url, args);
			}
		}, __('Export Report: '+ this.report_name), __('Download'));
	}

	get_data_for_csv(include_indentation) {
		const rows = this.datatable.bodyRenderer.visibleRows;
		if (this.raw_data.add_total_row) {
			rows.push(this.datatable.bodyRenderer.getTotalRow());
		}
		return rows.map(row => {
			const standard_column_count = this.datatable.datamanager.getStandardColumnCount();
			return row
				.slice(standard_column_count)
				.map((cell, i) => {
					if (include_indentation && i===0) {
						cell.content = '   '.repeat(row.meta.indent) + (cell.content || '');
					}
					return cell.content || '';
				});
		});
	}

	get_data_for_print() {
		if (!this.data.length) {
			return [];
		}

		const rows = this.datatable.datamanager.rowViewOrder.map(index => {
			if (this.datatable.bodyRenderer.visibleRowIndices.includes(index)) {
				return this.data[index];
			}
		}).filter(Boolean);

		if (this.raw_data.add_total_row) {
			let totalRow = this.datatable.bodyRenderer.getTotalRow().reduce((row, cell) => {
				row[cell.column.id] = cell.content;
				row.is_total_row = true;
				return row;
			}, {});

			rows.push(totalRow);
		}
		return rows;
	}

	get_columns_for_print(print_settings, custom_format) {
		let columns = [];

		if (print_settings && print_settings.columns) {
			columns = this.get_visible_columns().filter(column =>
				print_settings.columns.includes(column.fieldname)
			);
		} else {
			columns = custom_format ? this.columns : this.get_visible_columns();
		}

		return columns;
	}

	get_menu_items() {
		return [
			{
				label: __('Refresh'),
				action: () => this.refresh(),
				class: 'visible-xs'
			},
			{
				label: __('Edit'),
				action: () => frappe.set_route('Form', 'Report', this.report_name),
				condition: () => frappe.user.is_report_manager(),
				standard: true
			},
			{
				label: __('Print'),
				action: () => {
					let dialog = frappe.ui.get_print_settings(
						false,
						print_settings => this.print_report(print_settings),
						this.report_doc.letter_head,
						this.get_visible_columns()
					);
					this.add_portrait_warning(dialog);
				},
				condition: () => frappe.model.can_print(this.report_doc.ref_doctype),
				standard: true
			},
			{
				label: __('PDF'),
				action: () => {
					let dialog = frappe.ui.get_print_settings(
						false,
						print_settings => this.pdf_report(print_settings),
						this.report_doc.letter_head,
						this.get_visible_columns()
					);

					this.add_portrait_warning(dialog);
				},
				condition: () => frappe.model.can_print(this.report_doc.ref_doctype),
				standard: true
			},
			{
				label: __('Export'),
				action: () => this.export_report(),
				condition: () => frappe.model.can_export(this.report_doc.ref_doctype),
				standard: true
			},
			{
				label: __('Setup Auto Email'),
				action: () => frappe.set_route('List', 'Auto Email Report', {'report' : this.report_name}),
				standard: true
			},
			{
				label: __('Add Column'),
				action: () => {
					let d = new frappe.ui.Dialog({
						title: __('Add Column'),
						fields: [
							{
								fieldtype: 'Select',
								fieldname: 'doctype',
								label: __('From Document Type'),
								options: this.linked_doctypes.map(df => ({ label: df.doctype, value: df.doctype })),
								change: () => {
									let doctype = d.get_value('doctype');
									frappe.model.with_doctype(doctype, () => {
										let options = frappe.meta.get_docfields(doctype)
											.filter(frappe.model.is_value_type)
											.map(df => ({ label: df.label, value: df.fieldname }));

										d.set_df_property('field', 'options', options.sort(function(a, b) {
											if (a.label < b.label) {
												return -1;
											}
											if (a.label > b.label) {
												return 1;
											}
											return 0;
										})
										);
									});
								}
							},
							{
								fieldtype: 'Select',
								label: __('Field'),
								fieldname: 'field',
								options: []
							},
							{
								fieldtype: 'Select',
								label: __('Insert After'),
								fieldname: 'insert_after',
								options: this.columns.map(df => df.label)
							}
						],
						primary_action: (values) => {
							const custom_columns = [];
							let df = frappe.meta.get_docfield(values.doctype, values.field);
							const insert_after_index = this.columns
								.findIndex(column => column.label === values.insert_after);
							custom_columns.push({
								fieldname: df.fieldname,
								fieldtype: df.fieldtype,
								label: df.label,
								insert_after_index: insert_after_index,
								link_field: this.doctype_field_map[values.doctype],
								doctype: values.doctype,
								options: df.fieldtype === "Link" ? df.options : undefined,
								width: 100
							});

							this.custom_columns = this.custom_columns.concat(custom_columns);
							frappe.call({
								method: 'frappe.desk.query_report.get_data_for_custom_field',
								args: {
									field: values.field,
									doctype: values.doctype
								},
								callback: (r) => {
									const custom_data = r.message;
									const link_field = this.doctype_field_map[values.doctype];

									this.add_custom_column(custom_columns, custom_data, link_field, values.field, insert_after_index);
									d.hide();
								}
							});
							this.set_menu_items();
						}
					})

					d.show();
				},
				standard: true
			},
			{
				label: __('Save'),
				action: () => {
					let d = new frappe.ui.Dialog({
						title: __('Save Report'),
						fields: [
							{
								fieldtype: 'Data',
								fieldname: 'report_name',
								label: __("Report Name"),
								default: this.report_doc.is_standard == 'No' ? this.report_name : "",
							}
						],
						primary_action: (values) => {
							frappe.call({
								method: "frappe.desk.query_report.save_report",
								args: {
									reference_report: this.report_name,
									report_name: values.report_name,
									columns: this.get_visible_columns()
								},
								callback: function(r) {
									this.show_save = false;
									d.hide();
									frappe.set_route('query-report', r.message);
								}
							});
						}
					});
					d.show();
				},
				standard: true
			},
			{
				label: __('User Permissions'),
				action: () => frappe.set_route('List', 'User Permission', {
					doctype: 'Report',
					name: this.report_name
				}),
				condition: () => frappe.model.can_set_user_permissions('Report'),
				standard: true
			}
		];
	}

	add_portrait_warning(dialog) {
		if (this.columns.length > 10) {
			dialog.set_df_property('orientation', 'change', () => {
				let value = dialog.get_value('orientation');
				let description = value === 'Portrait'
					? __('Report with more than 10 columns looks better in Landscape mode.')
					: '';
				dialog.set_df_property('orientation', 'description', description);
			});
		}
	}

	add_custom_column(custom_column, custom_data, link_field, column_field, insert_after_index) {
		const column = this.prepare_columns(custom_column);

		this.columns.splice(insert_after_index + 1, 0, column[0]);

		this.data.forEach(row => {
			row[column_field] = custom_data[row[link_field]];
		});

		this.render_datatable();
	}

	get_linked_doctypes() {
		let doctypes = [];
		let dynamic_links = [];
		let dynamic_doctypes = new Set();
		this.doctype_field_map = {};

		this.columns.forEach(df => {
			if (df.fieldtype == "Link" && df.options && df.options != "Currency") {
				doctypes.push({
					doctype: df.options,
					fieldname: df.fieldname
				});
			}
			else if (df.fieldtype == "Dynamic Link" && df.options) {
				dynamic_links.push({
					link_name: df.options,
					fieldname: df.fieldname
				});
			}
		});

		this.data.forEach(row => {
			dynamic_links.forEach(field => {
				if (row[field.link_name]){
					dynamic_doctypes.add(row[field.link_name] + ":" + field.fieldname);
				}
			});
		});

		doctypes = doctypes.concat(Array.from(dynamic_doctypes).map(d => {
			const doc_field_pair = d.split(":");
			return {
				doctype: doc_field_pair[0],
				fieldname: doc_field_pair[1]
			};
		}));

		doctypes.forEach(doc => {
			this.doctype_field_map[doc.doctype] = doc.fieldname;
		});

		return doctypes;
	}

	setup_report_wrapper() {
		if (this.$report) return;

		let page_form = this.page.main.find('.page-form');
		this.$status = $(`<div class="form-message text-muted small"></div>`)
			.hide().insertAfter(page_form);

		this.$chart = $('<div class="chart-wrapper">').hide().appendTo(this.page.main);
		this.$report = $('<div class="report-wrapper">').appendTo(this.page.main);
		this.$message = $(this.message_div('')).hide().appendTo(this.page.main);
	}

	show_status(status_message) {
		this.$status.html(status_message).show();
	}

	hide_status() {
		this.$status.hide();
	}

	show_footer_message() {
		const message = __('For comparison, use >5, <10 or =324. For ranges, use 5:10 (for values between 5 & 10).');
		const execution_time_msg = __('Execution Time: {0} sec', [this.execution_time || 0.1]);

		this.page.footer.removeClass('hide').addClass('text-muted col-md-12').html(`
			<span class="text-left col-md-6">${message}</span><span class="text-right col-md-6">${execution_time_msg}</span>
		`);

		this.page.wrapper.find('.tree-footer').remove();
		if (this.tree_report) {
			this.$tree_footer = this.page.footer.clone().addClass('tree-footer');
			this.$tree_footer.html(`<div class="col-md-12">
				<button class="btn btn-xs btn-default" data-action="expand_all_rows">
					${__('Expand All')}</button>
				<button class="btn btn-xs btn-default" data-action="collapse_all_rows">
					${__('Collapse All')}</button>
			</div>`);
			this.page.footer.before(this.$tree_footer);
			this.$tree_footer.find('[data-action=collapse_all_rows]').show();
			this.$tree_footer.find('[data-action=expand_all_rows]').hide();
		}
	}

	expand_all_rows() {
		this.$tree_footer.find('[data-action=expand_all_rows]').hide();
		this.datatable.rowmanager.expandAllNodes();
		this.$tree_footer.find('[data-action=collapse_all_rows]').show();
	}

	collapse_all_rows() {
		this.$tree_footer.find('[data-action=collapse_all_rows]').hide();
		this.datatable.rowmanager.collapseAllNodes();
		this.$tree_footer.find('[data-action=expand_all_rows]').show();
	}

	message_div(message) {
		return `<div class='flex justify-center align-center text-muted' style='height: 50vh;'>
			<div>${message}</div>
		</div>`;
	}

	reset_report_view() {
		this.hide_status();
		this.toggle_nothing_to_show(true);
		this.refresh();
	}

	toggle_loading(flag) {
		this.toggle_message(flag, __('Loading') + '...');
	}


	toggle_nothing_to_show(flag) {
		let message = this.prepared_report
			? __('This is a background report. Please set the appropriate filters and then generate a new one.')
			: __('Nothing to show')

		this.toggle_message(flag, message);

		if (flag && this.prepared_report) {
			this.prepared_report_action = "New";
			this.add_prepared_report_buttons();
		}
	}

	toggle_message(flag, message) {
		if (flag) {
			this.$message.find('div').html(message);
			this.$message.show();
		} else {
			this.$message.hide();
		}
		this.$report.toggle(!flag);
		this.$chart.toggle(!flag);
	}
	// backward compatibility
	get get_values() {
		return this.get_filter_values;
	}
};

Object.defineProperty(frappe, 'query_report_filters_by_name', {
	get() {
		console.warn('[Query Report] frappe.query_report_filters_by_name is deprecated. Please use the new api: frappe.query_report.get_filter_value(fieldname) and frappe.query_report.set_filter_value(fieldname, value)');
		return null;
	}
});
