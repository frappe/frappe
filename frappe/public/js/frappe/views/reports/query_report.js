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
		frappe.query_report.init();
	});
};

frappe.views.QueryReport = class QueryReport extends frappe.views.BaseList {
	show() {

	}

	init() {
		console.log('init')
		if (this.init_promise && frappe.get_route()[1] === this.report_name) {
			return this.init_promise;
		}

		let tasks = [
			this.setup_defaults,
			this.setup_page,
			this.setup_report_wrapper,
			this.setup_report
		].map(fn => fn.bind(this));

		this.init_promise = frappe.run_serially(tasks);
		return this.init_promise;
	}

	setup_defaults() {
		this.route = frappe.get_route();
		this.page_name = frappe.get_route_str();
		this.report_name = this.route[1];
		this.page_title = __(this.report_name);
		this.user_settings = frappe.get_user_settings(this.report_name);

		this.start = 0;
		this.page_length = 20;
		this.data = [];

		this.fields = [];
		this.filters = [];
		this.order_by = 'modified desc';

		// Setup buttons
		this.primary_action = null;
		this.secondary_action = {
			label: __('Refresh'),
			action: () => this.refresh()
		};

		this.menu_items = this.get_menu_items();

		// throttle refresh for 500ms
		this.refresh = frappe.utils.throttle(this.refresh, 500);

		// Report Doc
		return frappe.db.get_doc('Report', this.report_name)
			.then(doc => {
				this.report_doc = doc;
			})
			// Ref DocType
			.then(() => {
				if (this.report_doc.ref_doctype) {
					return frappe.model.with_doctype(this.report_doc.ref_doctype);
				}
				return Promise.resolve();
			});
	}

	setup_report_wrapper() {
		if (this.$report) return;
		this.$report = $('<div class="report-wrapper">').appendTo(this.page.main);
	}

	setup_report() {
		this.$report.empty();
		this.datatable = null;
		return this.load_report_script()
			.then(() => this.load_report());
	}

	load_report_script() {
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
				this.html_format = r.message.html_format;
				this.report_settings.html_format = r.message.html_format;
			});
		});

		return this._load_script;
	}

	load_report() {
		this.page.clear_inner_toolbar();
		this.setup_filters();
		// this.toggle_expand_collapse_buttons(false);
		// this.is_tree_report = false;

		if (this.report_settings.onload) {
			frappe.run_serially([
				() => this.report_settings.onload(this),
				() => this.refresh()
			]);
		}
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
				// if(!this.flags.filters_set) {
				// 	// don't trigger change while setting filters
				// 	return;
				// }
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

		return this.set_route_filters();
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
		const filters = this.get_filter_values(true);

		this.report_ajax = frappe.call({
			method: "frappe.desk.query_report.run",
			type: "GET",
			args: {
				report_name: this.report_name,
				filters: filters
			}
		}).then(r => {
			this.report_ajax = undefined;
			this.render_report(r.message);
			// this.make_results(r.message);
		});
	}

	render_report(data) {
		this._data = data.result;
		if (this.datatable) {
			this.datatable.refresh(data.result);
			return;
		}
		this.datatable = new DataTable(this.$report[0], {
			columns: this.prepare_columns(data.columns),
			data: data.result,
			enableInlineFilters: true,
			// layout: 'fluid'
		});
	}

	prepare_columns(columns) {
		columns = columns.map(column => {
			if (typeof column === 'string') {
				if (column.includes(':')) {
					let [label, fieldtype, width] = column.split(':');
					let options;

					if (fieldtype.includes('/')) {
						[fieldtype, options] = fieldtype.split('/');
					}

					return {
						label,
						fieldtype,
						width,
						options
					};
				}

				return {
					label: column,
					fieldtype: 'Data'
				};
			}

			return column;
		});

		let get_original_data = (rowIndex) => {
			return this._data[rowIndex];
		};

		return columns.map(column => {
			return {
				id: column.fieldname,
				content: column.label,
				width: column.width || null,
				editable: false,
				format: (value, cell) => {
					const original_data = this._data[cell.rowIndex];//get_original_data(cell.rowIndex);
					let out = frappe.format(value, column);
					if (original_data.indent !== undefined && cell.colIndex === 1) {
						const next_row = get_original_data(cell.rowIndex + 1);
						const is_parent = next_row && next_row.indent > original_data.indent;
						const margin = 21 * original_data.indent;
						out = `<span class="report-tree-node" style="margin-left: ${margin}px">
							${is_parent ? '<span class="octicon octicon-triangle-down text-muted toggle"></span>': ''}
							${out}
						</span>`;
					}
					return out;
				}
			};
		});
	}

	get_data() {

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
		if (!this.report_doc.ref_doctype) return;
		const ref_doctype = frappe.get_meta(this.report_doc.ref_doctype);
		frappe.breadcrumbs.add(ref_doctype.module);
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
					frappe.ui.get_print_settings(false, function(print_settings) {
						this.print_report(print_settings);
					}, this.report_doc.letter_head);
				},
				standard: true
			},
			{
				label: __('PDF'),
				action: () => {
					frappe.ui.get_print_settings(false, function(print_settings) {
						this.pdf_report(print_settings);
					}, this.report_doc.letter_head);
				},
				standard: true
			},
			{
				label: __('Export'),
				action: () => this.make_export(),
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
				label: __('Add to Desktop'),
				action: () => frappe.add_to_desktop(this.report_name, null, this.report_name),
				standard: true
			},
		];
	}
};