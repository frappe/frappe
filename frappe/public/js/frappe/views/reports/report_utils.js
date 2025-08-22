frappe.provide("frappe.report_utils");

frappe.report_utils = {
	make_chart_options: function (
		columns,
		raw_data,
		{ y_fields, x_field, chart_type, colors, height }
	) {
		const type = chart_type.toLowerCase();

		let rows = raw_data.result.filter((value) => Object.keys(value).length);

		let labels = get_column_values(x_field);
		let datasets = y_fields.map((y_field) => ({
			name: get_translated_column_label(y_field),
			values: get_column_values(y_field).map((d) => Number(d)),
		}));

		if (raw_data.add_total_row) {
			labels = labels.slice(0, -1);
			datasets.forEach((dataset) => {
				dataset.values = dataset.values.slice(0, -1);
			});
		}

		return {
			data: {
				labels: labels.length ? labels : null,
				datasets: datasets,
			},
			truncateLegends: 1,
			type: type,
			height: height ? height : 280,
			colors: colors,
			axisOptions: {
				shortenYAxisNumbers: 1,
				xAxisMode: "tick",
				numberFormatter: frappe.utils.format_chart_axis_number,
			},
		};

		function get_column_values(column_name) {
			if (Array.isArray(rows[0])) {
				let column_index = columns.findIndex((column) => column.fieldname == column_name);
				return rows.map((row) => row[column_index]);
			} else {
				return rows.map((row) => row[column_name]);
			}
		}

		function get_translated_column_label(fieldname) {
			let column = columns.find((column) => column.fieldname === fieldname);
			return column?.label ?? __(frappe.model.unscrub(fieldname));
		}
	},

	get_field_options_from_report: function (columns, data) {
		const rows = data.result.filter((value) => Object.keys(value).length);
		const first_row = Array.isArray(rows[0])
			? rows[0]
			: columns.map((col) => rows[0][col.fieldname]);

		const indices = first_row.reduce((accumulator, current_value, current_index) => {
			if (Number.isFinite(current_value)) {
				accumulator.push(current_index);
			}
			return accumulator;
		}, []);

		function get_options(fields) {
			return fields.map((field) => {
				if (field.fieldname) {
					return { label: field.label, value: field.fieldname };
				} else {
					field = frappe.report_utils.prepare_field_from_column(field);
					return { label: field.label, value: field.fieldname };
				}
			});
		}

		const numeric_fields = columns.filter((col, i) => indices.includes(i));
		const non_numeric_fields = columns.filter((col, i) => !indices.includes(i));

		let numeric_field_options = get_options(numeric_fields);
		let non_numeric_field_options = get_options(non_numeric_fields);

		return {
			numeric_fields: numeric_field_options,
			non_numeric_fields: non_numeric_field_options,
		};
	},

	prepare_field_from_column: function (column) {
		if (typeof column === "string") {
			if (column.includes(":")) {
				let [label, fieldtype, width] = column.split(":");
				let options;

				if (fieldtype.includes("/")) {
					[fieldtype, options] = fieldtype.split("/");
				}

				column = {
					label,
					fieldname: label,
					fieldtype,
					width,
					options,
				};
			} else {
				column = {
					label: column,
					fieldname: column,
					fieldtype: "Data",
				};
			}
		}
		return column;
	},

	get_report_filters: function (report_name) {
		if (frappe.query_reports[report_name]) {
			let filters = frappe.query_reports[report_name].filters;
			return Promise.resolve(filters);
		}

		return frappe
			.xcall("frappe.desk.query_report.get_script", {
				report_name: report_name,
			})
			.then((r) => {
				frappe.dom.eval(r.script || "");
				return frappe.after_ajax(() => {
					if (
						frappe.query_reports[report_name] &&
						!frappe.query_reports[report_name].filters &&
						r.filters
					) {
						return (frappe.query_reports[report_name].filters = r.filters);
					}
					return (
						frappe.query_reports[report_name] &&
						frappe.query_reports[report_name].filters
					);
				});
			});
	},

	get_filter_values(filters) {
		return filters
			.map((f) => {
				var v = f.default;
				return {
					[f.fieldname]: v,
				};
			})
			.reduce((acc, f) => {
				Object.assign(acc, f);
				return acc;
			}, {});
	},

	get_result_of_fn(fn, values) {
		const get_result = {
			Minimum: (values) => values.reduce((min, val) => Math.min(min, val), values[0]),
			Maximum: (values) => values.reduce((min, val) => Math.max(min, val), values[0]),
			Average: (values) => values.reduce((a, b) => a + b, 0) / values.length,
			Sum: (values) => values.reduce((a, b) => a + b, 0),
		};
		return get_result[fn](values);
	},

	get_export_dialog(report_name, extra_fields, callback) {
		const fields = [
			{
				label: "File Format",
				fieldname: "file_format",
				fieldtype: "Select",
				options: ["Excel", "CSV"],
				default: "Excel",
				reqd: 1,
			},
			{
				fieldtype: "Section Break",
				fieldname: "csv_settings",
				label: "Settings",
				collapsible: 1,
				depends_on: "eval:doc.file_format=='CSV'",
			},
			{
				fieldtype: "Data",
				label: "CSV Delimiter",
				fieldname: "csv_delimiter",
				default: ",",
				length: 1,
				depends_on: "eval:doc.file_format=='CSV'",
			},
			{
				fieldtype: "Select",
				label: "CSV Quoting",
				fieldname: "csv_quoting",
				options: [
					{ value: 0, label: "Minimal" },
					{ value: 1, label: "All" },
					{ value: 2, label: "Non-numeric" },
					{ value: 3, label: "None" },
				],
				default: 2,
				depends_on: "eval:doc.file_format=='CSV'",
			},
			{
				fieldtype: "Data",
				label: "CSV Decimal Separator",
				fieldname: "csv_decimal_sep",
				default: ".",
				length: 1,
				depends_on: "eval:doc.file_format=='CSV' && doc.csv_quoting != 2",
			},
			{
				fieldtype: "Small Text",
				label: "CSV Preview",
				fieldname: "csv_preview",
				read_only: 1,
				depends_on: "eval:doc.file_format=='CSV'",
			},
		];

		if (extra_fields) {
			fields.push(
				{
					fieldtype: "Section Break",
					fieldname: "extra_fields",
					collapsible: 0,
				},
				...extra_fields
			);
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Export Report: {0}", [report_name], "Export report"),
			fields: fields,
			primary_action_label: __("Download", null, "Export report"),
			primary_action: callback,
		});

		function update_csv_preview(dialog) {
			const is_query_report = frappe.get_route()[0] === "query-report";
			const report = is_query_report ? frappe.query_report : cur_list;
			const columns = report.columns.filter((col) => col.hidden !== 1);
			let PREVIEW_DATA = [
				columns.map((col) => __(is_query_report ? col.label : col.name)),
				...report.data
					.slice(0, 3)
					.map((row) =>
						columns.map((col) => row[is_query_report ? col.fieldname : col.field])
					),
			];

			dialog.set_value(
				"csv_preview",
				frappe.report_utils.get_csv_preview(
					PREVIEW_DATA,
					dialog.get_value("csv_quoting"),
					dialog.get_value("csv_delimiter"),
					dialog.get_value("csv_decimal_sep")
				)
			);
		}

		dialog.fields_dict["file_format"].df.onchange = () => update_csv_preview(dialog);
		dialog.fields_dict["csv_quoting"].df.onchange = () => update_csv_preview(dialog);
		dialog.fields_dict["csv_delimiter"].df.onchange = () => {
			if (!dialog.get_value("csv_delimiter")) {
				dialog.set_value("csv_delimiter", ",");
			}
			update_csv_preview(dialog);
		};
		dialog.fields_dict["csv_decimal_sep"].df.onchange = () => {
			if (!dialog.get_value("csv_decimal_sep")) {
				dialog.set_value("csv_decimal_sep", ".");
			}
			update_csv_preview(dialog);
		};

		return dialog;
	},

	get_csv_preview(data, quoting, delimiter, decimal_sep) {
		// data: array of arrays
		// quoting: 0 - minimal, 1 - all, 2 - non-numeric, 3 - none
		// delimiter: any single character
		quoting = cint(quoting);
		const QUOTING = {
			Minimal: 0,
			All: 1,
			NonNumeric: 2,
			None: 3,
		};

		if (delimiter.length > 1) {
			frappe.throw(__("Delimiter must be a single character"));
		}

		if (decimal_sep.length > 1) {
			frappe.throw(__("Decimal Separator must be a single character"));
		}

		if (0 > quoting || quoting > 3) {
			frappe.throw(__("Quoting must be between 0 and 3"));
		}

		if (decimal_sep !== "." && quoting === QUOTING.NonNumeric) {
			frappe.throw(__("Decimal Separator must be '.' when Quoting is set to Non-numeric"));
		}

		return data
			.map((row) => {
				return row
					.map((col) => {
						if (col === null) {
							return "";
						}

						if (typeof col == "string" && col.includes('"')) {
							col = col.replace(/"/g, '""');
						}

						if (typeof col == "number" && decimal_sep !== ".") {
							col = col.toString().replace(".", decimal_sep);
						}

						switch (quoting) {
							case QUOTING.Minimal:
								return typeof col === "string" && col.includes(delimiter)
									? `"${col}"`
									: `${col}`;
							case QUOTING.All:
								return `"${col}"`;
							case QUOTING.NonNumeric:
								return isNaN(col) ? `"${col}"` : `${col}`;
							case QUOTING.None:
								return `${col}`;
						}
					})
					.join(delimiter);
			})
			.join("\n");
	},
};
