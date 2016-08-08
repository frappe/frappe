import frappe, json

def get_list_settings(doctype, for_update=False):
	list_settings = frappe.cache().hget('_list_settings',
		'{0}::{1}'.format(doctype, frappe.session.user))

	if list_settings is None:
		list_settings = frappe.db.sql('''select data from __ListSettings
			where user=%s and doctype=%s''', (frappe.session.user, doctype))
		list_settings = list_settings and list_settings[0][0] or '{}'

		if not for_update:
			update_list_settings(doctype, list_settings, True)

	return list_settings

def update_list_settings(doctype, list_settings, for_update=False):
	'''update list settings in cache'''

	if for_update:
		current = json.loads(list_settings)
	else:
		current = json.loads(get_list_settings(doctype, for_update = True))

		if isinstance(current, basestring):
			# corrupt due to old code, remove this in a future release
			current = {}

		current.update(list_settings)

	frappe.cache().hset('_list_settings', '{0}::{1}'.format(doctype, frappe.session.user),
		json.dumps(current))

def sync_list_settings():
	'''Sync from cache to database (called asynchronously via the browser)'''
	for key, data in frappe.cache().hgetall('_list_settings').iteritems():
		doctype, user = key.split('::')
		frappe.db.sql('''insert into __ListSettings (user, doctype, data) values (%s, %s, %s)
			on duplicate key update data=%s''', (user, doctype, data, data))