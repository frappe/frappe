# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
from frappe.utils import time_diff_in_seconds, now, now_datetime, DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
from six import string_types
import json

@frappe.whitelist()
def get_notifications():
	if (frappe.flags.in_install or
		not frappe.db.get_single_value('System Settings', 'setup_complete')):
		return {
			"open_count_doctype": {},
			"open_count_module": {},
			"open_count_other": {},
			"targets": {},
			"new_messages": []
		}

	config = get_notification_config()

	groups = list(config.get("for_doctype")) + list(config.get("for_module"))
	cache = frappe.cache()

	notification_count = {}
	notification_percent = {}

	for name in groups:
		count = cache.hget("notification_count:" + name, frappe.session.user)
		if count is not None:
			notification_count[name] = count

	return {
		"open_count_doctype": get_notifications_for_doctypes(config, notification_count),
		"open_count_module": get_notifications_for_modules(config, notification_count),
		"open_count_other": get_notifications_for_other(config, notification_count),
		"targets": get_notifications_for_targets(config, notification_percent),
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

	return frappe.db.sql("""select sender_full_name, content
		from `tabCommunication`
			where communication_type in ('Chat', 'Notification')
			and reference_doctype='user'
			and reference_name = %s
			and creation > %s
			order by creation desc""", (frappe.session.user, last_update), as_dict=1)

def get_notifications_for_modules(config, notification_count):
	"""Notifications for modules"""
	return get_notifications_for("for_module", config, notification_count)

def get_notifications_for_other(config, notification_count):
	"""Notifications for other items"""
	return get_notifications_for("for_other", config, notification_count)

def get_notifications_for(notification_type, config, notification_count):
	open_count = {}
	notification_map = config.get(notification_type) or {}
	for m in notification_map:
		try:
			if m in notification_count:
				open_count[m] = notification_count[m]
			else:
				open_count[m] = frappe.get_attr(notification_map[m])()

				frappe.cache().hset("notification_count:" + m, frappe.session.user, open_count[m])
		except frappe.PermissionError:
			frappe.clear_messages()
			pass
			# frappe.msgprint("Permission Error in notifications for {0}".format(m))

	return open_count

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
						result = len(frappe.get_list(d, fields=["name"],
							filters=condition, limit_page_length = 100, as_list=True, ignore_ifnull=True))
					else:
						result = frappe.get_attr(condition)()

				except frappe.PermissionError:
					frappe.clear_messages()
					pass
					# frappe.msgprint("Permission Error in notifications for {0}".format(d))

				except Exception as e:
					# OperationalError: (1412, 'Table definition has changed, please retry transaction')
					if e.args[0]!=1412:
						raise

				else:
					open_count_doctype[d] = result
					frappe.cache().hset("notification_count:" + d, frappe.session.user, result)

	return open_count_doctype

def get_notifications_for_targets(config, notification_percent):
	"""Notifications for doc targets"""
	can_read = frappe.get_user().get_can_read()
	doc_target_percents = {}

	# doc_target_percents = {
	# 	"Company": {
	# 		"Acme": 87,
	# 		"RobotsRUs": 50,
	# 	}, {}...
	# }

	for doctype in config.targets:
		if doctype in can_read:
			if doctype in notification_percent:
				doc_target_percents[doctype] = notification_percent[doctype]
			else:
				doc_target_percents[doctype] = {}
				d = config.targets[doctype]
				condition = d["filters"]
				target_field = d["target_field"]
				value_field = d["value_field"]
				try:
					if isinstance(condition, dict):
						doc_list = frappe.get_list(doctype, fields=["name", target_field, value_field],
							filters=condition, limit_page_length = 100, ignore_ifnull=True)

				except frappe.PermissionError:
					frappe.clear_messages()
					pass
				except Exception as e:
					if e.args[0]!=1412:
						raise

				else:
					for doc in doc_list:
						value = doc[value_field]
						target = doc[target_field]
						doc_target_percents[doctype][doc.name] = (value/target * 100) if value < target else 100

	return doc_target_percents

def clear_notifications(user=None):
	if frappe.flags.in_install:
		return

	config = get_notification_config()
	for_doctype = list(config.get('for_doctype')) if config.get('for_doctype') else []
	for_module = list(config.get('for_module')) if config.get('for_module') else []
	groups = for_doctype + for_module
	cache = frappe.cache()

	for name in groups:
		if user:
			cache.hdel("notification_count:" + name, user)
		else:
			cache.delete_key("notification_count:" + name)

	frappe.publish_realtime('clear_notifications')

def delete_notification_count_for(doctype):
	frappe.cache().delete_key("notification_count:" + doctype)
	frappe.publish_realtime('clear_notifications')

def clear_doctype_notifications(doc, method=None, *args, **kwargs):
	config = get_notification_config()
	if isinstance(doc, string_types):
		doctype = doc # assuming doctype name was passed directly
	else:
		doctype = doc.doctype

	if doctype in config.for_doctype:
		delete_notification_count_for(doctype)
		return

def get_notification_info_for_boot():
	out = get_notifications()
	config = get_notification_config()
	can_read = frappe.get_user().get_can_read()
	conditions = {}
	module_doctypes = {}
	doctype_info = dict(frappe.db.sql("""select name, module from tabDocType"""))

	for d in list(set(can_read + list(config.for_doctype))):
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
		hooks = frappe.get_hooks()
		if hooks:
			for notification_config in hooks.notification_config:
				nc = frappe.get_attr(notification_config)()
				for key in ("for_doctype", "for_module", "for_other", "targets"):
					config.setdefault(key, {})
					config[key].update(nc.get(key, {}))
		return config

	return frappe.cache().get_value("notification_config", _get)

def get_filters_for(doctype):
	'''get open filters for doctype'''
	config = get_notification_config()
	return config.get('for_doctype').get(doctype, {})

@frappe.whitelist()
def get_open_count(doctype, name, items=[]):
	'''Get open count for given transactions and filters

	:param doctype: Reference DocType
	:param name: Reference Name
	:param transactions: List of transactions (json/dict)
	:param filters: optional filters (json/list)'''

	frappe.has_permission(doc=frappe.get_doc(doctype, name), throw=True)

	meta = frappe.get_meta(doctype)
	links = meta.get_dashboard_data()

	# compile all items in a list
	if not items:
		for group in links.transactions:
			items.extend(group.get('items'))

	if not isinstance(items, list):
		items = json.loads(items)

	out = []
	for d in items:
		if d in links.get('internal_links', {}):
			# internal link
			continue

		filters = get_filters_for(d)
		fieldname = links.get('non_standard_fieldnames', {}).get(d, links.fieldname)
		data = {'name': d}
		if filters:
			# get the fieldname for the current document
			# we only need open documents related to the current document
			filters[fieldname] = name
			total = len(frappe.get_all(d, fields='name',
				filters=filters, limit=100, distinct=True, ignore_ifnull=True))
			data['open_count'] = total

		total = len(frappe.get_all(d, fields='name',
			filters={fieldname: name}, limit=100, distinct=True, ignore_ifnull=True))
		data['count'] = total
		out.append(data)

	out = {
		'count': out,
	}

	module = frappe.get_meta_module(doctype)
	if hasattr(module, 'get_timeline_data'):
		out['timeline_data'] = module.get_timeline_data(doctype, name)

	return out
