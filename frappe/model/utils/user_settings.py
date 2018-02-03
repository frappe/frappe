# Settings saved per user basis
# such as page_limit, filters, last_view

import frappe, json
from six import iteritems, string_types


def get_user_settings(doctype, for_update=False):
	user_settings = frappe.cache().hget('_user_settings',
		'{0}::{1}'.format(doctype, frappe.session.user))

	if user_settings is None:
		user_settings = frappe.db.sql('''select data from __UserSettings
			where user=%s and doctype=%s''', (frappe.session.user, doctype))
		user_settings = user_settings and user_settings[0][0] or '{}'

		if not for_update:
			update_user_settings(doctype, user_settings, True)

	return user_settings or '{}'

def update_user_settings(doctype, user_settings, for_update=False):
	'''update user settings in cache'''

	if for_update:
		current = json.loads(user_settings)
	else:
		current = json.loads(get_user_settings(doctype, for_update = True))

		if isinstance(current, string_types):
			# corrupt due to old code, remove this in a future release
			current = {}

		current.update(user_settings)

	frappe.cache().hset('_user_settings', '{0}::{1}'.format(doctype, frappe.session.user),
		json.dumps(current))

def sync_user_settings():
	'''Sync from cache to database (called asynchronously via the browser)'''
	for key, data in iteritems(frappe.cache().hgetall('_user_settings')):
		doctype, user = key.split('::')
		frappe.db.sql('''insert into __UserSettings (user, doctype, data) values (%s, %s, %s)
			on duplicate key update data=%s''', (user, doctype, data, data))

@frappe.whitelist()
def save(doctype, user_settings):
	user_settings = json.loads(user_settings or '{}')
	update_user_settings(doctype, user_settings)
	return user_settings
