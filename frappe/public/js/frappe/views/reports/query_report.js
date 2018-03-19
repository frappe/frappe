// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import DataTable from 'frappe-datatable';

frappe.provide("frappe.views");
frappe.provide("frappe.query_reports");

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
			this.setup_report_wrapper
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
		this.route = frappe.get_route();
		this.page_name = frappe.get_route_str();
		this.report_name = this.route[1];
		this.page_title = __(this.report_name);
		this.menu_items = this.get_menu_items();
		this.datatable = null;

		frappe.run_serially([
			() => this.get_report_doc(),
			() => this.get_report_settings(),
			() => this.report_settings.onload && this.report_settings.onload(this),
			() => this.setup_page_head(),
			() => this.refresh_report()
		]);
	}

	refresh_report() {
		this.toggle_message(true);

		return frappe.run_serially([
			() => this.setup_filters(),
			() => this.set_route_filters(),
			() => this.get_user_settings(),
			() => this.refresh(),
			() => this.save_user_settings()
		]);
	}

	get_report_doc() {
		return frappe.model.with_doc('Report', this.report_name)
			.then(doc => {
				this.report_doc = doc;
			})
			.then(() => frappe.model.with_doc('DocType', this.report_doc.ref_doctype));
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

			const f = this.page.add_field(df);

			if (df.default) {
				f.set_input(df.default);
			}

			if (df.get_query) f.get_query = df.get_query;
			if (df.on_change) f.on_change = df.on_change;
			df.onchange = () => {
				if (f.on_change) {
					f.on_change(this);
				} else {
					this.refresh();
				}
			};

			return f;
		}).filter(Boolean);

		if (this.filters.length === 0) {
			// hide page form if no filters
			this.page.hide_form();
		} else {
			this.page.show_form();
		}

		// set the field 'query_report_filters_by_name' first
		// as they can be used in
		// setting/triggering the filters
		this.set_filters_by_name();
	}

	set_filters_by_name() {
		frappe.query_report_filters_by_name = {};
		for (var i in this.filters) {
			frappe.query_report_filters_by_name[this.filters[i].df.fieldname] = this.filters[i];
		}
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
		const filters = this.get_filter_values(true);
		return new Promise(resolve => frappe.call({
			method: "frappe.desk.query_report.run",
			type: "GET",
			args: {
				report_name: this.report_name,
				filters: filters
			},
			callback: resolve
		})).then(r => {
			const data = r.message;

			this.toggle_message(false);

			if (data.result && data.result.length) {
				this.render_chart(data);
				this.render_report(data);
			} else {
				this.toggle_nothing_to_show(true);
			}
		});
	}

	render_report(data) {
		this._data = data.result;
		this._columns = this.prepare_columns(data.columns);
		this.is_tree_report = this._data.some(d => 'indent' in d);

		const columns = this.get_columns_for_datatable();

		if (this.datatable) {
			this.datatable.refresh(this._data, columns);
			return;
		}

		this.datatable = new DataTable(this.$report[0], {
			columns: columns,
			data: this._data,
			inlineFilters: true,
			treeView: this.is_tree_report,
			layout: 'fixed',
			events: {
				onRemoveColumn: () => this.save_user_settings(),
				onSwitchColumn: () => this.save_user_settings()
			}
		});
	}

	render_chart(data) {
		this.$chart.empty();
		let opts = this.report_settings.get_chart_data
			? this.report_settings.get_chart_data(data.columns, data.result)
			: data.chart
				? data.chart
				: {};
		if (!(opts.data && opts.data.labels && opts.data.labels.length > 0)) return;

		Object.assign(opts, {
			height: 200
		});

		this.$chart.show();
		this.chart = new Chart(this.$chart[0], opts);
	}

	get_user_settings() {
		return frappe.model.user_settings.get(this.report_name)
			.then(user_settings => {
				this.user_settings = user_settings;
			});
	}

	save_user_settings(clear_settings = false) {
		if (clear_settings) {
			return frappe.model.user_settings.remove(this.report_name, 'column_order');
		}
		if (!this.datatable) return;
		const column_order = this.datatable.datamanager.getColumns(true).map(col => col.id);
		return frappe.model.user_settings.save(this.report_name, 'column_order', column_order);
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

					return {
						label,
						fieldname: label,
						fieldtype,
						width,
						options
					};
				}

				return {
					label: column,
					fieldname: column,
					fieldtype: 'Data'
				};
			}

			return column;
		});
	}

	get_columns_for_datatable() {
		const columns = this._columns.map(df => {
			return {
				id: df.fieldname,
				name: df.label,
				width: df.width || null,
				editable: false,
				format: (value, row, column, data) =>
					frappe.format(value || '', df,
						{for_print: false, always_show_decimals: true}, data)
			};
		});

		return columns;

		// if (this.user_settings.column_order && this.user_settings.column_order.length > 0) {
		// 	return this.user_settings.column_order
		// 		.map(id => columns.find(col => col.id === id))
		// 		.filter(Boolean);
		// } else {
		// 	return columns;
		// }
	}

	get_filter_values(raise) {
		const mandatory = this.filters.filter(f => f.df.reqd);
		const missing_mandatory = mandatory.filter(f => !f.get_value());

		if (raise && missing_mandatory.length > 0) {
			// this.chart_area.hide();
			// this.wrapper.find(".waiting-area").empty().toggle(false);
			// this.$no_result.html(__("Please set filters")).show();
			if (raise) {
				frappe.throw(__('Filter missing: {0}', [missing_mandatory.map(f => f.df.label).join(', ')]));
			}
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

	set_breadcrumbs() {
		if (!this.report_doc || !this.report_doc.ref_doctype) return;
		const ref_doctype = frappe.get_meta(this.report_doc.ref_doctype);
		frappe.breadcrumbs.add(ref_doctype.module);
	}

	print_report(print_settings) {
		const columns = this.get_columns_for_print();
		frappe.render_grid({
			template: this.report_settings.html_format || null,
			title: __(this.report_name),
			print_settings: print_settings,
			filters: this.get_filter_values(),
			data: this.get_data_for_print(),
			columns: columns,
			report: this
		});
	}

	pdf_report(print_settings) {
		const base_url = frappe.urllib.get_base_url();
		const print_css = frappe.boot.print_css;
		const landscape = print_settings.orientation == "Landscape";
		const columns = this.columns;

		let html;
		if (this.report_settings.html_format) {
			const content = frappe.render(this.report_settings.html_format, {
				data: this.get_data_for_print(),
				filters: this.get_filter_values(),
				report: this,
			});

			//Render Report in HTML
			html = frappe.render_template("print_template", {
				title:__(this.report_name),
				content: content,
				base_url: base_url,
				print_css: print_css,
				print_settings: print_settings,
				landscape: landscape,
				columns: columns
			});
		} else {
			const content = frappe.render_template("print_grid", {
				title: __(this.report_name),
				data: this.get_data_for_print(),
				columns: columns
			});

			//Render Report in HTML
			html = frappe.render_template("print_template", {
				content: content,
				title: __(this.report_name),
				base_url: base_url,
				print_css: print_css,
				print_settings: print_settings,
				landscape: landscape,
				columns: columns
			});
		}

		frappe.render_pdf(html, print_settings);
	}

	export_report() {
		if (this.export_dialog) {
			this.export_dialog.clear();
			this.export_dialog.show();
			return;
		}

		this.export_dialog = frappe.prompt({
			label: __('Select File Format'),
			fieldname: 'file_format',
			fieldtype: 'Select',
			options: ['Excel', 'CSV'],
			default: 'Excel',
			reqd: 1
		}, ({ file_format }) => {
			if (file_format === 'CSV') {
				const column_row = this._columns.map(col => col.label);
				const data = this.get_data_for_print();
				const out = [column_row].concat(data);

				frappe.tools.downloadify(out, null, this.report_name);
			} else {
				const filters = this.get_filter_values(true);

				const args = {
					cmd: 'frappe.desk.query_report.export_query',
					report_name: this.report_name,
					file_format_type: file_format,
					filters: filters,
					visible_idx: this.datatable.datamanager.getFilteredRowIndices(),
				};

				open_url_post(frappe.request.url, args);
			}
		}, __("Export Report: "+ this.report_name), __("Download"));
	}

	get_data_for_print() {
		const indices = this.datatable.datamanager.getFilteredRowIndices();
		const out = indices.map(i => this.datatable.datamanager.getRow(i).map(c => c.content));
		return out.map(row => row.slice(1));
	}

	get_columns_for_print() {
		return this._columns || [];
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
				action: () => frappe.set_route("Form", "Report", this.report_name),
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
					doctype: "Report",
					name: this.report_name
				}),
				condition: () => frappe.model.can_set_user_permissions('Report'),
				standard: true
			},
			{
				label: __('Clear User Settings'),
				action: () => this.save_user_settings(true).then(() => this.refresh_report()),
				standard: true
			},
			{
				label: __('Add to Desktop'),
				action: () => frappe.add_to_desktop(this.report_name, null, this.report_name),
				standard: true
			},
		];
	}

	setup_page_head() {
		super.setup_page_head();
		this.page.set_title_sub(`<label class="label label-warning text-color">${__('Beta')}</label>`);
	}

	setup_report_wrapper() {
		if (this.$report) return;
		this.$chart = $('<div class="chart-wrapper">').hide().appendTo(this.page.main);
		this.$report = $('<div class="report-wrapper">').appendTo(this.page.main);
		this.$message = $(this.message_div('')).hide().appendTo(this.page.main);
	}

	message_div(message) {
		return `<div class="flex justify-center align-center text-muted" style="height: 50vh;">
			<div>${message}</div>
		</div>`;
	}

	toggle_loading(flag) {
		this.toggle_message(flag, __('Loading') + '...');
	}

	toggle_nothing_to_show(flag) {
		this.toggle_message(flag, __('Nothing to show'));
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

	get data() {
		return this._data;
	}

	get columns() {
		return this._columns;
	}
};