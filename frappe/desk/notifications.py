# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
from frappe.desk.doctype.notification_settings.notification_settings import get_subscribed_documents
from six import string_types
import json

@frappe.whitelist()
@frappe.read_only()
def get_notifications():
	if (frappe.flags.in_install or
		not frappe.db.get_single_value('System Settings', 'setup_complete')):
		return {
			"open_count_doctype": {},
			"targets": {},
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
		"targets": get_notifications_for_targets(config, notification_percent),
	}

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
						result = frappe.get_list(d, fields=["count(*) as count"], filters=condition, ignore_ifnull=True)[0].count
					else:
						result = frappe.get_attr(condition)()

				except frappe.PermissionError:
					frappe.clear_messages()
					pass
					# frappe.msgprint("Permission Error in notifications for {0}".format(d))

				except Exception as e:
					# OperationalError: (1412, 'Table definition has changed, please retry transaction')
					# InternalError: (1684, 'Table definition is being modified by concurrent DDL statement')
					if e.args and e.args[0] not in (1412, 1684):
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
					if e.args[0] not in (1412, 1684):
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
	cache = frappe.cache()
	config = get_notification_config()
	for_doctype = list(config.get('for_doctype')) if config.get('for_doctype') else []
	for_module = list(config.get('for_module')) if config.get('for_module') else []
	groups = for_doctype + for_module

	for name in groups:
		if user:
			cache.hdel("notification_count:" + name, user)
		else:
			cache.delete_key("notification_count:" + name)

	frappe.publish_realtime('clear_notifications')

def clear_notification_config(user):
	frappe.cache().hdel('notification_config', user)

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

@frappe.whitelist()
def get_notification_info():
	config = get_notification_config()
	out = get_notifications()
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
	user = frappe.session.user or 'Guest'

	def _get():
		subscribed_documents = get_subscribed_documents()
		config = frappe._dict()
		hooks = frappe.get_hooks()
		if hooks:
			for notification_config in hooks.notification_config:
				nc = frappe.get_attr(notification_config)()
				for key in ("for_doctype", "for_module", "for_other", "targets"):
					config.setdefault(key, {})
					if key == "for_doctype":
						if len(subscribed_documents) > 0:
							key_config = nc.get(key, {})
							subscribed_docs_config = frappe._dict()
							for document in subscribed_documents:
								if key_config.get(document):
									subscribed_docs_config[document] = key_config.get(document)
							config[key].update(subscribed_docs_config)
						else:
							config[key].update(nc.get(key, {}))
					else:
						config[key].update(nc.get(key, {}))
		return config

	return frappe.cache().hget("notification_config", user, _get)

def get_filters_for(doctype):
	'''get open filters for doctype'''
	config = get_notification_config()
	return config.get("for_doctype").get(doctype, {})

@frappe.whitelist()
@frappe.read_only()
def get_open_count(doctype, name, items=[]):
	'''Get open count for given transactions and filters

	:param doctype: Reference DocType
	:param name: Reference Name
	:param transactions: List of transactions (json/dict)
	:param filters: optional filters (json/list)'''

	if frappe.flags.in_migrate or frappe.flags.in_install:
		return {
			"count": []
		}

	frappe.has_permission(doc=frappe.get_doc(doctype, name), throw=True)

	meta = frappe.get_meta(doctype)
	links = meta.get_dashboard_data()

	# compile all items in a list
	if not items:
		for group in links.transactions:
			items.extend(group.get("items"))

	if not isinstance(items, list):
		items = json.loads(items)

	out = []
	for d in items:
		if d in links.get("internal_links", {}):
			# internal link
			continue

		filters = get_filters_for(d)
		fieldname = links.get("non_standard_fieldnames", {}).get(d, links.get('fieldname'))
		data = {"name": d}
		if filters:
			# get the fieldname for the current document
			# we only need open documents related to the current document
			filters[fieldname] = name
			total = len(frappe.get_all(d, fields="name",
				filters=filters, limit=100, distinct=True, ignore_ifnull=True))
			data["open_count"] = total

		total = len(frappe.get_all(d, fields="name",
			filters={fieldname: name}, limit=100, distinct=True, ignore_ifnull=True))
		data["count"] = total
		out.append(data)

	out = {
		"count": out,
	}

	module = frappe.get_meta_module(doctype)
	if hasattr(module, "get_timeline_data"):
		out["timeline_data"] = module.get_timeline_data(doctype, name)

	return out
