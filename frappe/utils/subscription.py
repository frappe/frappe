import json

import requests

import frappe


@frappe.whitelist()
def show_banner():
	if frappe.conf.subscription:
		try:
			navbar_item, hidden = frappe.db.get_value(
				"Navbar Item", {"item_label": "Manage Subscriptions"}, ["name", "hidden"]
			)
			if navbar_item and hidden:
				doc = frappe.get_cached_doc("Navbar Item", navbar_item)
				doc.hidden = False
				doc.save()
			return frappe.conf.subscription["expiry"]
		except Exception:
			return False

	return False


@frappe.whitelist()
def remote_login():
	try:
		login_url = frappe.conf.subscription["login_url"]
		if frappe.conf.subscription["expiry"] and login_url:
			resp = requests.post(login_url)

			if resp.status_code != 200:
				return

			return json.loads(resp.text)["message"]
	except Exception:
		return False

	return False
