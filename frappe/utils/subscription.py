import json
import requests
import frappe


@frappe.whitelist()
def show_banner():
	expiry = frappe.conf.expiry
	if expiry and frappe.conf.login_url:
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
