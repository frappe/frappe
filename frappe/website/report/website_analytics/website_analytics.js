// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Website Analytics"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.now_date(), -100),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.now_date(),
		},
		{
			fieldname: "range",
			label: __("Range"),
			fieldtype: "Select",
			options: [
				{ value: "Daily", label: __("Daily") },
				{ value: "Weekly", label: __("Weekly") },
				{ value: "Monthly", label: __("Monthly") },
			],
			default: "Daily",
			reqd: 1,
		},
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: [
				{ value: "path", label: __("Path") },
				{ value: "browser", label: __("Browser") },
				{ value: "referrer", label: __("Referrer") },
				{ value: "source", label: __("Source") },
				{ value: "campaign", label: __("Campaign") },
				{ value: "medium", label: __("Medium") },
				{ value: "content", label: __("Content") },
			],
			default: "path",
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		const group_by = frappe.query_report.get_filter_value("group_by");

		if (column.id !== group_by) {
			return default_formatter(value, row, column, data);
		}

		if (!value) {
			return group_by === "source"
				? `<i>${__("Unknown")}</i>`
				: default_formatter(value, row, column, data);
		}

		const escaped_value = frappe.utils.escape_html(value);

		if (group_by === "source") {
			const [doctype, name] = String(value).split(">");
			if (doctype && name) {
				return frappe.utils.get_form_link(
					doctype.trim(),
					name.trim(),
					true,
					escaped_value
				);
			}
		}

		return default_formatter(escaped_value, row, column, data);
	},
};
