from frappe import _

def get_data():
	return [{
		"label": _("Settings"),
		"icon": "fa fa-wrench",
		"items": [
			{
				"type": "doctype",
				"name": "System Settings",
				"label": _("System Settings"),
				"description": _("Language, Date and Time settings"),
				"hide_count": True
			},
			{
				"type": "doctype",
				"name": "Error Log",
				"description": _("Log of error on automated events (scheduler).")
			},
			{
				"type": "doctype",
				"name": "Error Snapshot",
				"description": _("Log of error during requests.")
			},
			{
				"type": "doctype",
				"name": "Domain Settings",
				"label": _("Domain Settings"),
				"description": _("Enable / Disable Domains"),
				"hide_count": True
			},
		]
	}]
