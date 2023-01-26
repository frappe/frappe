import json

import frappe
from frappe.model.utils.user_settings import sync_user_settings, update_user_settings


def execute():
	users = frappe.db.sql("select distinct(user) from `__UserSettings`", as_dict=True)

	for user in users:
		user_settings = frappe.db.sql(
			"""
			select
				* from `__UserSettings`
			where
				user='{user}'
		""".format(
				user=user.user
			),
			as_dict=True,
		)

		for setting in user_settings:
			data = frappe.parse_json(setting.get("data"))
			if data:
				for key in data:
					update_user_setting_filters(data, key, setting)

	sync_user_settings()


def update_user_setting_filters(data, key, user_setting):
	timespan_map = {
		"1 week": "week",
		"1 month": "month",
		"3 months": "quarter",
		"6 months": "6 months",
		"1 year": "year",
	}

	period_map = {"Previous": "last", "Next": "next"}

	if data.get(key):
		update = False
		if isinstance(data.get(key), dict):
			filters = data.get(key).get("filters")
			if filters and isinstance(filters, list):
				for f in filters:
					if f[2] == "Next" or f[2] == "Previous":
						update = True
						f[3] = period_map[f[2]] + " " + timespan_map[f[3]]
						f[2] = "Timespan"

			if update:
				data[key]["filters"] = filters
				update_user_settings(user_setting["doctype"], json.dumps(data), for_update=True)
