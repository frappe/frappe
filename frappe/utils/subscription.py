import json

import requests

import frappe


@frappe.whitelist()
def show_banner():
	expiry = frappe.conf.expiry
	if expiry and frappe.conf.login_url:
		navbar_item, hidden = frappe.db.get_value(
			"Navbar Item", {"item_label": "Manage Subscriptions"}, ["name", "hidden"]
		)
		if navbar_item and hidden:
			doc = frappe.get_cached_doc("Navbar Item", navbar_item)
			doc.hidden = False
			doc.save()
		return expiry
	return False


@frappe.whitelist()
def remote_login():
	login_url = frappe.conf.login_url
	if frappe.conf.expiry and login_url:
		resp = requests.post(login_url)

		if resp.status_code != 200:
			return

		return json.loads(resp.text)["message"]
	else:
		return False
