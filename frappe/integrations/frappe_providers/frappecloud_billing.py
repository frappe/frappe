from typing import Any

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


def mock_billing_enabled() -> bool:
	"""True when a developer asked for fake Frappe Cloud billing data.

	Put both of these in site_config.json to see the trial/upgrade banner on a
	local site that has no Frappe Cloud credentials:

	    "developer_mode": 1,
	    "mock_fc_billing": 1

	Optionally set "mock_fc_trial_days" (default 7) to move the trial end date.
	"""
	return bool(frappe.conf.developer_mode and frappe.conf.get("mock_fc_billing"))


def mock_site_info() -> dict:
	"""Stand-in for what Frappe Cloud would report for a site on a trial plan."""
	from frappe.utils import add_days, cint, nowdate

	trial_days = cint(frappe.conf.get("mock_fc_trial_days")) or 7
	site_name = get_site_name()

	return {
		"name": site_name,
		"site_name": site_name,
		"base_url": get_base_url(),
		"trial_end_date": add_days(nowdate(), trial_days),
		"plan": {"is_trial_plan": True},
		"is_fc_user": True,
		"setup_complete": cint(frappe.get_system_settings("setup_complete")),
	}


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
	frappe.only_for("System Manager")

	if mock_billing_enabled():
		# not cached, so tweaking site_config shows up on the next reload
		return mock_site_info()
	cache_key = f"fc_current_site_info:{frappe.local.site}"
	cached_data = frappe.cache().get_value(cache_key)
	if cached_data:
		return cached_data

	res = {}
	request = requests.post(f"{get_base_url()}/api/method/press.saas.api.site.info", headers=get_headers())
	if request.status_code == 200:
		res = request.json().get("message")
		if not res or not isinstance(res, dict):
			return None

	site_info = {
		**res,
		"site_name": get_site_name(),
		"base_url": get_base_url(),
		"setup_complete": cint(frappe.get_system_settings("setup_complete")),
	}

	frappe.cache().set_value(cache_key, site_info, expires_in_sec=600)

	return site_info


@frappe.whitelist()
def api(method: str, data: str | dict[str, Any] | None = None):
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
	if not is_system_manager:
		return False

	return bool(mock_billing_enabled() or frappe.conf.get("fc_communication_secret"))


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
