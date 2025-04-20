import requests

import frappe
from frappe import _


def get_base_url():
	url = "https://frappecloud.com"
	if frappe.conf.developer_mode and frappe.conf.get("fc_base_url"):
		url = frappe.conf.get("fc_base_url")
	return url


def get_site_login_url():
	return f"{get_base_url()}/dashboard/site-login"


def get_site_name():
	site_name = frappe.local.site
	if frappe.conf.developer_mode and frappe.conf.get("saas_billing_site_name"):
		site_name = frappe.conf.get("saas_billing_site_name")
	return site_name


def get_headers():
	# check if user is system manager
	if frappe.get_roles(frappe.session.user).count("System Manager") == 0:
		frappe.throw(_("You are not allowed to access this resource"))

	# check if communication secret is set
	if not frappe.conf.get("fc_communication_secret"):
		frappe.throw(_("Communication secret not set"))

	return {
		"X-Site-Token": frappe.conf.get("fc_communication_secret"),
		"X-Site-User": frappe.session.user,
		"X-Site": get_site_name(),
	}


@frappe.whitelist()
def current_site_info():
	from frappe.utils import cint

	request = requests.post(f"{get_base_url()}/api/method/press.saas.api.site.info", headers=get_headers())
	if request.status_code == 200:
		res = request.json().get("message")
		if not res:
			return None

		return {
			**res,
			"site_name": get_site_name(),
			"base_url": get_base_url(),
			"setup_complete": cint(frappe.get_system_settings("setup_complete")),
		}

	else:
		frappe.throw(_("Failed to get site info"))


@frappe.whitelist()
def api(method, data=None):
	if data is None:
		data = {}
	request = requests.post(
		f"{get_base_url()}/api/method/press.saas.api.{method}",
		headers=get_headers(),
		json=data,
	)
	if request.status_code == 200:
		return request.json().get("message")
	else:
		frappe.throw(_("Failed while calling API {0}", method))


@frappe.whitelist()
def is_fc_site() -> bool:
	is_system_manager = frappe.get_roles(frappe.session.user).count("System Manager")
	return bool(is_system_manager and frappe.conf.get("fc_communication_secret"))


# login to frappe cloud dashboard
@frappe.whitelist()
def send_verification_code():
	request = requests.post(
		f"{get_base_url()}/api/method/press.api.developer.saas.send_verification_code",
		headers=get_headers(),
		json={"domain": get_site_name()},
	)
	if request.status_code == 200:
		return request.json().get("message")
	else:
		frappe.throw(_("Failed to request login to Frappe Cloud"))


@frappe.whitelist()
def verify_verification_code(verification_code: str, route: str):
	request = requests.post(
		f"{get_base_url()}/api/method/press.api.developer.saas.verify_verification_code",
		headers=get_headers(),
		json={"domain": get_site_name(), "verification_code": verification_code, "route": route},
	)

	if request.status_code == 200:
		return {
			"base_url": get_base_url(),
			"login_token": request.json()["login_token"],
		}
	else:
		frappe.throw(_("Invalid Code. Please try again."))
