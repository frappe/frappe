import frappe, json
from frappe.model.utils.user_settings import update_user_settings, sync_user_settings

def execute():
	""" Update list_view's sort by property from __UserSettings """

	users = frappe.db.sql("select distinct(user) from `__UserSettings`", as_dict=True)

	for user in users:
		# get user_settings for each user
		settings = frappe.db.sql("select * from `__UserSettings` \
			where user={0}".format(frappe.db.escape(user.user)), as_dict=True)

		# traverse through each doctype's settings for a user
		for d in settings:
			data = json.loads(d['data'])
			if data and ('List' in data) and ('sort_by' in data['List']) and data['List']['sort_by'] == 'modified':
				# if order_by is 'modified' then update it to 'creation'
				data['List']['sort_by'] = 'creation'
				update_user_settings(d['doctype'], json.dumps(data), for_update=True)

	sync_user_settings()