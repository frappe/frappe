// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import DataTable from "frappe-datatable";

// Expose DataTable globally to allow customizations.
window.DataTable = DataTable;

frappe.provide("frappe.widget.utils");
frappe.provide("frappe.views");
frappe.provide("frappe.query_reports");

frappe.standard_pages["query-report"] = function () {
	var wrapper = frappe.container.add_page("query-report");

	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Query Report"),
		single_column: true,
	});

	frappe.query_report = new frappe.views.QueryReport({
		parent: wrapper,
	});

	$(wrapper).bind("show", function () {
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
			this.setup_events,
		].map((fn) => fn.bind(this));
		this.init_promise = frappe.run_serially(tasks);
		return this.init_promise;
	}

	setup_defaults() {
		this.route = frappe.get_route();
		this.page_name = frappe.get_route_str();

		// Setup buttons
		this.primary_action = null;

		// throttle refresh for 300ms
		this.refresh = frappe.utils.throttle(this.refresh, 300);

		this.ignore_prepared_report = false;
		this.menu_items = [];
	}

	update_url_with_filters() {
		if (frappe.get_route_str() == this.page_name) {
			window.history.replaceState(null, null, this.get_url_with_filters());
		}
	}

	get_url_with_filters() {
		let query_params = new URLSearchParams();
		if (this.prepared_report_name) {
			query_params.append("prepared_report_name", this.prepared_report_name);
		} else {
			Object.entries(this.get_filter_values()).map(([field, value], _idx) => {
				// multiselects
				if (Array.isArray(value)) {
					if (!value.length) return "";
					value = JSON.stringify(value);
				}
				query_params.append(field, value);
			});
		}
		let full_url = window.location.href.replace(window.location.search, "");
		if (query_params.toString()) {
			full_url += "?" + query_params.toString();
		}
		return full_url;
	}

	set_default_secondary_action() {
		this.refresh_button && this.refresh_button.remove();
		this.refresh_button = this.page.add_action_icon(
			"es-line-reload",
			() => {
				this.setup_progress_bar();
				this.refresh();
			},
			"",
			__("Reload Report")
		);
	}

	get_no_result_message() {
		return `<div class="msg-box no-border">
			<svg class="icon icon-xl mb-4" style="stroke: var(--text-light);">
				<use href="#icon-table"></use>
			</svg>
			<p>${__("Nothing to show")}</p>
		</div>`;
	}

	setup_events() {
		frappe.realtime.on("report_generated", (data) => {
			this.toggle_primary_button_disabled(false);
			if (data.report_name) {
				// If generated report and currently active Prepared Report has same fiters
				// then refresh the Prepared Report
				// Otherwise show alert with the link to the Prepared Report
				if (data.name == this.prepared_report_doc_name) {
					this.refresh();
				} else {
					let alert_message = `Report ${this.report_name} generated.
						<a href="#query-report/${this.report_name}/?prepared_report_name=${data.name}">View</a>`;
					frappe.show_alert({ message: alert_message, indicator: "orange" });
				}
			}
		});
		this.page.wrapper.on("click", "[data-action]", (e) => {
			let action_name = $(e.currentTarget).data("action");
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

		let route_options = {};
		route_options = Object.assign(route_options, frappe.route_options);

		if (this.report_name !== frappe.get_route()[1]) {
			// different report
			this.load_report(route_options);
		} else if (frappe.has_route_options()) {
			// filters passed through routes
			// so refresh report again
			this.refresh_report(route_options);
		} else {
			// same report
			// don't do anything to preserve state
			// like filters and datatable column widths
		}
	}

	load_report(route_options) {
		this.page.clear_inner_toolbar();
		this.route = frappe.get_route();
		this.page_name = frappe.get_route_str();
		this.report_name = this.route[1];
		this.page_title = __(this.report_name);
		this.show_save = false;
		this.menu_items = this.get_menu_items();
		this.datatable = null;
		this.export_dialog = null;

		frappe.run_serially([
			() => this.get_report_doc(),
			() => this.get_report_settings(),
			() => this.add_translate_data_checkbox(),
			() => this.setup_progress_bar(),
			() => this.setup_page_head(),
			() => this.refresh_report(route_options),
			() => this.add_chart_buttons_to_toolbar(true),
			() => this.add_card_button_to_toolbar(true),
		]);
	}

	add_card_button_to_toolbar() {
		if (!frappe.model.can_create("Number Card")) return;
		this.page.add_inner_button(
			__("Create Card"),
			() => {
				this.add_card_to_dashboard();
			},
			__("Actions")
		);
	}

	add_chart_buttons_to_toolbar(show) {
		if (!frappe.model.can_create("Dashboard Chart")) return;
		if (show) {
			this.create_chart_button && this.create_chart_button.remove();
			this.create_chart_button = this.page.add_inner_button(
				__("Set Chart"),
				() => {
					this.open_create_chart_dialog();
				},
				__("Actions")
			);

			if (this.chart_fields || this.chart_options) {
				this.add_to_dashboard_button && this.add_to_dashboard_button.remove();
				this.add_to_dashboard_button = this.page.add_inner_button(
					__("Add Chart to Dashboard"),
					() => {
						this.add_chart_to_dashboard();
					},
					__("Actions")
				);
			}
		} else {
			this.create_chart_button && this.create_chart_button.remove();
			this.add_to_dashboard_button && this.add_to_dashboard_button.remove();
		}
	}

	add_card_to_dashboard() {
		let field_options = frappe.report_utils.get_field_options_from_report(
			this.columns,
			this.raw_data
		);
		const dashboard_field = frappe.dashboard_utils.get_dashboard_link_field();
		const set_standard = frappe.boot.developer_mode;

		const dialog = new frappe.ui.Dialog({
			title: __("Create Card"),
			fields: [
				{
					fieldname: "report_field",
					label: __("Field"),
					fieldtype: "Select",
					options: field_options.numeric_fields,
				},
				{
					fieldname: "cb_1",
					fieldtype: "Column Break",
				},
				{
					fieldname: "report_function",
					label: __("Function"),
					options: ["Sum", "Average", "Minimum", "Maximum"],
					fieldtype: "Select",
				},
				{
					fieldname: "sb_1",
					label: __("Add to Dashboard"),
					fieldtype: "Section Break",
				},
				dashboard_field,
				{
					fieldname: "cb_2",
					fieldtype: "Column Break",
				},
				{
					fieldname: "label",
					label: __("Card Label"),
					fieldtype: "Data",
				},
			],
			primary_action_label: __("Add"),
			primary_action: (values) => {
				if (!values.label) {
					values.label = `${values.report_function} of ${toTitle(values.report_field)}`;
				}
				this.create_number_card(values, values.dashboard, values.label, set_standard);
				dialog.hide();
			},
		});

		dialog.show();
	}

	add_chart_to_dashboard() {
		if (this.chart_fields || this.chart_options) {
			const dashboard_field = frappe.dashboard_utils.get_dashboard_link_field();
			const set_standard = frappe.boot.developer_mode;

			const dialog = new frappe.ui.Dialog({
				title: __("Create Chart"),
				fields: [
					{
						fieldname: "dashboard_chart_name",
						label: __("Chart Name"),
						fieldtype: "Data",
					},
					dashboard_field,
				],
				primary_action_label: __("Add"),
				primary_action: (values) => {
					this.create_dashboard_chart(
						this.chart_fields || this.chart_options,
						values.dashboard,
						values.dashboard_chart_name,
						set_standard
					);
					dialog.hide();
				},
			});

			dialog.show();
		} else {
			frappe.msgprint(__("Please Set Chart"));
		}
	}

	create_number_card(values, dashboard_name, card_name, set_standard) {
		let args = {
			dashboard: dashboard_name || null,
			type: "Report",
			report_name: this.report_name,
			filters_json: JSON.stringify(this.get_filter_values()),
			set_standard: set_standard,
		};
		Object.assign(args, values);

		this.add_to_dashboard(
			"frappe.desk.doctype.number_card.number_card.create_report_number_card",
			args,
			dashboard_name,
			card_name,
			"Number Card"
		);
	}

	create_dashboard_chart(chart_args, dashboard_name, chart_name, set_standard) {
		let args = {
			dashboard: dashboard_name || null,
			chart_type: "Report",
			report_name: this.report_name,
			type: chart_args.chart_type || frappe.model.unscrub(chart_args.type),
			color: chart_args.color,
			filters_json: JSON.stringify(this.get_filter_values()),
			custom_options: {},
			set_standard: set_standard,
		};

		for (let key in chart_args) {
			if (key != "data") {
				args["custom_options"][key] = chart_args[key];
			}
		}

		if (this.chart_fields) {
			let x_field_title = toTitle(chart_args.x_field);
			let y_field_title = toTitle(chart_args.y_fields[0]);
			chart_name = chart_name || `${this.report_name}: ${x_field_title} vs ${y_field_title}`;

			Object.assign(args, {
				chart_name: chart_name,
				x_field: chart_args.x_field,
				y_axis: chart_args.y_axis_fields.map((f) => {
					return { y_field: f.y_field, color: f.color };
				}),
				use_report_chart: 0,
			});
		} else {
			chart_name = chart_name || this.report_name;
			Object.assign(args, {
				chart_name: chart_name,
				use_report_chart: 1,
			});
		}

		this.add_to_dashboard(
			"frappe.desk.doctype.dashboard_chart.dashboard_chart.create_report_chart",
			args,
			dashboard_name,
			chart_name,
			"Dashboard Chart"
		);
	}

	add_to_dashboard(method, args, dashboard_name, name, doctype) {
		frappe.xcall(method, { args: args }).then(() => {
			let message;
			if (dashboard_name) {
				let dashboard_route_html = `<a href="/app/dashboard-view/${dashboard_name}">${dashboard_name}</a>`;
				message = __("New {0} {1} added to Dashboard {2}", [
					__(doctype),
					name,
					dashboard_route_html,
				]);
			} else {
				message = __("New {0} {1} created", [__(doctype), name]);
			}

			frappe.msgprint(message, __("New {0} Created", [__(doctype)]));
		});
	}

	refresh_report(route_options) {
		this.prepared_report_name = null; // this should be set only if prepared report is EXPLICITLY requested
		this.toggle_message(true);
		this.toggle_report(false);

		return frappe.run_serially([
			() => this.setup_filters(),
			() => (this._no_refresh = true),
			() => this.set_route_filters(route_options),
			() => this.page.clear_custom_actions(),
			() => this.report_settings.onload && this.report_settings.onload(this),
			() => (this._no_refresh = false),
			() => this.refresh(),
		]);
	}

	get_report_doc() {
		return frappe.model
			.with_doc("Report", this.report_name)
			.then((doc) => {
				this.report_doc = doc;
			})
			.then(() => frappe.model.with_doctype(this.report_doc?.ref_doctype));
	}

	get_report_settings() {
		return new Promise((resolve, reject) => {
			if (frappe.query_reports[this.report_name]) {
				this.report_settings = frappe.query_reports[this.report_name];
				resolve();
			} else {
				frappe
					.xcall("frappe.desk.query_report.get_script", {
						report_name: this.report_name,
					})
					.then((settings) => {
						frappe.dom.eval(settings.script || "");
						frappe.after_ajax(() => {
							this.report_settings = this.get_local_report_settings(
								settings.custom_report_name
							);
							this.report_settings.html_format = settings.html_format;
							this.report_settings.execution_time = settings.execution_time || 0;
							frappe.query_reports[this.report_name] = this.report_settings;

							if (this.report_doc.filters && !this.report_settings.filters) {
								// add configured filters
								this.report_settings.filters = this.report_doc.filters;
							}

							resolve();
						});
					})
					.catch(reject);
			}
		});
	}

	get_local_report_settings(custom_report_name) {
		let report_script_name =
			this.report_doc.report_type === "Custom Report"
				? custom_report_name
					? custom_report_name
					: this.report_doc.reference_report
				: this.report_name;
		return frappe.query_reports[report_script_name] || {};
	}

	setup_progress_bar() {
		let seconds_elapsed = 0;
		const execution_time = this.report_settings?.execution_time || 0;

		if (execution_time < 5) return;

		this.interval = setInterval(function () {
			seconds_elapsed += 1;
			frappe.show_progress(__("Preparing Report"), seconds_elapsed, execution_time);
		}, 1000);
	}

	refresh_filters_dependency() {
		this.filters.forEach((filter) => {
			filter.guardian_has_value = true;

			if (filter.df.depends_on) {
				filter.guardian_has_value = this.evaluate_depends_on_value(
					filter.df.depends_on,
					filter.df.label
				);

				if (filter.guardian_has_value) {
					if (filter.df.hidden_due_to_dependency) {
						filter.df.hidden_due_to_dependency = false;
						this.toggle_filter_display(filter.df.fieldname, false);
					}
				} else {
					if (!filter.df.hidden_due_to_dependency) {
						filter.df.hidden_due_to_dependency = true;
						this.toggle_filter_display(filter.df.fieldname, true);
						filter.set_value(filter.df.default || null);
					}
				}
			}
		});
	}

	evaluate_depends_on_value(expression, filter_label) {
		let out = null;
		let doc = this.get_filter_values();
		if (doc) {
			if (typeof expression === "boolean") {
				out = expression;
			} else if (expression.substr(0, 5) == "eval:") {
				try {
					out = frappe.utils.eval(expression.substr(5), { doc });
				} catch (e) {
					frappe.throw(
						__('Invalid "depends_on" expression set in filter {0}', [filter_label])
					);
				}
			} else {
				var value = doc[expression];
				if ($.isArray(value)) {
					out = !!value.length;
				} else {
					out = !!value;
				}
			}
		}
		return out;
	}

	setup_filters() {
		this.clear_filters();
		const { filters = [] } = this.report_settings;

		let filter_area = this.page.page_form;
		this.filters = [];
		if (this.report_settings.seperate_check_filters) this.setup_check_filter_area();
		this.filters = filters
			.map((df, index) => {
				if (df.fieldtype === "Break") return;
				let f;
				if (df.fieldtype === "Check" && this.check_filter_area) {
					f = this.page.add_field(df, this.check_filter_area);
				} else {
					f = this.page.add_field(df, filter_area);
				}
				if (df.default) {
					f.set_input(df.default);
				}

				if (df.get_query) f.get_query = df.get_query;
				if (df.on_change) f.on_change = df.on_change;

				df.onchange = () => {
					this.refresh_filters_dependency();

					let current_filters = this.get_filter_values();
					if (
						this.previous_filters &&
						JSON.stringify(this.previous_filters) === JSON.stringify(current_filters)
					) {
						// filter values have not changed
						return;
					}
					// clear previous_filters after 10 seconds, to allow refresh for new data
					this.previous_filters = current_filters;
					setTimeout(() => (this.previous_filters = null), 10000);

					if (f.on_change) {
						f.on_change(this);
					} else if (!this._no_refresh) {
						this.refresh(true);
					}
				};

				f = Object.assign(f, df);

				return f;
			})
			.filter(Boolean);
		if (this.report_settings.seperate_check_filters) this.move_check_filter_area();
		if (this.report_settings.collapsible_filters) {
			this.filters_hidden = true;
			this.filter_row_length = this.get_filter_row_length();
			this.add_collapse_button();
			this.toggle_filter_visiblity();
		}
		this.refresh_filters_dependency();
		if (this.filters.length === 0) {
			// hide page form if no filters
			this.page.hide_form();
		} else {
			this.page.show_form();
		}
	}

	move_check_filter_area() {
		this.page.page_form.append(this.check_filter_area);
	}

	setup_check_filter_area() {
		let check_filter_area = "<div class='check-filter-area'> </div>";
		this.page.page_form.append(check_filter_area);
		this.check_filter_area = this.page.page_form.find(".check-filter-area");
	}

	get_filter_row_length() {
		let max_width = document.documentElement.clientWidth;
		let all_filters_position = this.filters.map((f) => f.wrapper.getBoundingClientRect().x);
		let closest_width = all_filters_position.reduce(function (prev, curr) {
			return Math.abs(curr - max_width) < Math.abs(prev - max_width) ? curr : prev;
		});
		return all_filters_position.indexOf(closest_width) + 1;
	}

	toggle_filter_visiblity() {
		let icon_name;
		if (this.filters_hidden) {
			for (let i = this.filter_row_length; i < this.filters.length; i++) {
				$(this.filters[i].wrapper).addClass("hidden");
			}
			this.check_filter_area.css("display", "none");
			this.filters_hidden = false;
			icon_name = "chevron-down";
		} else {
			for (let i = this.filter_row_length; i < this.filters.length; i++) {
				$(this.filters[i].wrapper).removeClass("hidden");
			}
			this.check_filter_area.css("display", "flex");
			this.filters_hidden = true;
			icon_name = "chevron-up";
		}
		this.$collapse_button.find("use").attr("href", `#icon-${icon_name}`);
	}

	add_collapse_button() {
		const me = this;
		let filter_no = this.filter_row_length - 1;
		if (this.filters[filter_no]) {
			this.$collapse_button = $(`<div>${frappe.utils.icon("chevron-down", "md")}</div>`);
			$(this.filters[filter_no].wrapper).append(this.$collapse_button);
			$(this.filters[filter_no].wrapper).css("display", "flex");
			$(this.filters[filter_no].wrapper).css("align-items", "center");
			$(this.filters[filter_no].wrapper).css("gap", "5px");
			this.$collapse_button.on("click", function () {
				me.toggle_filter_visiblity();
			});
		}
	}

	set_filters(filters) {
		this.filters.map((f) => {
			if (f.fieldtype == "MultiSelectList") {
				f.set_value(filters[f.fieldname]);
			} else {
				f.set_input(filters[f.fieldname]);
			}
		});
	}

	set_route_filters(route_options) {
		if (!route_options) route_options = frappe.route_options;

		if (route_options) {
			const fields = Object.keys(route_options);

			const filters_to_set = this.filters.filter((f) => fields.includes(f.df.fieldname));
			this.prepared_report_name = route_options.prepared_report_name;

			const promises = filters_to_set.map((f) => {
				return async () => {
					let value = route_options[f.df.fieldname];
					if (typeof value === "string" && value[0] === "[") {
						// multiselect array
						value = JSON.parse(value);
					}
					await f.set_value(value);
				};
			});
			promises.push(() => {
				frappe.route_options = null;
			});

			this.ignore_prepared_report = route_options["ignore_prepared_report"] || false;

			return frappe.run_serially(promises);
		}
	}

	clear_filters() {
		this.page.clear_fields();
	}

	refresh(have_filters_changed) {
		this.toggle_message(true);
		this.toggle_report(false);
		let filters = this.get_filter_values(!this.prepared_report_name);

		// for custom reports,
		// are_default_filters is true if the filters haven't been modified and for all filters,
		// the filter value is the default value or there's no default value for the filter and the current value is empty.
		// are_default_filters is false otherwise.

		let are_default_filters = this.filters
			.map((filter) => {
				return (
					!have_filters_changed &&
					(filter.default === filter.value || (!filter.default && !filter.value))
				);
			})
			.every((res) => res === true);

		this.show_loading_screen();

		// only one refresh at a time
		if (this.last_ajax) {
			this.last_ajax.abort();
		}

		if (this.prepared_report_name) {
			filters.prepared_report_name = this.prepared_report_name;
		}

		return new Promise((resolve) => {
			this.last_ajax = frappe.call({
				method: "frappe.desk.query_report.run",
				type: "GET",
				args: {
					report_name: this.report_name,
					filters: filters,
					ignore_prepared_report: this.ignore_prepared_report,
					is_tree: this.report_settings.tree,
					parent_field: this.report_settings.parent_field,
					are_default_filters: are_default_filters,
				},
				callback: resolve,
				always: () => this.page.btn_secondary.prop("disabled", false),
			});
		})
			.then((r) => {
				let data = r.message;
				this.hide_status();
				clearInterval(this.interval);

				this.execution_time = data.execution_time || 0.1;

				if (data.custom_filters) {
					this.set_filters(data.custom_filters);
					this.previous_filters = data.custom_filters;
				}

				if (data.prepared_report) {
					this.prepared_report = true;
					this.prepared_report_document = data.doc;
					// If query_string contains prepared_report_name then set filters
					// to match the mentioned prepared report doc and disable editing
					if (this.prepared_report_name) {
						const filters_from_report = JSON.parse(data.doc.filters);
						Object.values(this.filters).forEach(function (field) {
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

				if (data.report_summary) {
					this.$summary.empty();
					this.render_summary(data.report_summary);
				}

				if (data.message && !data.prepared_report) this.show_status(data.message);

				this.toggle_message(false);
				if (data.result && data.result.length) {
					this.prepare_report_data(data);
					this.chart_options = this.get_chart_options(data);

					this.$chart.empty();
					if (this.chart_options) {
						this.render_chart(this.chart_options);
					} else {
						this.$chart.empty();
						if (this.chart_fields) {
							this.chart_options = frappe.report_utils.make_chart_options(
								this.columns,
								this.raw_data,
								this.chart_fields
							);
							this.chart_options && this.render_chart(this.chart_options);
						}
					}
					this.render_datatable();
					this.add_chart_buttons_to_toolbar(true);
					this.add_card_button_to_toolbar();
					this.$report.show();
				} else {
					this.data = [];
					this.toggle_nothing_to_show(true);
					this.add_chart_buttons_to_toolbar(false);
				}

				this.show_footer_message();
				frappe.hide_progress();
			})
			.finally(() => {
				this.hide_loading_screen();
				this.update_url_with_filters();
				this.report_settings.after_refresh?.(this);
			});
	}

	render_summary(data) {
		data.forEach((summary) => {
			frappe.utils.build_summary_item(summary).appendTo(this.$summary);
		});

		this.$summary.show();
	}

	get_query_params() {
		const query_string = frappe.utils.get_query_string(frappe.get_route_str());
		return frappe.utils.get_query_params(query_string);
	}

	add_prepared_report_buttons(doc) {
		if (doc) {
			this.page.add_inner_button(
				__("Download Report"),
				function () {
					window.open(
						frappe.urllib.get_full_url(
							"/api/method/frappe.core.doctype.prepared_report.prepared_report.download_attachment?" +
								"dn=" +
								encodeURIComponent(doc.name)
						)
					);
				},
				__("Actions")
			);

			let pretty_diff = frappe.datetime.comment_when(doc.report_end_time);
			const days_old = frappe.datetime.get_day_diff(
				frappe.datetime.now_datetime(),
				doc.report_end_time
			);
			if (days_old > 1) {
				pretty_diff = `<span style="color:var(--red-600)">${pretty_diff}</span>`;
			}
			const part1 = __("This report was generated {0}.", [pretty_diff]);
			const part2 = __("To get the updated report, click on {0}.", [__("Rebuild")]);
			const part3 = __("See all past reports.");

			this.show_status(`
				<div class="indicator orange">
					<span>
						${part1}
						${part2}
						<a href="/app/List/Prepared%20Report?report_name=${this.report_name}"> ${part3}</a>
					</span>
				</div>
			`);
		}

		// Three cases
		// 1. First time with given filters, no data.
		// 2. Showing data from specific report
		// 3. Showing data from an old report without specific report name
		this.primary_action_map = {
			New: {
				label: __("Generate New Report"),
				click: () => {
					this.show_warning_or_generate_report();
				},
			},
			Edit: {
				label: __("Edit"),
				click: () => {
					frappe.set_route(frappe.get_route());
				},
			},
			Rebuild: {
				label: __("Rebuild"),
				click: () => {
					this.show_warning_or_generate_report();
				},
			},
		};

		let prepared_report_action = "New";
		if (this.prepared_report_name) {
			prepared_report_action = "Edit";
		} else if (doc) {
			prepared_report_action = "Rebuild";
		}

		let primary_action = this.primary_action_map[prepared_report_action];

		if (!this.primary_button || this.primary_button.text() !== primary_action.label) {
			this.primary_button = this.page.set_primary_action(
				primary_action.label,
				primary_action.click
			);
		}
	}

	toggle_primary_button_disabled(disable) {
		this.primary_button.prop("disabled", disable);
	}

	show_warning_or_generate_report() {
		frappe
			.xcall(
				"frappe.core.doctype.prepared_report.prepared_report.get_reports_in_queued_state",
				{
					filters: this.get_filter_values(),
					report_name: this.report_name,
				}
			)
			.then((reports) => {
				this.queued_prepared_reports = reports;

				if (reports.length) {
					const message = this.get_queued_prepared_reports_warning_message(reports);
					this.prepared_report_dialog = frappe.warn(
						__("Reports already in Queue"),
						message,
						() => this.generate_background_report(),
						__("Proceed Anyway"),
						true
					);

					this.prepared_report_dialog.footer.prepend(`
					<button type="button" class="btn btn-sm btn-default pull-left" data-action="delete_old_queued_reports">
						${__("Delete and Generate New")}
					</button>`);

					frappe.utils.bind_actions_with_object(
						this.prepared_report_dialog.wrapper,
						this
					);
				} else {
					this.generate_background_report();
				}
			});
	}

	get_queued_prepared_reports_warning_message(reports) {
		const route = `/app/List/Prepared Report/List?status=Queued&report_name=${this.report_name}`;
		const report_link_html =
			reports.length == 1
				? `<a class="underline" href="${route}">${__("1 Report")}</a>`
				: `<a class="underline" href="${route}">${__("{0} Reports", [
						reports.length,
				  ])}</a>`;

		const no_of_reports_html =
			reports.length == 1
				? `${__("There is {0} with the same filters already in the queue:", [
						report_link_html,
				  ])}`
				: `${__("There are {0} with the same filters already in the queue:", [
						report_link_html,
				  ])}`;

		let warning_message = `
			<p>
				${__("Are you sure you want to generate a new report?")}
				${no_of_reports_html}
			</p>`;

		let get_item_html = (item) =>
			`<a class="underline" href="/app/prepared-report/${item.name}">${item.name}</a>`;

		warning_message += reports.map(get_item_html).join(", ");

		return warning_message;
	}

	delete_old_queued_reports() {
		this.prepared_report_dialog.hide();
		frappe
			.xcall("frappe.core.doctype.prepared_report.prepared_report.delete_prepared_reports", {
				reports: this.queued_prepared_reports,
			})
			.then(() => this.generate_background_report());
	}

	generate_background_report() {
		this.toggle_primary_button_disabled(true);
		let mandatory = this.filters.filter((f) => f.df.reqd);
		let missing_mandatory = mandatory.filter((f) => !f.get_value());
		if (!missing_mandatory.length) {
			let filters = this.get_filter_values(true);
			return new Promise((resolve) =>
				frappe.call({
					method: "frappe.core.doctype.prepared_report.prepared_report.make_prepared_report",
					args: {
						report_name: this.report_name,
						filters: filters,
					},
					callback: resolve,
				})
			).then((r) => {
				const data = r.message;
				// Rememeber the name of Prepared Report doc
				this.prepared_report_doc_name = data.name;
				let alert_message =
					`<a href='/app/prepared-report/${data.name}'>` +
					__("Report initiated, click to view status") +
					`</a>`;
				frappe.show_alert({ message: alert_message, indicator: "orange" }, 10);
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
		this.tree_report = this.data.some((d) => "indent" in d);
	}

	render_datatable() {
		let data = this.data;
		let columns = this.columns.filter((col) => !col.hidden);

		if (data.length > (cint(frappe.boot.sysdefaults.max_report_rows) || 100000)) {
			let msg = __(
				"This report contains {0} rows and is too big to display in browser, you can {1} this report instead.",
				[cstr(format_number(data.length, null, 0)).bold(), __("export").bold()]
			);

			this.toggle_message(true, `${frappe.utils.icon("solid-warning")} ${msg}`);
			return;
		}

		if (this.raw_data.add_total_row && !this.report_settings.tree) {
			data = data.slice();
			data.splice(-1, 1);
		}

		this.$report.show();
		if (
			this.datatable &&
			this.datatable.options &&
			this.datatable.options.showTotalRow === this.raw_data.add_total_row
		) {
			this.datatable.options.treeView = this.tree_report;
			this.datatable.refresh(data, columns);
		} else {
			let datatable_options = {
				columns: columns,
				data: data,
				inlineFilters: true,
				language: frappe.boot.lang,
				translations: frappe.utils.datatable.get_translations(),
				treeView: this.tree_report,
				layout: "fixed",
				cellHeight: 33,
				showTotalRow: this.raw_data.add_total_row && !this.report_settings.tree,
				direction: frappe.utils.is_rtl() ? "rtl" : "ltr",
				hooks: {
					columnTotal: frappe.utils.report_column_total,
				},
			};

			if (this.report_settings.get_datatable_options) {
				datatable_options = this.report_settings.get_datatable_options(datatable_options);
			}
			this.datatable = new window.DataTable(this.$report[0], datatable_options);
		}

		if (typeof this.report_settings.initial_depth == "number") {
			this.datatable.rowmanager.setTreeDepth(this.report_settings.initial_depth);
		}
		if (this.report_settings.after_datatable_render) {
			this.report_settings.after_datatable_render(this.datatable);
		}
	}

	show_loading_screen() {
		const loading_state = `<div class="msg-box no-border">
			<svg class="icon icon-xl mb-4" style="stroke: var(--text-light);">
				<use href="#icon-table"></use>
			</svg>
			<p>${__("Loading")}...</p>
		</div>`;

		this.$loading.find("div").html(loading_state);
		this.$report.hide();
		this.$loading.show();
	}

	hide_loading_screen() {
		this.$loading.hide();
	}

	get_chart_options(data) {
		let options = this.report_settings.get_chart_data
			? this.report_settings.get_chart_data(data.columns, data.result)
			: data.chart
			? data.chart
			: undefined;

		if (!(options && options.data && options.data.labels && options.data.labels.length > 0))
			return;

		if (options.fieldtype) {
			options.tooltipOptions = {
				formatTooltipY: (d) =>
					frappe.format(
						d,
						{
							fieldtype: options.fieldtype,
							options: options.options,
						},
						options.options,
						options
					),
			};
		}
		options.axisOptions = {
			shortenYAxisNumbers: 1,
			numberFormatter: frappe.utils.format_chart_axis_number,
		};
		options.height = 280;
		return options;
	}

	render_chart(options) {
		this.$chart.empty();
		this.$chart.show();
		this.chart = new frappe.Chart(this.$chart[0], options);
	}

	open_create_chart_dialog() {
		const me = this;
		let field_options = frappe.report_utils.get_field_options_from_report(
			this.columns,
			this.raw_data
		);

		function set_chart_values(values) {
			values.y_fields = [];
			values.colors = [];
			if (values.y_axis_fields) {
				values.y_axis_fields.map((f) => {
					values.y_fields.push(f.y_field);
					values.colors.push(f.color);
				});
			}

			values.y_fields = values.y_fields.map((d) => d.trim()).filter(Boolean);

			return values;
		}

		function preview_chart() {
			const wrapper = $(dialog.fields_dict["chart_preview"].wrapper);
			let values = dialog.get_values(true);
			values = set_chart_values(values);

			if (values.x_field && values.y_fields.length) {
				let options = frappe.report_utils.make_chart_options(
					me.columns,
					me.raw_data,
					values
				);
				me.chart_fields = values;
				wrapper.empty();
				new frappe.Chart(wrapper[0], options);
				wrapper.find(".chart-container .title, .chart-container .sub-title").hide();
				wrapper.show();

				dialog.fields_dict["create_dashoard_chart"].df.hidden = 0;
				dialog.refresh();
			} else {
				wrapper[0].innerHTML = `<div class="flex justify-center align-center text-muted" style="height: 120px; display: flex;">
					<div>${__("Please select X and Y fields")}</div>
				</div>`;
			}
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Create Chart"),
			fields: [
				{
					fieldname: "x_field",
					label: "X Field",
					fieldtype: "Select",
					default: me.chart_fields ? me.chart_fields.x_field : null,
					options: field_options.non_numeric_fields,
				},
				{
					fieldname: "cb_1",
					fieldtype: "Column Break",
				},
				{
					fieldname: "chart_type",
					label: "Type of Chart",
					fieldtype: "Select",
					options: ["Bar", "Line", "Percentage", "Pie", "Donut"],
					default: me.chart_fields ? me.chart_fields.chart_type : "Bar",
				},
				{
					fieldname: "sb_1",
					fieldtype: "Section Break",
					label: "Y Axis",
				},
				{
					fieldname: "y_axis_fields",
					fieldtype: "Table",
					fields: [
						{
							fieldtype: "Select",
							fieldname: "y_field",
							name: "y_field",
							label: __("Y Field"),
							options: field_options.numeric_fields,
							in_list_view: 1,
						},
						{
							fieldtype: "Color",
							fieldname: "color",
							name: "color",
							label: __("Color"),
							in_list_view: 1,
						},
					],
				},
				{
					fieldname: "preview_chart_button",
					fieldtype: "Button",
					label: "Preview Chart",
					click: preview_chart,
				},
				{
					fieldname: "sb_2",
					fieldtype: "Section Break",
					label: "Chart Preview",
				},
				{
					fieldname: "chart_preview",
					label: "Chart Preview",
					fieldtype: "HTML",
				},
				{
					fieldname: "create_dashoard_chart",
					label: "Add Chart to Dashboard",
					fieldtype: "Button",
					hidden: 1,
					click: () => {
						dialog.hide();
						this.add_chart_to_dashboard();
					},
				},
			],
			primary_action_label: __("Create"),
			primary_action: (values) => {
				values = set_chart_values(values);

				let options = frappe.report_utils.make_chart_options(
					this.columns,
					this.raw_data,
					values
				);
				me.chart_fields = values;

				let x_field_label = field_options.numeric_fields.filter(
					(field) => field.value == values.y_fields[0]
				)[0].label;
				let y_field_label = field_options.non_numeric_fields.filter(
					(field) => field.value == values.x_field
				)[0].label;

				options.title = __("{0}: {1} vs {2}", [
					this.report_name,
					x_field_label,
					y_field_label,
				]);

				this.render_chart(options);
				this.add_chart_buttons_to_toolbar(true);

				dialog.hide();
			},
		});

		dialog.show();

		// load preview after dialog animation
		setTimeout(preview_chart, 500);
	}

	prepare_columns(columns) {
		let is_query_generated_report =
			this.report_doc.query &&
			this.report_doc.query != undefined &&
			this.report_doc.query != "";
		return columns.map((column) => {
			column = frappe.report_utils.prepare_field_from_column(column);

			const format_cell = (value, row, column, data) => {
				if (column.isHeader && !data && this.data) {
					// totalRow doesn't have a data object
					// proxy it using the first data object
					// applied to Float, Currency fields, needed only for currency formatting.
					// make first data column have value 'Total'
					let index = 1;

					if (this.report_settings.get_datatable_options) {
						let datatable = this.report_settings.get_datatable_options({});
						if (datatable && datatable.checkboxColumn) index = 2;
					}

					if (column.colIndex === index && !value) {
						value = __("Total");
						column = { fieldtype: "Data" }; // avoid type issues for value if Date column
					} else if (["Currency", "Float"].includes(column.fieldtype)) {
						// proxy for currency and float
						data = this.data[0];
					}
				}
				return frappe.format(
					value,
					column,
					{ for_print: false, always_show_decimals: true },
					data
				);
			};

			let compareFn = null;
			if (column.fieldtype === "Date") {
				compareFn = (cell, keyword) => {
					if (!cell.content) return null;
					if (keyword.length !== "YYYY-MM-DD".length) return null;

					const keywordValue = frappe.datetime.user_to_obj(keyword);
					const cellValue = frappe.datetime.str_to_obj(cell.content);
					return [+cellValue, +keywordValue];
				};
			}

			return Object.assign(column, {
				id: column.fieldname,
				// The column label should have already been translated in the
				// backend. Translating it again would cause unexpected behaviour.

				// Translating based on condition: when a report is generated through a query, the label is not translated.
				name: is_query_generated_report ? __(column.label) : column.label,
				width: parseInt(column.width) || null,
				editable: column.editable ?? false,
				compareValue: compareFn,
				format: (value, row, column, data, filter) => {
					if (this.report_settings.formatter) {
						return this.report_settings.formatter(
							value,
							row,
							column,
							data,
							format_cell,
							filter
						);
					}
					return format_cell(value, row, column, data);
				},
			});
		});
	}

	prepare_data(data) {
		return data.map((row) => {
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
		const visible_column_ids = this.datatable.datamanager
			.getColumns(true)
			.map((col) => col.id);

		return visible_column_ids
			.map((id) => this.columns.find((col) => col.id === id))
			.filter(Boolean);
	}

	get_filter_values(raise) {
		// check for mandatory property for filters added via UI
		if (raise) {
			const mandatory = this.filters.filter((f) => f.df.reqd || f.df.mandatory);
			const missing_mandatory = mandatory.filter((f) => !f.get_value());
			if (missing_mandatory.length > 0) {
				let message = __("Please set filters");
				this.hide_loading_screen();
				this.toggle_message(raise, message);
				throw "Filter missing";
			}
		}

		raise && this.toggle_message(false);

		return this.filters
			.filter((f) => f.get_value?.())
			.map((f) => {
				var v = f.get_value();
				// hidden fields dont have $input
				if (f.df.hidden) v = f.value;
				if (v === "%") v = null;
				if (f.df.wildcard_filter) {
					v = `%${v}%`;
				}
				return {
					[f.df.fieldname]: v,
				};
			})
			.reduce((acc, f) => {
				Object.assign(acc, f);
				return acc;
			}, {});
	}

	get_filter(fieldname) {
		const field = (this.filters || []).find((f) => f.df.fieldname === fieldname);
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
		if (typeof fieldname === "string") {
			field_value_map[fieldname] = value;
		} else {
			field_value_map = fieldname;
		}

		this._no_refresh = true;
		Object.keys(field_value_map).forEach((fieldname, i, arr) => {
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

	make_access_log(method, file_format) {
		frappe.call("frappe.core.doctype.access_log.access_log.make_access_log", {
			doctype: this.doctype || "",
			report_name: this.report_name,
			filters: this.get_filter_values(),
			file_type: file_format,
			method: method,
		});
	}

	async print_report(print_settings) {
		let custom_format = this.report_settings.html_format || null;
		const filters_html = this.get_filters_html_for_print();
		const landscape = print_settings.orientation == "Landscape";

		if (print_settings.report) {
			custom_format = await this.get_report_print_format(print_settings.report);
		}

		this.make_access_log("Print", "PDF");
		frappe.render_grid({
			template: print_settings.columns ? "print_grid" : custom_format,
			title: __(this.report_name),
			subtitle: filters_html,
			print_settings: print_settings,
			landscape: landscape,
			filters: this.get_filter_values(),
			data: this.get_data_for_print(),
			columns: this.get_columns_for_print(print_settings, custom_format),
			original_data: this.data,
			report: this,
			can_use_smaller_font: this.report_doc.is_standard === "Yes" && custom_format ? 0 : 1,
		});
	}

	async pdf_report(print_settings) {
		const base_url = frappe.urllib.get_base_url();
		const print_css = frappe.boot.print_css;
		const landscape = print_settings.orientation == "Landscape";

		let custom_format = this.report_settings.html_format || null;
		const columns = this.get_columns_for_print(print_settings, custom_format);
		const data = this.get_data_for_print();
		const applied_filters = this.get_filter_values();

		if (print_settings.report) {
			custom_format = await this.get_report_print_format(print_settings.report);
		}

		const filters_html = this.get_filters_html_for_print();
		const template = print_settings.columns || !custom_format ? "print_grid" : custom_format;
		const content = frappe.render_template(template, {
			title: __(this.report_name),
			subtitle: filters_html,
			filters: applied_filters,
			data: data,
			original_data: this.data,
			columns: columns,
			report: this,
		});

		// Render Report in HTML
		const html = frappe.render_template("print_template", {
			title: __(this.report_name),
			content: content,
			base_url: base_url,
			print_css: print_css,
			print_settings: print_settings,
			landscape: landscape,
			columns: columns,
			lang: frappe.boot.lang,
			layout_direction: frappe.utils.is_rtl() ? "rtl" : "ltr",
			can_use_smaller_font: this.report_doc.is_standard === "Yes" && custom_format ? 0 : 1,
		});

		let filter_values = [],
			name_len = 0;
		for (var key of Object.keys(applied_filters)) {
			name_len = name_len + applied_filters[key].toString().length;
			if (name_len > 200) break;
			filter_values.push(applied_filters[key]);
		}

		if (filter_values.length) {
			print_settings.report_name = `${__(this.report_name)}_${filter_values.join("_")}.pdf`;
		} else {
			print_settings.report_name = `${__(this.report_name)}.pdf`;
		}
		frappe.render_pdf(html, print_settings);
	}

	async get_report_print_format(report_name) {
		const filters = {
			name: report_name,
			disabled: 0,
		};
		const r = await frappe.db.get_value("Print Format", filters, ["html", "css"]);
		if (r && r.message && r.message.html) {
			const css = r.message.css || "";
			const html = r.message.html || "";
			return `<style>${css}</style>${html}`;
		} else {
			frappe.msgprint(__("Print Format not found"));
			return null;
		}
	}

	get_filters_html_for_print() {
		const applied_filters = this.get_filter_values();
		return Object.keys(applied_filters)
			.map((fieldname) => {
				const docfield = frappe.query_report.get_filter(fieldname).df;
				const value = applied_filters[fieldname];

				if (frappe.utils.is_empty(value) || docfield.hidden_due_to_dependency) {
					return null;
				}

				return `<div class="filter-row">
					<b>${__(docfield.label, null, docfield.parent)}:</b> ${frappe.format(value, docfield)}
				</div>`;
			})
			.join("");
	}

	export_report() {
		if (this.export_dialog) {
			this.export_dialog.clear();
			this.export_dialog.show();
			return;
		}

		let extra_fields = [];

		if (this.tree_report) {
			extra_fields.push({
				label: __("Include indentation"),
				fieldname: "include_indentation",
				fieldtype: "Check",
			});
		}

		if (this.filters.length > 0) {
			extra_fields.push({
				label: __("Include filters"),
				fieldname: "include_filters",
				fieldtype: "Check",
			});
		}

		if (this.report_settings.export_hidden_cols) {
			const hidden_fields = [];
			this.columns.forEach((column) => {
				if (column.hidden) {
					hidden_fields.push(column.label);
				}
			});
			if (hidden_fields.length) {
				extra_fields.push(
					{
						fieldname: "column_break_1",
						fieldtype: "Column Break",
					},
					{
						label: __("Include hidden columns"),
						fieldname: "include_hidden_columns",
						description: __("Hidden columns include: {0}", [hidden_fields.join(", ")]),
						fieldtype: "Check",
					}
				);
			}
		}

		this.export_dialog = frappe.report_utils.get_export_dialog(
			__(this.report_name),
			extra_fields,
			({
				file_format,
				include_indentation,
				include_filters,
				include_hidden_columns,
				csv_delimiter,
				csv_quoting,
				csv_decimal_sep,
			}) => {
				this.make_access_log("Export", file_format);

				let filters = this.get_filter_values(true);
				let boolean_labels = { 1: __("Yes"), 0: __("No") };
				let applied_filters = {};

				for (const [key, value] of Object.entries(filters)) {
					const df = frappe.query_report.get_filter(key).df;
					if (!df.hidden_due_to_dependency) {
						applied_filters[df.label] =
							df.fieldtype === "Check" ? boolean_labels[value] : value;
					}
				}

				if (this.prepared_report_name) {
					filters.prepared_report_name = this.prepared_report_name;
				}

				const visible_idx = this.datatable?.bodyRenderer.visibleRowIndices || [];
				if (visible_idx.length + 1 === this.data?.length) {
					visible_idx.push(visible_idx.length);
				}

				const args = {
					cmd: "frappe.desk.query_report.export_query",
					report_name: this.report_name,
					custom_columns: this.custom_columns?.length ? this.custom_columns : [],
					file_format_type: file_format,
					filters: filters,
					applied_filters: applied_filters,
					visible_idx,
					csv_delimiter,
					csv_quoting,
					csv_decimal_sep,
					include_indentation,
					include_filters,
					include_hidden_columns,
				};

				open_url_post(frappe.request.url, args);

				this.export_dialog.hide();
			}
		);

		this.export_dialog.show();
	}

	get_data_for_csv(include_indentation) {
		const rows = this.datatable.bodyRenderer.visibleRows;
		if (this.raw_data.add_total_row) {
			rows.push(this.datatable.bodyRenderer.getTotalRow());
		}
		return rows.map((row) => {
			const standard_column_count = this.datatable.datamanager.getStandardColumnCount();
			return row.slice(standard_column_count).map((cell, i) => {
				if (cell.column.fieldtype === "Duration") {
					cell.content = frappe.utils.get_formatted_duration(cell.content);
				}
				if (include_indentation && i === 0) {
					cell.content = "   ".repeat(row.meta.indent) + (cell.content ?? "");
				}
				return cell.content ?? "";
			});
		});
	}

	get_data_for_print() {
		if (!this.data.length) {
			return [];
		}

		const rows = this.datatable.datamanager.rowViewOrder
			.map((index) => {
				if (this.datatable.bodyRenderer.visibleRowIndices.includes(index)) {
					return this.data[index];
				}
			})
			.filter(Boolean);

		if (this.raw_data.add_total_row && !this.report_settings.tree) {
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
			columns = this.get_visible_columns().filter((column) =>
				print_settings.columns.includes(column.fieldname)
			);
		} else {
			columns = custom_format ? this.columns : this.get_visible_columns();
		}

		return columns;
	}

	get_menu_items() {
		let items = [
			{
				label: __("Refresh"),
				action: () => this.refresh(),
				class: "visible-xs",
			},
			{
				label: __("Edit"),
				action: () => frappe.set_route("Form", "Report", this.report_name),
				condition: () => frappe.user.is_report_manager(),
				standard: true,
			},
			{
				label: __("Print"),
				action: () => {
					let dialog = frappe.ui.get_print_settings(
						false,
						(print_settings) => this.print_report(print_settings),
						this.report_doc.letter_head,
						this.get_visible_columns()
					);
					this.add_portrait_warning(dialog);
				},
				condition: () => frappe.model.can_print(this.report_doc.ref_doctype),
				standard: true,
			},
			{
				label: __("PDF"),
				action: () => {
					let dialog = frappe.ui.get_print_settings(
						false,
						(print_settings) => this.pdf_report(print_settings),
						this.report_doc.letter_head,
						this.get_visible_columns()
					);

					this.add_portrait_warning(dialog);
				},
				condition: () => frappe.model.can_print(this.report_doc.ref_doctype),
				standard: true,
			},
			{
				label: __("Export"),
				action: () => this.export_report(),
				condition: () => frappe.model.can_export(this.report_doc.ref_doctype),
				standard: true,
			},
			{
				label: __("Setup Auto Email"),
				action: () =>
					frappe.set_route("List", "Auto Email Report", { report: this.report_name }),
				standard: true,
			},
			{
				label: __("Add Column"),
				action: () => {
					let d = new frappe.ui.Dialog({
						title: __("Add Column"),
						fields: [
							{
								fieldtype: "Select",
								fieldname: "doctype",
								label: __("From Document Type"),
								options: this.linked_doctypes?.map((df) => ({
									label: df.doctype + " (" + frappe.unscrub(df.fieldname) + ")",
									value: JSON.stringify({
										doctype: df.doctype,
										fieldname: df.fieldname,
									}),
								})),
								change: () => {
									const { doctype, fieldname } = JSON.parse(
										d.get_value("doctype")
									);
									frappe.model.with_doctype(doctype, () => {
										let options = frappe.meta
											.get_docfields(doctype)
											.filter(frappe.model.is_value_type)
											.map((df) => ({
												label: df.label,
												value: df.fieldname,
											}));

										d.set_df_property(
											"field",
											"options",
											options.sort(function (a, b) {
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
								},
							},
							{
								fieldtype: "Select",
								label: __("Field"),
								fieldname: "field",
								options: [],
							},
							{
								fieldtype: "Select",
								label: __("Insert After"),
								fieldname: "insert_after",
								options: this.columns.map((df) => df.label),
							},
						],
						primary_action: (values) => {
							const custom_columns = [];
							const { doctype, fieldname } = JSON.parse(values.doctype);
							Object.assign(values, { doctype, fieldname });
							let df = frappe.meta.get_docfield(values.doctype, values.field);
							const insert_after_index = this.columns.findIndex(
								(column) => column.label === values.insert_after
							);

							custom_columns.push({
								fieldname: this.columns
									.map((column) => column.fieldname)
									.includes(df.fieldname)
									? df.fieldname + "-" + frappe.scrub(values.doctype)
									: df.fieldname,
								fieldtype: df.fieldtype,
								label: df.label,
								insert_after_index: insert_after_index,
								link_field: this.doctype_field_map[values.doctype],
								doctype: values.doctype,
								options: df.options,
								width: 100,
							});

							this.custom_columns = this.custom_columns.concat(custom_columns);
							frappe.call({
								method: "frappe.desk.query_report.get_data_for_custom_field",
								args: {
									field: values.field,
									doctype: values.doctype,
									names: Array.from(
										this.doctype_field_map[values.doctype].names
									),
								},
								callback: (r) => {
									const custom_data = r.message;
									this.add_custom_column(
										custom_columns,
										custom_data,
										values,
										insert_after_index
									);
									d.hide();
								},
							});
							this.set_menu_items();
						},
					});

					d.show();
				},
				standard: true,
			},
			{
				label: __("User Permissions"),
				action: () =>
					frappe.set_route("List", "User Permission", {
						doctype: "Report",
						name: this.report_name,
					}),
				condition: () => frappe.user.has_role("System Manager"),
				standard: true,
			},
		];

		if (frappe.user.is_report_manager()) {
			items.push({
				label: __("Save"),
				action: () => {
					let d = new frappe.ui.Dialog({
						title: __("Save Report"),
						fields: [
							{
								fieldtype: "Data",
								fieldname: "report_name",
								label: __("Report Name"),
								default:
									this.report_doc.is_standard == "No" ? this.report_name : "",
								reqd: true,
							},
						],
						primary_action: (values) => {
							frappe.call({
								method: "frappe.desk.query_report.save_report",
								args: {
									reference_report: this.report_name,
									report_name: values.report_name,
									columns: this.get_visible_columns(),
									filters: this.get_filter_values(),
								},
								callback: function (r) {
									this.show_save = false;
									d.hide();
									frappe.set_route("query-report", r.message);
								},
							});
						},
					});
					d.show();
				},
				standard: true,
			});
		}

		return items;
	}

	add_portrait_warning(dialog) {
		if (this.columns.length > 10) {
			dialog.set_df_property("orientation", "change", () => {
				let value = dialog.get_value("orientation");
				let description =
					value === "Portrait"
						? __("Report with more than 10 columns looks better in Landscape mode.")
						: "";
				dialog.set_df_property("orientation", "description", description);
			});
		}
	}

	add_custom_column(custom_column, custom_data, new_column_data, insert_after_index) {
		const column = this.prepare_columns(custom_column);
		const column_field = new_column_data.field;

		this.columns.splice(insert_after_index + 1, 0, column[0]);

		this.data.forEach((row) => {
			if (column[0].fieldname.includes("-")) {
				row[column_field + "-" + frappe.scrub(new_column_data.doctype)] =
					custom_data[row[new_column_data.fieldname]];
			} else {
				row[column_field] = custom_data[row[new_column_data.fieldname]];
			}
		});

		this.render_datatable();
	}

	get_linked_doctypes() {
		let doctypes = [];
		let dynamic_links = [];
		let dynamic_doctypes = new Set();
		this.doctype_field_map = {};

		this.columns.forEach((df) => {
			if (df.fieldtype == "Link" && df.options && df.options != "Currency") {
				doctypes.push({
					doctype: df.options,
					fieldname: df.fieldname,
				});
			} else if (df.fieldtype == "Dynamic Link" && df.options) {
				dynamic_links.push({
					link_name: df.options,
					fieldname: df.fieldname,
				});
			}
		});

		this.data.forEach((row) => {
			dynamic_links.forEach((field) => {
				if (row[field.link_name]) {
					dynamic_doctypes.add(row[field.link_name] + ":" + field.fieldname);
				}
			});
		});

		doctypes = doctypes.concat(
			Array.from(dynamic_doctypes).map((d) => {
				const doc_field_pair = d.split(":");
				return {
					doctype: doc_field_pair[0],
					fieldname: doc_field_pair[1],
				};
			})
		);

		doctypes.forEach((doc) => {
			this.doctype_field_map[doc.doctype] = { fieldname: doc.fieldname, names: new Set() };
		});

		this.data.forEach((row) => {
			doctypes.forEach((doc) => {
				this.doctype_field_map[doc.doctype].names.add(row[doc.fieldname]);
			});
		});

		return doctypes;
	}

	setup_report_wrapper() {
		if (this.$report) return;

		// Remove border from
		$(".page-head-content").removeClass("border-bottom");

		let page_form = this.page.main.find(".page-form");
		this.$status = $(`<div class="form-message text-muted small"></div>`)
			.hide()
			.insertAfter(page_form);

		this.$summary = $(`<div class="report-summary"></div>`).hide().appendTo(this.page.main);

		this.$chart = $('<div class="chart-wrapper">').hide().appendTo(this.page.main);

		this.$loading = $(this.message_div("")).hide().appendTo(this.page.main);
		this.$report = $('<div class="report-wrapper">').appendTo(this.page.main);
		this.$message = $(this.message_div("")).hide().appendTo(this.page.main);
	}

	show_status(status_message) {
		this.$status.html(status_message).show();
	}

	hide_status() {
		this.$status.hide();
	}

	show_footer_message() {
		this.$report_footer && this.$report_footer.remove();
		this.$report_footer = $(`<div class="report-footer text-muted"></div>`).appendTo(
			this.page.main
		);
		if (this.tree_report) {
			this.$tree_footer = $(`<div class="tree-footer col-md-3">
				<div class="input-group">
				  <input id="tree-level" type="number" class="form-control" aria-label="Tree Level" value="2">
					<button class="btn btn-xs btn-secondary" data-action="set_tree_level">
						${__("Set Level")}</button>
					<button class="btn btn-xs btn-secondary" data-action="expand_all_rows">
						${__("Expand All")}</button>
					<button class="btn btn-xs btn-secondary" data-action="collapse_all_rows">
						${__("Collapse All")}</button>
				</div>
			</div>`);
			$(this.$report_footer).append(this.$tree_footer);
			this.$tree_footer.find("[data-action=collapse_all_rows]").show();
			this.$tree_footer.find("[data-action=expand_all_rows]").hide();
		}

		const message = __(
			"For comparison, use >5, <10 or =324. For ranges, use 5:10 (for values between 5 & 10)."
		);
		const execution_time_msg = __("Execution Time: {0} sec", [this.execution_time || 0.1]);

		this.$report_footer.append(`<div class="col-md-12">
			<span">${message}</span><span class="pull-right">${execution_time_msg}</span>
		</div>`);
	}

	expand_all_rows() {
		this.$tree_footer.find("[data-action=expand_all_rows]").hide();
		let rows = this.datatable.rowmanager.datamanager.getRows();
		let maxDepth = rows.reduce((max, row) => {
			return Math.max(max, row.meta.indent || 0);
		}, 0);
		var treeLevel = maxDepth + 1;
		this.$tree_footer.find("#tree-level").val(treeLevel);
		this.datatable.rowmanager.expandAllNodes();
		this.$tree_footer.find("[data-action=collapse_all_rows]").show();
	}

	collapse_all_rows() {
		this.$tree_footer.find("[data-action=collapse_all_rows]").hide();
		this.$tree_footer.find("#tree-level").val(1);
		this.datatable.rowmanager.collapseAllNodes();
		this.$tree_footer.find("[data-action=expand_all_rows]").show();
	}

	set_tree_level() {
		var inputVal = parseInt(this.$tree_footer.find("#tree-level").val(), 10) || 0;
		let rows = this.datatable.rowmanager.datamanager.getRows();
		let maxDepth = rows.reduce((max, row) => {
			return Math.max(max, row.meta.indent || 0);
		}, 0);
		var treeLevel = Math.min(maxDepth + 1, Math.max(1, inputVal));
		var treeDepth = treeLevel - 1;
		this.$tree_footer.find("#tree-level").val(treeLevel);
		if (treeDepth === 0) {
			this.$tree_footer.find("[data-action=collapse_all_rows]").hide();
		} else {
			this.$tree_footer.find("[data-action=collapse_all_rows]").show();
		}
		this.datatable.rowmanager.setTreeDepth(treeDepth);
		if (treeDepth === 0) {
			this.$tree_footer.find("[data-action=expand_all_rows]").show();
		} else {
			this.$tree_footer.find("[data-action=expand_all_rows]").hide();
		}
	}

	message_div(message) {
		return `<div class='flex justify-center align-center text-muted' style='height: calc(100vh - 280px);'>
			<div>${message}</div>
		</div>`;
	}

	toggle_nothing_to_show(flag) {
		let message =
			this.prepared_report && !this.prepared_report_document
				? __(
						"This is a background report. Please set the appropriate filters and then generate a new one."
				  )
				: this.get_no_result_message();

		this.toggle_message(flag, message);

		if (flag && this.prepared_report) {
			if (!this.primary_button.is(":visible")) {
				this.add_prepared_report_buttons();
			}
		}
	}

	toggle_message(flag, message) {
		if (flag) {
			this.$message.find("div").html(message);
			this.$message.show();
		} else {
			this.$message.hide();
		}
	}

	toggle_filter_display(fieldname, flag) {
		this.$page.find(`div[data-fieldname=${fieldname}]`).toggleClass("hide-control", flag);
	}

	toggle_report(flag) {
		this.$report.toggle(flag);
		this.$chart.toggle(flag);
		this.$summary.toggle(flag);
	}

	get_checked_items(only_docnames) {
		const indexes = this.datatable.rowmanager.getCheckedRows();

		return indexes.reduce((items, i) => {
			if (i === undefined) return items;

			const item = this.data[i];
			items.push(only_docnames ? item.name : item);
			return items;
		}, []);
	}

	// backward compatibility
	get get_values() {
		return this.get_filter_values;
	}

	add_translate_data_checkbox() {
		if (this.report_doc.add_translate_data) {
			let filter_config = {
				fieldname: "translate_data",
				fieldtype: "Check",
				label: __("Translate Data"),
			};
			this.report_settings.filters.push(filter_config);
		}
	}
};
