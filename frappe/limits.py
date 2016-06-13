from __future__ import unicode_literals
import frappe
from frappe.utils import now_datetime, getdate
from frappe.installer import update_site_config
from frappe.utils.data import formatdate
from frappe import _

class SiteExpiredError(frappe.ValidationError):
	pass

EXPIRY_WARNING_DAYS = 10

def load_limits(bootinfo):
	bootinfo["frappe_limits"] = get_limits()
	bootinfo["expiry_message"] = get_expiry_message()


def has_expired():
	if frappe.session.user=="Administrator":
		return False

	expires_on = get_limits().get("expiry")
	if not expires_on:
		return False

	if now_datetime().date() <= getdate(expires_on):
		return False

	return True

def check_if_expired():
	"""check if account is expired. If expired, do not allow login"""
	if not has_expired():
		return
	# if expired, stop user from logging in
	expires_on = formatdate(get_limits().get("expiry"))
	support_email = get_limits().get("support_email") or _("your provider")
	
	frappe.throw(_("""Your subscription expired on {0}.
		To extend please send an email to {1}""").format(expires_on, support_email),
		SiteExpiredError)

def get_expiry_message():
	if "System Manager" not in frappe.get_roles():
		return ""

	if not get_limits().get("expiry"):
		return ""

	expires_on = getdate(get_limits().get("expiry"))
	today = now_datetime().date()

	message = ""
	if today > expires_on:
		message = _("Your subscription has expired")
	else:
		days_to_expiry = (expires_on - today).days

		if days_to_expiry == 0:
			message = _("Your subscription will expire today")

		elif days_to_expiry == 1:
			message = _("Your subscription will expire tomorrow")

		elif days_to_expiry <= EXPIRY_WARNING_DAYS:
			message = _("Your subscription will expire on") + " " + formatdate(expires_on)

	return message


@frappe.whitelist()
def get_limits():
	limits = frappe.get_conf().get("limits") or {}
	day = frappe.utils.add_months(frappe.utils.today(), -1)
	limits["bulk_count"] = frappe.db.count("Bulk Email", filters={'creation': ['>', day]})
	return limits


def set_limits(limits):
		# Add/Update current config options in site_config
	frappe_limits = get_limits() or {}
	for key in limits.keys():
		frappe_limits[key] = limits[key]

	update_site_config("limits", frappe_limits, validate=False)


def clear_limit(limit):
	frappe_limits = get_limits()
	if limit in frappe_limits:
		del frappe_limits[limit]

	update_site_config("limits", frappe_limits, validate=False)
