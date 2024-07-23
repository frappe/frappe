// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.provide("frappe.dashboards.chart_sources");

frappe.ui.form.on("Dashboard Chart", {
	setup: function (frm) {
		// fetch timeseries from source
		frm.add_fetch("source", "timeseries", "timeseries");
	},

	before_save: function (frm) {
		let dynamic_filters = JSON.parse(frm.doc.dynamic_filters_json || "null");
		let static_filters = JSON.parse(frm.doc.filters_json || "null");
		static_filters = frappe.dashboard_utils.remove_common_static_filter_values(
			static_filters,
			dynamic_filters
		);

		frm.set_value("filters_json", JSON.stringify(static_filters));
		frm.trigger("show_filters");
	},

	refresh: function (frm) {
		frm.chart_filters = null;
		frm.is_disabled = !frappe.boot.developer_mode && frm.doc.is_standard;

		if (frm.is_disabled) {
			!frm.doc.custom_options && frm.set_df_property("chart_options_section", "hidden", 1);
			frm.disable_form();
		}

		if (!frm.is_new()) {
			frm.add_custom_button("Add Chart to Dashboard", () => {
				const dialog = frappe.dashboard_utils.get_add_to_dashboard_dialog(
					frm.doc.name,
					"Dashboard Chart",
					"frappe.desk.doctype.dashboard_chart.dashboard_chart.add_chart_to_dashboard"
				);

				if (!frm.doc.chart_name) {
					frappe.msgprint(__("Please create chart first"));
				} else {
					dialog.show();
				}
			});
		}

		frm.set_df_property("filters_section", "hidden", 1);
		frm.set_df_property("dynamic_filters_section", "hidden", 1);

		frm.trigger("set_parent_document_type");
		frm.trigger("set_time_series");
		frm.set_query("document_type", function () {
			return {
				filters: {
					issingle: false,
				},
			};
		});
		frm.trigger("update_options");
		frm.trigger("set_heatmap_year_options");
		if (frm.doc.report_name) {
			frm.trigger("set_chart_report_filters");
		}
	},

	is_standard: function (frm) {
		if (frappe.boot.developer_mode && frm.doc.is_standard) {
			frm.trigger("render_dynamic_filters_table");
		} else {
			frm.set_df_property("dynamic_filters_section", "hidden", 1);
		}
	},

	source: function (frm) {
		frm.trigger("show_filters");
	},

	set_heatmap_year_options: function (frm) {
		if (frm.doc.type == "Heatmap") {
			frappe.db.get_doc("System Settings").then((doc) => {
				const creation_date = doc.creation;
				frm.set_df_property(
					"heatmap_year",
					"options",
					frappe.dashboard_utils.get_years_since_creation(creation_date)
				);
			});
		}
	},

	chart_type: function (frm) {
		frm.trigger("set_time_series");
		if (frm.doc.chart_type == "Report") {
			frm.set_query("report_name", () => {
				return {
					filters: {
						report_type: ["!=", "Report Builder"],
					},
				};
			});
		} else {
			frm.set_value("document_type", "");
		}
	},

	set_time_series: function (frm) {
		// set timeseries based on chart type
		if (["Count", "Average", "Sum"].includes(frm.doc.chart_type)) {
			frm.set_value("timeseries", 1);
		} else if (frm.doc.chart_type == "Custom") {
			return;
		} else {
			frm.set_value("timeseries", 0);
		}
	},

	document_type: function (frm) {
		// update `based_on` options based on date / datetime fields
		frm.set_value("source", "");
		frm.set_value("based_on", "");
		frm.set_value("value_based_on", "");
		frm.set_value("parent_document_type", "");
		frm.set_value("filters_json", "[]");
		frm.set_value("dynamic_filters_json", "[]");
		frm.trigger("update_options");
		frm.trigger("set_parent_document_type");
	},

	report_name: function (frm) {
		frm.set_value("x_field", "");
		frm.set_value("y_axis", []);
		frm.set_df_property("x_field", "options", []);
		frm.set_value("filters_json", "{}");
		frm.set_value("dynamic_filters_json", "{}");
		frm.set_value("use_report_chart", 0);
		frm.trigger("set_chart_report_filters");
	},

	set_chart_report_filters: function (frm) {
		let report_name = frm.doc.report_name;

		if (report_name) {
			if (frm.doc.filters_json.length > 2) {
				frm.trigger("show_filters");
				frm.trigger("set_chart_field_options");
			} else {
				frappe.report_utils.get_report_filters(report_name).then((filters) => {
					if (filters) {
						frm.chart_filters = filters;
						let filter_values = frappe.report_utils.get_filter_values(filters);
						frm.set_value("filters_json", JSON.stringify(filter_values));
					}
					frm.trigger("show_filters");
					frm.trigger("set_chart_field_options");
				});
			}
		}
	},

	use_report_chart: function (frm) {
		!frm.doc.use_report_chart && frm.trigger("set_chart_field_options");
	},

	set_chart_field_options: function (frm) {
		let filters = frm.doc.filters_json.length > 2 ? JSON.parse(frm.doc.filters_json) : null;
		if (frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2) {
			filters = frappe.dashboard_utils.get_all_filters(frm.doc);
		}
		frappe
			.xcall("frappe.desk.query_report.run", {
				report_name: frm.doc.report_name,
				filters: filters,
				ignore_prepared_report: 1,
			})
			.then((data) => {
				frm.report_data = data;
				let report_has_chart = Boolean(data.chart);

				frm.set_df_property("use_report_chart", "hidden", !report_has_chart);

				if (!frm.doc.use_report_chart) {
					if (data.result.length) {
						frm.field_options = frappe.report_utils.get_field_options_from_report(
							data.columns,
							data
						);
						frm.set_df_property(
							"x_field",
							"options",
							frm.field_options.non_numeric_fields
						);
						if (!frm.field_options.numeric_fields.length) {
							frappe.msgprint(
								__("Report has no numeric fields, please change the Report Name")
							);
						} else {
							let y_field_df = frappe.meta.get_docfield(
								"Dashboard Chart Field",
								"y_field",
								frm.doc.name
							);
							y_field_df.options = frm.field_options.numeric_fields;
						}
					} else {
						frappe.msgprint(
							__(
								"Report has no data, please modify the filters or change the Report Name"
							)
						);
					}
				} else {
					frm.set_value("use_report_chart", 1);
					frm.set_df_property("use_report_chart", "hidden", false);
				}
			});
	},

	timespan: function (frm) {
		const time_interval_options = {
			"Select Date Range": ["Quarterly", "Monthly", "Weekly", "Daily"],
			"All Time": ["Yearly", "Monthly"],
			"Last Year": ["Quarterly", "Monthly", "Weekly", "Daily"],
			"Last Quarter": ["Monthly", "Weekly", "Daily"],
			"Last Month": ["Weekly", "Daily"],
			"Last Week": ["Daily"],
		};
		if (frm.doc.timespan) {
			frm.set_df_property(
				"time_interval",
				"options",
				time_interval_options[frm.doc.timespan]
			);
		}
	},

	update_options: function (frm) {
		let doctype = frm.doc.document_type;
		let date_fields = [
			{ label: __("Created On"), value: "creation" },
			{ label: __("Last Modified On"), value: "modified" },
		];
		let value_fields = [];
		let group_by_fields = [{ label: "Created By", value: "owner" }];
		let aggregate_function_fields = [];
		let update_form = function () {
			// update select options
			frm.set_df_property("based_on", "options", date_fields);
			frm.set_df_property("value_based_on", "options", value_fields);
			frm.set_df_property("group_by_based_on", "options", group_by_fields);
			frm.set_df_property(
				"aggregate_function_based_on",
				"options",
				aggregate_function_fields
			);
			frm.trigger("show_filters");
		};

		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				// get all date and datetime fields
				frappe.get_meta(doctype).fields.map((df) => {
					if (["Date", "Datetime"].includes(df.fieldtype)) {
						date_fields.push({ label: df.label, value: df.fieldname });
					}
					if (
						["Int", "Float", "Currency", "Percent", "Duration"].includes(df.fieldtype)
					) {
						value_fields.push({ label: df.label, value: df.fieldname });
						aggregate_function_fields.push({ label: df.label, value: df.fieldname });
					}
					if (["Link", "Select"].includes(df.fieldtype)) {
						group_by_fields.push({ label: df.label, value: df.fieldname });
					}
				});
				update_form();
			});
		} else {
			// update select options
			update_form();
		}
	},

	show_filters: function (frm) {
		frm.chart_filters = [];
		frappe.dashboard_utils.get_filters_for_chart_type(frm.doc).then((filters) => {
			if (filters) {
				frm.chart_filters = filters;
			}
			frm.trigger("render_filters_table");

			if (frappe.boot.developer_mode && frm.doc.is_standard) {
				frm.trigger("render_dynamic_filters_table");
			}
		});
	},

	render_filters_table: function (frm) {
		frm.set_df_property("filters_section", "hidden", 0);
		let is_document_type = frm.doc.chart_type !== "Report" && frm.doc.chart_type !== "Custom";
		let is_dynamic_filter = (f) => ["Date", "DateRange"].includes(f.fieldtype) && f.default;

		let wrapper = $(frm.get_field("filters_json").wrapper).empty();
		let table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th style="width: 20%">${__("Filter")}</th>
					<th style="width: 20%">${__("Condition")}</th>
					<th>${__("Value")}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);
		$(`<p class="text-muted small">${__("Click table to edit")}</p>`).appendTo(wrapper);

		let filters = JSON.parse(frm.doc.filters_json || "[]");
		var filters_set = false;

		// Set dynamic filters for reports
		if (frm.doc.chart_type == "Report") {
			let set_filters = false;
			frm.chart_filters.forEach((f) => {
				if (is_dynamic_filter(f)) {
					filters[f.fieldname] = f.default;
					set_filters = true;
				}
			});
			set_filters && frm.set_value("filters_json", JSON.stringify(filters));
		}

		let fields = [];
		if (is_document_type) {
			fields = [
				{
					fieldtype: "HTML",
					fieldname: "filter_area",
				},
			];

			if (filters.length > 0) {
				filters.forEach((filter) => {
					const filter_row = $(`<tr>
							<td>${filter[1]}</td>
							<td>${filter[2] || ""}</td>
							<td>${filter[3]}</td>
						</tr>`);

					table.find("tbody").append(filter_row);
					filters_set = true;
				});
			}
		} else if (frm.chart_filters.length) {
			fields = frm.chart_filters.filter((f) => f.fieldname);

			fields.map((f) => {
				if (filters[f.fieldname]) {
					let condition = "=";
					const filter_row = $(`<tr>
							<td>${f.label}</td>
							<td>${condition}</td>
							<td>${filters[f.fieldname] || ""}</td>
						</tr>`);

					table.find("tbody").append(filter_row);
					filters_set = true;
				}
			});
		}

		if (!filters_set) {
			const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
				${__("Click to Set Filters")}</td></tr>`);
			table.find("tbody").append(filter_row);
		}

		table.on("click", () => {
			frm.is_disabled && frappe.throw(__("Cannot edit filters for standard charts"));

			let dialog = new frappe.ui.Dialog({
				title: __("Set Filters"),
				fields: fields.filter((f) => !is_dynamic_filter(f)),
				primary_action: function () {
					let values = this.get_values();
					if (values) {
						this.hide();
						if (is_document_type) {
							let filters = frm.filter_group.get_filters();
							frm.set_value("filters_json", JSON.stringify(filters));
						} else {
							frm.set_value("filters_json", JSON.stringify(values));
						}

						frm.trigger("show_filters");
						if (frm.doc.chart_type == "Report") {
							frm.trigger("set_chart_report_filters");
						}
					}
				},
				primary_action_label: __("Set"),
			});
			frappe.dashboards.filters_dialog = dialog;

			if (is_document_type) {
				frm.filter_group = new frappe.ui.FilterGroup({
					parent: dialog.get_field("filter_area").$wrapper,
					doctype: frm.doc.document_type,
					parent_doctype: frm.doc.parent_document_type,
					on_change: () => {},
				});

				frm.filter_group.add_filters_to_filter_group(filters);
			}

			dialog.show();

			if (frm.doc.chart_type == "Report") {
				//Set query report object so that it can be used while fetching filter values in the report
				frappe.query_report = new frappe.views.QueryReport({
					filters: dialog.fields_list,
				});
				frappe.query_reports[frm.doc.report_name] &&
					frappe.query_reports[frm.doc.report_name].onload &&
					frappe.query_reports[frm.doc.report_name].onload(frappe.query_report);
			}

			dialog.set_values(filters);
		});
	},

	render_dynamic_filters_table(frm) {
		frm.set_df_property("dynamic_filters_section", "hidden", 0);

		let is_document_type = frm.doc.chart_type !== "Report" && frm.doc.chart_type !== "Custom";

		let wrapper = $(frm.get_field("dynamic_filters_json").wrapper).empty();

		frm.dynamic_filter_table =
			$(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th style="width: 20%">${__("Filter")}</th>
					<th style="width: 20%">${__("Condition")}</th>
					<th>${__("Value")}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);

		frm.dynamic_filters =
			frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2
				? JSON.parse(frm.doc.dynamic_filters_json)
				: null;

		frm.trigger("set_dynamic_filters_in_table");

		let filters = JSON.parse(frm.doc.filters_json || "[]");

		let fields = frappe.dashboard_utils.get_fields_for_dynamic_filter_dialog(
			is_document_type,
			filters,
			frm.dynamic_filters
		);

		frm.dynamic_filter_table.on("click", () => {
			let dialog = new frappe.ui.Dialog({
				title: __("Set Dynamic Filters"),
				fields: fields,
				primary_action: () => {
					let values = dialog.get_values();
					dialog.hide();
					let dynamic_filters = [];
					for (let key of Object.keys(values)) {
						if (is_document_type) {
							let [doctype, fieldname] = key.split(":");
							dynamic_filters.push([doctype, fieldname, "=", values[key]]);
						}
					}

					if (is_document_type) {
						frm.set_value("dynamic_filters_json", JSON.stringify(dynamic_filters));
					} else {
						frm.set_value("dynamic_filters_json", JSON.stringify(values));
					}
					frm.trigger("set_dynamic_filters_in_table");
				},
				primary_action_label: __("Set"),
			});

			dialog.show();
			dialog.set_values(frm.dynamic_filters);
		});
	},

	set_dynamic_filters_in_table: function (frm) {
		frm.dynamic_filters =
			frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2
				? JSON.parse(frm.doc.dynamic_filters_json)
				: null;

		if (!frm.dynamic_filters) {
			const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
				${__("Click to Set Dynamic Filters")}</td></tr>`);
			frm.dynamic_filter_table.find("tbody").html(filter_row);
		} else {
			let filter_rows = "";
			if ($.isArray(frm.dynamic_filters)) {
				frm.dynamic_filters.forEach((filter) => {
					filter_rows += `<tr>
							<td>${filter[1]}</td>
							<td>${filter[2] || ""}</td>
							<td>${filter[3]}</td>
						</tr>`;
				});
			} else {
				let condition = "=";
				for (let [key, val] of Object.entries(frm.dynamic_filters)) {
					filter_rows += `<tr>
							<td>${key}</td>
							<td>${condition}</td>
							<td>${val || ""}</td>
						</tr>`;
				}
			}

			frm.dynamic_filter_table.find("tbody").html(filter_rows);
		}
	},

	set_parent_document_type: async function (frm) {
		let document_type = frm.doc.document_type;
		if (!document_type) {
			frm.set_df_property("parent_document_type", "hidden", 1);
			return;
		}
		frappe.model.with_doctype(document_type, async () => {
			let doc_is_table = frappe.get_meta(document_type).istable;
			frm.set_df_property("parent_document_type", "hidden", !doc_is_table);

			if (doc_is_table) {
				let parents = await frappe.xcall(
					"frappe.desk.doctype.dashboard_chart.dashboard_chart.get_parent_doctypes",
					{ child_type: document_type }
				);

				frm.set_query("parent_document_type", function () {
					return {
						filters: {
							name: ["in", parents],
						},
					};
				});

				if (parents.length === 1) {
					frm.set_value("parent_document_type", parents[0]);
				}
			}
		});
	},
});
