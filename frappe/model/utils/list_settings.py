import frappe, json

def get_list_settings(doctype):
	list_settings = frappe.cache().hget('_list_settings',
		'{0}::{1}'.format(doctype, frappe.session.user))

	if list_settings is None:
		list_settings = frappe.db.sql('''select * from __ListSettings
			where user=%s and doctype=%s''', (frappe.session.user, doctype), as_dict=True)
		list_settings = list_settings and list_settings[0] or '{}'
		update_list_settings(doctype, list_settings)

	return list_settings

def update_list_settings(doctype, list_settings):
	'''update list settings in cache'''
	if not isinstance(list_settings, basestring):
		list_settings = json.dumps(list_settings)

	frappe.cache().hset('_list_settings', '{0}::{1}'.format(doctype, frappe.session.user),
		list_settings)

def sync_list_settings():
	'''Sync from cache to database (called asynchronously via the browser)'''
	for key, data in frappe.cache().hgetall('_list_settings').iteritems():
		doctype, user = key.split('::')
		frappe.db.sql('''insert into __ListSettings (user, doctype, data) values (%s, %s, %s)
			on duplicate key update data=%s''', (user, doctype, data, data))