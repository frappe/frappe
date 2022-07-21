import frappe
from frappe.patches.v13_0.encrypt_2fa_secrets import DOCTYPE
from frappe.patches.v13_0.encrypt_2fa_secrets import PARENT_FOR_DEFAULTS as TWOFACTOR_PARENT
from frappe.utils import cint


def execute():
	"""
	This patch is needed to fix parent incorrectly set as `__2fa` because of
	https://github.com/frappe/frappe/commit/a822092211533ff17ff9b92dd86f6f868ed63e2e
	"""

	if not frappe.db.get_value(
		DOCTYPE, {"parent": TWOFACTOR_PARENT, "defkey": ("not like", "%_otp%")}, "defkey"
	):
		return

	# system settings
	system_settings = frappe.get_single("System Settings")
	system_settings.set_defaults()

	# home page
	frappe.db.set_default(
		"desktop:home_page", "workspace" if cint(system_settings.setup_complete) else "setup-wizard"
	)

	# letter head
	try:
		letter_head = frappe.get_doc("Letter Head", {"is_default": 1})
		letter_head.set_as_default()

	except frappe.DoesNotExistError:
		pass

	# other app defaults
	for doctype in (
		"Accounts Settings",
		"Stock Settings",
		"Selling Settings",
		"Buying Settings",
		"CRM Settings",
		"Global Defaults",
		"Healthcare Settings",
		"Education Settings",
	):
		if not frappe.db.exists("DocType", doctype):
			continue

		try:
			frappe.get_single(doctype).save()
		except Exception:
			pass

	# pos profile
	if frappe.db.exists("DocType", "POS Profile"):
		pos_profile = frappe.get_last_doc("POS Profile")
		try:
			pos_profile.set_defaults()
		except Exception:
			pass
