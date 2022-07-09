import json

import frappe
from frappe.model.utils.user_settings import sync_user_settings, update_user_settings


def execute():
	"""Update list_view's order by property from __UserSettings"""

	users = frappe.db.sql("select distinct(user) from `__UserSettings`", as_dict=True)

	for user in users:
		# get user_settings for each user
		settings = frappe.db.sql(
			"select * from `__UserSettings` \
			where user={}".format(
				frappe.db.escape(user.user)
			),
			as_dict=True,
		)

		# traverse through each doctype's settings for a user
		for d in settings:
			data = json.loads(d["data"])
			if data and ("List" in data) and ("order_by" in data["List"]) and data["List"]["order_by"]:
				# convert order_by to sort_order & sort_by and delete order_by
				order_by = data["List"]["order_by"]
				if "`" in order_by and "." in order_by:
					order_by = order_by.replace("`", "").split(".")[1]

				data["List"]["sort_by"], data["List"]["sort_order"] = order_by.split(" ")
				data["List"].pop("order_by")
				update_user_settings(d["doctype"], json.dumps(data), for_update=True)

	sync_user_settings()
