# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import flt, time_diff_in_seconds, now, cint
import json

class BannedIP(Document):
	pass

def upban_ip_address():
	defaults = frappe.defaults.get_defaults()
	for doc in frappe.get_all("Banned IP", filters={'banned': 1}, fields=["name", "modified", "ip_address"]):
		minutes = round(flt(time_diff_in_seconds(now(), doc.modified))/60, 6)

		if minutes > (flt(defaults.ban_ip_till) or 5.0):
			frappe.db.set_value("Banned IP", doc.name, "banned", 0)
			update_failed_to_ban_count(doc.ip_address, reset_count=True)

def update_failed_to_ban_count(ip_address, reset_count=False):
	cache = frappe.cache()
	login_failed_from_ip = {}
	defaults = frappe.defaults.get_defaults()

	# if cache not contains login_failed_from_ip then add key to cache
	# else load failed ip count dict from cache
	if not cache.get("login_failed_from_ip"):
		cache.set("login_failed_from_ip", {})
	else:
		login_failed_from_ip = json.loads(cache.get("login_failed_from_ip"))

	if not login_failed_from_ip.get(ip_address) and not reset_count:
		login_failed_from_ip[ip_address] = 0

	elif login_failed_from_ip.get(ip_address) and reset_count:
		del login_failed_from_ip[ip_address]

	if not reset_count:
		login_failed_from_ip[ip_address] += 1 if frappe.flags.auth_failed else -1

		if login_failed_from_ip.get(ip_address, 0) < 0:
			login_failed_from_ip[ip_address] = 0

	if login_failed_from_ip.get(ip_address) >= (cint(defaults.ban_ip_after_auth_failure) or 3):
		ban_ip_address(ip_address)

	cache.set("login_failed_from_ip", json.dumps(login_failed_from_ip))

def ban_ip_address(ip_address):
	banned_ip = frappe.db.get_value("Banned IP", filters={"ip_address": ip_address})

	if not banned_ip:
		frappe.get_doc({
			"doctype": "Banned IP",
			"ip_address": ip_address,
			"banned": 1
		}).insert(ignore_permissions=True)
	else:
		frappe.db.set_value("Banned IP", banned_ip, "banned", 1)

	frappe.db.commit()