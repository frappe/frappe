from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
        {
			"label": _("Customize"),
			"icon": "fa fa-glass",
			"items": [
				{
					"type": "doctype",
					"name": "Customize Form",
					"description": _("Change field properties (hide, readonly, permission etc.)")
				},
				{
					"type": "doctype",
					"name": "Custom Field",
					"description": _("Add fields to forms.")
				},
				{
					"type": "doctype",
					"label": _("Custom Translations"),
					"name": "Translation",
					"description": _("Add your own translations")
				},
				{
					"type": "doctype",
					"name": "Custom Script",
					"description": _("Add custom javascript to forms.")
				},
				{
					"type": "doctype",
					"name": "DocType",
					"description": _("Add custom forms.")
				},
				{
					"type": "doctype",
					"label": _("Custom Tags"),
					"name": "Tag Category",
					"description": _("Add your own Tag Categories")
				}
			]
		},
	]
