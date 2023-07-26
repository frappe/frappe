# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

from bs4 import BeautifulSoup

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import (
	enqueue_create_notification,
	get_title,
	get_title_html,
)
from frappe.desk.doctype.notification_settings.notification_settings import (
	get_subscribed_documents,
)
from frappe.utils import get_fullname


@frappe.whitelist()
@frappe.read_only()
def get_notifications():
	out = {
		"open_count_doctype": {},
		"targets": {},
	}
	if frappe.flags.in_install or not frappe.db.get_single_value("System Settings", "setup_complete"):
		return out

	config = get_notification_config()

	if not config:
		return out

	groups = list(config.get("for_doctype")) + list(config.get("for_module"))
	cache = frappe.cache()

	notification_count = {}
	notification_percent = {}

	for name in groups:
		count = cache.hget("notification_count:" + name, frappe.session.user)
		if count is not None:
			notification_count[name] = count

	out["open_count_doctype"] = get_notifications_for_doctypes(config, notification_count)
	out["targets"] = get_notifications_for_targets(config, notification_percent)

	return out


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
						result = frappe.get_list(
							d, fields=["count(*) as count"], filters=condition, ignore_ifnull=True
						)[0].count
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
						doc_list = frappe.get_list(
							doctype,
							fields=["name", target_field, value_field],
							filters=condition,
							limit_page_length=100,
							ignore_ifnull=True,
						)

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
						doc_target_percents[doctype][doc.name] = (value / target * 100) if value < target else 100

	return doc_target_percents


def clear_notifications(user=None):
	if frappe.flags.in_install:
		return
	cache = frappe.cache()
	config = get_notification_config()

	if not config:
		return

	for_doctype = list(config.get("for_doctype")) if config.get("for_doctype") else []
	for_module = list(config.get("for_module")) if config.get("for_module") else []
	groups = for_doctype + for_module

	for name in groups:
		if user:
			cache.hdel("notification_count:" + name, user)
		else:
			cache.delete_key("notification_count:" + name)


def clear_notification_config(user):
	frappe.cache().hdel("notification_config", user)


def delete_notification_count_for(doctype):
	frappe.cache().delete_key("notification_count:" + doctype)


def clear_doctype_notifications(doc, method=None, *args, **kwargs):
	config = get_notification_config()
	if not config:
		return
	if isinstance(doc, str):
		doctype = doc  # assuming doctype name was passed directly
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

	out.update(
		{
			"conditions": conditions,
			"module_doctypes": module_doctypes,
		}
	)

	return out


def get_notification_config():
	user = frappe.session.user or "Guest"

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
	"""get open filters for doctype"""
	config = get_notification_config()
	doctype_config = config.get("for_doctype").get(doctype, {})
	filters = doctype_config if not isinstance(doctype_config, str) else None

	return filters


@frappe.whitelist()
@frappe.read_only()
def get_open_count(doctype, name, items=None):
	"""Get count for internal and external links for given transactions

	:param doctype: Reference DocType
	:param name: Reference Name
	:param items: Optional list of transactions (json/dict)"""

	if frappe.flags.in_migrate or frappe.flags.in_install:
		return {"count": []}

	doc = frappe.get_doc(doctype, name)
	doc.check_permission()
	meta = doc.meta
	links = meta.get_dashboard_data()

	# compile all items in a list
	if items is None:
		items = []
		for group in links.transactions:
			items.extend(group.get("items"))

	if not isinstance(items, list):
		items = json.loads(items)

	out = {
		"external_links_found": [],
		"internal_links_found": [],
	}

	for d in items:
		internal_link_for_doctype = links.get("internal_links", {}).get(d)
		if internal_link_for_doctype:
			internal_links_data_for_d = get_internal_links(doc, internal_link_for_doctype, d)
			if internal_links_data_for_d["count"]:
				out["internal_links_found"].append(internal_links_data_for_d)
			else:
				try:
					external_links_data_for_d = get_external_links(d, name, links)
					out["external_links_found"].append(external_links_data_for_d)
				except Exception as e:
					out["external_links_found"].append({"doctype": d, "open_count": 0, "count": 0})
		else:
			external_links_data_for_d = get_external_links(d, name, links)
			out["external_links_found"].append(external_links_data_for_d)

	out = {
		"count": out,
	}

	if not meta.custom:
		module = frappe.get_meta_module(doctype)
		if hasattr(module, "get_timeline_data"):
			out["timeline_data"] = module.get_timeline_data(doctype, name)

	return out


def get_internal_links(doc, link, link_doctype):
	names = []
	data = {"doctype": link_doctype}

	if isinstance(link, str):
		# get internal links in parent document
		value = doc.get(link)
		if value and value not in names:
			names.append(value)
	elif isinstance(link, list):
		# get internal links in child documents
		table_fieldname, link_fieldname = link
		for row in doc.get(table_fieldname):
			value = row.get(link_fieldname)
			if value and value not in names:
				names.append(value)

	data["open_count"] = 0
	data["count"] = len(names)
	data["names"] = names

	return data


def get_external_links(doctype, name, links):
	filters = get_filters_for(doctype)
	fieldname = links.get("non_standard_fieldnames", {}).get(doctype, links.get("fieldname"))
	data = {"doctype": doctype}

	if filters:
		# get the fieldname for the current document
		# we only need open documents related to the current document
		filters[fieldname] = name
		total = len(
			frappe.get_all(
				doctype, fields="name", filters=filters, limit=100, distinct=True, ignore_ifnull=True
			)
		)
		data["open_count"] = total
	else:
		data["open_count"] = 0

	total = len(
		frappe.get_all(
			doctype, fields="name", filters={fieldname: name}, limit=100, distinct=True, ignore_ifnull=True
		)
	)
	data["count"] = total

	return data


def notify_mentions(ref_doctype, ref_name, content):
	if ref_doctype and ref_name and content:
		mentions = extract_mentions(content)

		if not mentions:
			return

		sender_fullname = get_fullname(frappe.session.user)
		title = get_title(ref_doctype, ref_name)

		recipients = [
			frappe.db.get_value(
				"User",
				{"enabled": 1, "name": name, "user_type": "System User", "allowed_in_mentions": 1},
				"email",
			)
			for name in mentions
		]

		notification_message = _("""{0} mentioned you in a comment in {1} {2}""").format(
			frappe.bold(sender_fullname), frappe.bold(ref_doctype), get_title_html(title)
		)

		notification_doc = {
			"type": "Mention",
			"document_type": ref_doctype,
			"document_name": ref_name,
			"subject": notification_message,
			"from_user": frappe.session.user,
			"email_content": content,
		}

		enqueue_create_notification(recipients, notification_doc)


def extract_mentions(txt):
	"""Find all instances of @mentions in the html."""
	soup = BeautifulSoup(txt, "html.parser")
	emails = []
	for mention in soup.find_all(class_="mention"):
		if mention.get("data-is-group") == "true":
			try:
				user_group = frappe.get_cached_doc("User Group", mention["data-id"])
				emails += [d.user for d in user_group.user_group_members]
			except frappe.DoesNotExistError:
				pass
			continue
		email = mention["data-id"]
		emails.append(email)

	return emails
