// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.views.calendar["ToDo"] = {
	field_map: {
		"start": "date",
		"end": "date",
		"id": "name",
		"title": "description",
		"allDay": "allDay",
		"progress": "progress"
	},
	gantt: true,
	filters: [
		{
			"fieldtype": "Link",
			"fieldname": "reference_type",
			"options": "Task",
			"label": __("Task")
		},
		{
			"fieldtype": "Dynamic Link",
			"fieldname": "reference_name",
			"options": "reference_type",
			"label": __("Task")
		}

	],
	get_events_method: "frappe.desk.calendar.get_events"
};

