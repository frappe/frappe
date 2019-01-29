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
			action: () => this.refresh()
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
	}

	load() {
		if (frappe.get_route().length < 2) {
			this.toggle_nothing_to_show(true);
			return;
		}
		if (this.report_name !== frappe.get_route()[1]) {
			this.toggle_loading(true);
			// different report
			this.load_report();
		} else {
			// same report
			this.refresh_report();
		}
	}

	load_report() {
		this.page.clear_inner_toolbar();
		this.route = frappe.get_route();
		this.page_name = frappe.get_route_str();
		this.report_name = this.route[1];
		this.page_title = __(this.report_name);
		this.menu_items = this.get_menu_items();
		this.datatable = null;
		this.prepared_report_action = "New";

		frappe.run_serially([
			() => this.get_report_doc(),
			() => this.get_report_settings(),
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
		if (frappe.query_reports[this.report_name]) {
			this.report_settings = frappe.query_reports[this.report_name];
			return this._load_script;
		}

		this._load_script = (new Promise(resolve => frappe.call({
			method: 'frappe.desk.query_report.get_script',
			args: { report_name: this.report_name },
			callback: resolve
		}))).then(r => {
			frappe.dom.eval(r.message.script || '');
			return r;
		}).then(r => {
			return frappe.after_ajax(() => {
				this.report_settings = frappe.query_reports[this.report_name];
				this.report_settings.html_format = r.message.html_format;
			});
		});

		return this._load_script;
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
				if (this.previous_filters
					&& (JSON.stringify(this.previous_filters) == JSON.stringify(this.get_filter_values()))) {
					// filter values have not changed
					return;
				}
				this.previous_filters = this.get_filter_values();

				// clear previous_filters after 3 seconds, to allow refresh for new data
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
					return f.set_value(value);
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
		let query = frappe.utils.get_query_string(frappe.get_route_str());

		if(query) {
			let obj = frappe.utils.get_query_params(query);
			filters = Object.assign(filters || {}, obj);
		}

		// only one refresh at a time
		if (this.last_ajax) {
			this.last_ajax.abort();
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
			})
		}).then(r => {
			let data = r.message;

			this.hide_status();

			if (data.prepared_report) {
				this.prepared_report = true;
				const query_string = frappe.utils.get_query_string(frappe.get_route_str());
				const query_params = frappe.utils.get_query_params(query_string);
				// If query_string contains prepared_report_name then set filters
				// to match the mentioned prepared report doc and disable editing
				if(query_params.prepared_report_name) {
					this.prepared_report_action = "Edit";
					const filters_from_report = JSON.parse(data.doc.filters);
					Object.values(this.filters).forEach(function(field) {
						if (filters_from_report[field.fieldname]) {
							field.set_input(filters_from_report[field.fieldname]);
						}
						field.input.disabled = true;
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

				this.render_datatable();
			} else {
				this.toggle_nothing_to_show(true);
			}
		});
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
		this.data = this.prepare_data(data.result);

		this.tree_report = this.data.some(d => 'indent' in d);
	}

	render_datatable() {
		let data = this.data;
		if (this.raw_data.add_total_row) {
			data = data.slice();
			data.splice(-1, 1);
		}

		if (this.datatable) {
			this.datatable.options.treeView = this.tree_report;
			this.datatable.refresh(data, this.columns);
		} else {
			let datatable_options = {
				columns: this.columns,
				data: data,
				inlineFilters: true,
				treeView: this.tree_report,
				layout: 'fixed',
				cellHeight: 33,
				showTotalRow: this.raw_data.add_total_row,
				hooks: {
					totalAccumulator: frappe.utils.report_total_accumulator
				}
			};

			if (this.report_settings.get_datatable_options) {
				datatable_options = this.report_settings.get_datatable_options(datatable_options);
			}
			this.datatable = new DataTable(this.$report[0], datatable_options);
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

		return options;
	}

	render_chart(options, height=200) {
		Object.assign(options, {
			height: height
		});

		this.$chart.empty();
		this.chart = new Chart(this.$chart[0], options);
		this.$chart.show();
	}

	get_possible_chart_options() {
		const columns = this.raw_data.columns;
		const rows =  this.raw_data.result;
		const first_row = rows[0];
		const has_total_row = this.raw_data.add_total_row;

		const indices = first_row.reduce((accumulator, current_value, current_index) => {
			if(!isNaN(Number(current_value))) {
				accumulator.push(current_index);
			}
			return accumulator;
		}, []);

		function get_column_values(column_name) {
			const column_index = columns.indexOf(column_name);
			return rows.map(row => row[column_index]);
		}

		function get_chart_options({ y_field, x_field, chart_type, color }) {
			const type = chart_type.toLowerCase();
			const colors = color ? [color] : undefined;

			let labels = get_column_values(x_field)
				.filter(Boolean)
				.map(d => d.trim())
				.filter(Boolean);

			let dataset_values = get_column_values(y_field).map(d => Number(d));

			if(has_total_row) {
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
				type: type,
				colors: colors
			};
		}

		function preview_chart() {
			const wrapper = $(dialog.fields_dict["chart_preview"].wrapper);
			const values = dialog.get_values(true);
			let options = get_chart_options(values);

			Object.assign(options, {
				height: 150
			});

			wrapper.empty();
			new Chart(wrapper[0], options);
			wrapper.find('.chart-container .title, .chart-container .sub-title').hide();
			wrapper.show();
		}

		const numeric_fields = columns.filter((col, i) => indices.includes(i));
		const non_numeric_fields = columns.filter((col, i) => !indices.includes(i))

		const dialog = new frappe.ui.Dialog({
			title: __('Make Chart'),
			fields: [
				{
					fieldname: 'y_field',
					label: 'Y Field',
					fieldtype: 'Select',
					options: numeric_fields,
					default: numeric_fields[0],
					onchange: preview_chart
				},
				{
					fieldname: 'x_field',
					label: 'X Field',
					fieldtype: 'Select',
					options: non_numeric_fields,
					default: non_numeric_fields[0],
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
					options: ['Bar', 'Line', 'Percentage', 'Pie'],
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
			primary_action_label: __('Make'),
			primary_action: (values) => {
				let options = get_chart_options(values);

				options.title = __(`${this.report_name}: ${values.y_field} vs ${values.x_field}`);

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
				return frappe.format(value == null ? '' : value, column,
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
				name: column.label,
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

	print_report(print_settings) {
		const custom_format = this.report_settings.html_format || null;
		const filters_html = this.get_filters_html_for_print();
		const landscape = print_settings.orientation == 'Landscape';

		frappe.render_grid({
			template: custom_format,
			title: __(this.report_name),
			subtitle: filters_html,
			print_settings: print_settings,
			landscape: landscape,
			filters: this.get_filter_values(),
			data: custom_format ? this.data : this.get_data_for_print(),
			columns: custom_format ? this.columns : this.get_columns_for_print(),
			report: this
		});
	}

	pdf_report(print_settings) {
		const base_url = frappe.urllib.get_base_url();
		const print_css = frappe.boot.print_css;
		const landscape = print_settings.orientation == 'Landscape';

		const custom_format = this.report_settings.html_format || null;
		const columns = custom_format ? this.columns : this.get_columns_for_print();
		const data = custom_format ? this.data : this.get_data_for_print();
		const applied_filters = this.get_filter_values();

		const filters_html = this.get_filters_html_for_print();
		const content = frappe.render_template(custom_format || 'print_grid', {
			title: __(this.report_name),
			subtitle: filters_html,
			filters: applied_filters,
			data: data,
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
				reqd: 1,
				onchange: () => {
					this.export_dialog.set_df_property('with_indentation',
						'hidden', this.export_dialog.get_value('file_format') !== 'CSV');
				}
			},
			{
				label: __('With Group Indentation'),
				fieldname: 'with_indentation',
				fieldtype: 'Check',
				hidden: 1
			}
		], ({ file_format, with_indentation }) => {
			if (file_format === 'CSV') {
				const column_row = this.columns.map(col => col.label);
				const data = this.get_data_for_csv(with_indentation);
				const out = [column_row].concat(data);

				frappe.tools.downloadify(out, null, this.report_name);
			} else {
				let filters = this.get_filter_values(true);
				if (frappe.urllib.get_dict("prepared_report_name")) {
					filters = Object.assign(frappe.urllib.get_dict("prepared_report_name"), filters);
				}

				const visible_idx = this.datatable.datamanager.getFilteredRowIndices();
				if (visible_idx.length + 1 === this.data.length) {
					visible_idx.push(visible_idx.length);
				}

				const args = {
					cmd: 'frappe.desk.query_report.export_query',
					report_name: this.report_name,
					file_format_type: file_format,
					filters: filters,
					visible_idx: visible_idx,
				};

				open_url_post(frappe.request.url, args);
			}
		}, __('Export Report: '+ this.report_name), __('Download'));
	}

	get_data_for_csv(with_indentation = false) {

		const indices = this.datatable.datamanager.getFilteredRowIndices();
		const rows = indices.map(i => this.datatable.datamanager.getRow(i));
		return rows.map(row => {
			const standard_column_count = this.datatable.datamanager.getStandardColumnCount();
			return row
				.slice(standard_column_count)
				.map((cell, i) => {
				if (with_indentation && i === 0) {
					return '   '.repeat(row.meta.indent) + cell.content;
				}
				return cell.content;
			});
		});
	}

	get_data_for_print() {
		const indices = this.datatable.datamanager.getFilteredRowIndices();
		return indices.map(i => this.data[i]);
	}

	get_columns_for_print() {
		return this.get_visible_columns();
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
					frappe.ui.get_print_settings(
						false,
						print_settings => this.print_report(print_settings),
						this.report_doc.letter_head
					);
				},
				condition: () => frappe.model.can_print(this.report_doc.ref_doctype),
				standard: true
			},
			{
				label: __('PDF'),
				action: () => {
					frappe.ui.get_print_settings(
						false,
						print_settings => this.pdf_report(print_settings),
						this.report_doc.letter_head
					);
				},
				condition: () => frappe.model.can_print(this.report_doc.ref_doctype),
				standard: true
			},
			{
				label: __('Export'),
				action: () => this.export_report(),
				standard: true
			},
			{
				label: __('Setup Auto Email'),
				action: () => frappe.set_route('List', 'Auto Email Report', {'report' : this.report_name}),
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
			},
			{
				label: __('Add to Desktop'),
				action: () => frappe.add_to_desktop(this.report_name, null, this.report_name),
				standard: true
			},
		];
	}

	setup_report_wrapper() {
		if (this.$report) return;

		let page_form = this.page.main.find('.page-form');
		this.$status = $(`<div class="form-message text-muted small"></div>`)
			.hide().insertAfter(page_form);

		this.show_tip();
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

	show_tip() {
		const message = __('For comparison, use >5, <10 or =324. For ranges, use 5:10 (for values between 5 & 10).');
		this.page.footer.removeClass('hide').addClass('text-muted text-center').html(`<p>${message}</p>`);
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
