// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.query_reports["Permitted Documents For User"] = {
	filters: [
		{
			fieldname: "doctype",
			get_query: function () {
				return {
					query: "frappe.core.report.permitted_documents_for_user.permitted_documents_for_user.query_doctypes",
					filters: {
						user: frappe.query_report.get_filter_value("user"),
					},
				};
			},
		},
	],
};
