import frappe
import json
from frappe.model.utils.user_settings import update_user_settings, sync_user_settings

def execute():
	""" Update list_view's sort by property from __UserSettings """

	user_field = frappe.qb.Field("user")
	query = frappe.qb.from_("__UserSettings").select(user_field).distinct()
	users = query.run(as_dict=True)

	for user in users:
		# get user_settings for each user
		query = frappe.qb.from_("__UserSettings").select("*").where(user_field == user.user)
		settings = query.run(as_dict=True)

		# traverse through each doctype's settings for a user
		for d in settings:
			data = json.loads(d['data'])
			if data and ('List' in data) and ('sort_by' in data['List']) and data['List']['sort_by'] == 'modified':
				# if order_by is 'modified' then update it to 'creation'
				data['List']['sort_by'] = 'creation'
				update_user_settings(d['doctype'], json.dumps(data), for_update=True)

	sync_user_settings()