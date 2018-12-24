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
				"name": "Domain Settings",
				"label": _("Domain Settings"),
				"description": _("Enable / Disable Domains"),
				"hide_count": True
			},
			{
				"type": "doctype",
				"name": "Print Settings",
				"label": _("Print Settings"),
				"description": _("Print Style, PDF Size"),
				"hide_count": True
			},
			{
				"type": "doctype",
				"name": "Website Settings",
				"label": _("Website Settings"),
				"description": _("Landing Page, Website Theme, Brand Setup and more"),
				"hide_count": True
			},
			{
				"type": "doctype",
				"name": "S3 Backup Settings",
				"label": _("S3 Backup Settings"),
				"description": _("Enable / Disable Backup, Backup Frequency"),
				"hide_count": True
			},
			{
				"type": "doctype",
				"name": "SMS Settings",
				"label": _("SMS Settings"),
				"description": _("SMS Gateway URL, Message & Receiver Parameter"),
				"hide_count": True
			}
		]
	}]
