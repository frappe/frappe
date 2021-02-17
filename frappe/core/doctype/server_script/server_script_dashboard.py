# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from frappe import _


def get_data():
	return {
		"fieldname": "server_script",
		"transactions": [
			{"label": _("Scheduled Jobs"), "items": ["Scheduled Job Type"]},
		],
	}
