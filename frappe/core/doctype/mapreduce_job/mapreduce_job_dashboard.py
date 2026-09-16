from frappe import _


def get_data():
	return {
		"fieldname": "master",
		"transactions": [
			{"label": _("Tasks"), "items": ["MapReduce Task"]},
		],
	}
