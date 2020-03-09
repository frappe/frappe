import frappe
import json
from six import string_types

def execute():
	__usersettings = frappe.db.sql("""SELECT * FROM __UserSettings""", as_dict=True)

	user_settings_fields = ["name", "user", "document_type", "last_view", "updated_on"]
	user_settings = []

	user_view_settings_fields = ["name", "view", "sort_by", "sort_order", "document_type", "filters", "fields",
		"parenttype", "parent", "parentfield", "creation", "modified", "modified_by"]
	user_view_settings = []
	datetime = frappe.utils.get_datetime_str(frappe.utils.now_datetime())

	for _usersettings in __usersettings:
		settings = json.loads(_usersettings.get("data"))

		name = "{0}-{1}".format(_usersettings.get("doctype"), _usersettings.get("user"))
		user_settings.append((
			name,
			_usersettings.get("user"),
			_usersettings.get("doctype"),
			settings.get("last_view"),
			settings.get("created_on")
		))

		for view in ['List', 'Gantt', 'Kanban', 'Calendar', 'Image', 'Inbox', 'Report']:
			if not settings.get(view):
				continue

			view_data = settings.get(view)
			if isinstance(view_data, string_types):
				view_data = json.loads(view_data)

			user_view_settings.append((
				frappe.generate_hash(view+name+_usersettings.get("user")+_usersettings.get("doctype")),
				view,
				view_data.get("sort_by"),
				view_data.get("sort_order"),
				_usersettings.get("doctype"),
				json.dumps(view_data.get("filters")),
				json.dumps(view_data.get("fields")),
				"User Settings",
				name,
				"views",
				datetime,
				datetime,
				"Administrator"
			))

	frappe.db.bulk_insert("User Settings", user_settings_fields, user_settings)
	frappe.db.bulk_insert("User View Settings", user_view_settings_fields, user_view_settings, True)