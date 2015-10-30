# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import time_diff_in_seconds, now, now_datetime, DATETIME_FORMAT
from dateutil.relativedelta import relativedelta

@frappe.whitelist()
def get_notifications():
	if frappe.flags.in_install:
		return

	config = get_notification_config()
	groups = config.get("for_doctype").keys() + config.get("for_module").keys()
	cache = frappe.cache()

	notification_count = {}
	for name in groups:
		count = cache.hget("notification_count:" + name, frappe.session.user)
		if count is not None:
			notification_count[name] = count

	return {
		"open_count_doctype": get_notifications_for_doctypes(config, notification_count),
		"open_count_module": get_notifications_for_modules(config, notification_count),
		"new_messages": get_new_messages()
	}

def get_new_messages():
	last_update = frappe.cache().hget("notifications_last_update", frappe.session.user)
	now_timestamp = now()
	frappe.cache().hset("notifications_last_update", frappe.session.user, now_timestamp)

	if not last_update:
		return []

	if last_update and time_diff_in_seconds(now_timestamp, last_update) > 1800:
		# no update for 30 mins, consider only the last 30 mins
		last_update = (now_datetime() - relativedelta(seconds=1800)).strftime(DATETIME_FORMAT)

	return frappe.db.sql("""select comment_by_fullname, comment
		from tabComment
			where comment_doctype='Message'
			and comment_docname = %s
			and ifnull(creation, "2000-01-01") > %s
			order by creation desc""", (frappe.session.user, last_update), as_dict=1)

def get_notifications_for_modules(config, notification_count):
	"""Notifications for modules"""
	open_count_module = {}
	for m in config.for_module:
		try:
			if m in notification_count:
				open_count_module[m] = notification_count[m]
			else:
				open_count_module[m] = frappe.get_attr(config.for_module[m])()

				frappe.cache().hset("notification_count:" + m, frappe.session.user, open_count_module[m])
		except frappe.PermissionError:
			frappe.msgprint("Permission Error in notifications for {0}".format(m))

	return open_count_module

def get_notifications_for_doctypes(config, notification_count):
	"""Notifications for DocTypes"""
	can_read = frappe.get_user().get_can_read()
	open_count_doctype = {}

	for d in config.for_doctype:
		if d in can_read:
			condition = config.for_doctype[d]

			if d in notification_count:
				open_count_doctype[d] = notification_count[d]
			else:
				try:
					if isinstance(condition, dict):
						result = frappe.get_list(d, fields=["count(*)"],
							filters=condition, as_list=True)[0][0]
					else:
						result = frappe.get_attr(condition)()

				except frappe.PermissionError:
					frappe.msgprint("Permission Error in notifications for {0}".format(d))

				except Exception, e:
					# OperationalError: (1412, 'Table definition has changed, please retry transaction')
					if e.args[0]!=1412:
						raise

				else:
					open_count_doctype[d] = result
					frappe.cache().hset("notification_count:" + d, frappe.session.user, result)

	return open_count_doctype

def clear_notifications(user="*"):
	if user=="*":
		frappe.cache().delete_keys("notification_count:")
	else:
		# delete count for user
		frappe.cache().hdel_keys("notification_count:", user)

def delete_notification_count_for(doctype):
	frappe.cache().delete_key("notification_count:" + doctype)

def clear_doctype_notifications(doc, method=None, *args, **kwargs):
	config = get_notification_config()
	doctype = doc.doctype

	if doctype in config.for_doctype:
		delete_notification_count_for(doctype)
		return

	if doctype in config.for_module_doctypes:
		delete_notification_count_for(config.for_module_doctypes[doctype])

def get_notification_info_for_boot():
	out = get_notifications()
	config = get_notification_config()
	can_read = frappe.get_user().get_can_read()
	conditions = {}
	module_doctypes = {}
	doctype_info = dict(frappe.db.sql("""select name, module from tabDocType"""))

	for d in list(set(can_read + config.for_doctype.keys())):
		if d in config.for_doctype:
			conditions[d] = config.for_doctype[d]

		if d in doctype_info:
			module_doctypes.setdefault(doctype_info[d], []).append(d)

	out.update({
		"conditions": conditions,
		"module_doctypes": module_doctypes,
	})

	return out

def get_notification_config():
	def _get():
		config = frappe._dict()
		for notification_config in frappe.get_hooks().notification_config:
			nc = frappe.get_attr(notification_config)()
			for key in ("for_doctype", "for_module", "for_module_doctypes"):
				config.setdefault(key, {})
				config[key].update(nc.get(key, {}))
		return config

	return frappe.cache().get_value("notification_config", _get)
