# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.model.document import Document
from frappe.utils import cint, today


class SystemSettings(Document):
	def validate(self):
		from frappe.twofactor import toggle_two_factor_auth

		enable_password_policy = cint(self.enable_password_policy) and True or False
		minimum_password_score = cint(getattr(self, "minimum_password_score", 0)) or 0
		if enable_password_policy and minimum_password_score <= 0:
			frappe.throw(_("Please select Minimum Password Score"))
		elif not enable_password_policy:
			self.minimum_password_score = ""

		for key in ("session_expiry", "session_expiry_mobile"):
			if self.get(key):
				parts = self.get(key).split(":")
				if len(parts) != 2 or not (cint(parts[0]) or cint(parts[1])):
					frappe.throw(_("Session Expiry must be in format {0}").format("hh:mm"))

		if self.enable_two_factor_auth:
			if self.two_factor_method == "SMS":
				if not frappe.db.get_single_value("SMS Settings", "sms_gateway_url"):
					frappe.throw(
						_("Please setup SMS before setting it as an authentication method, via SMS Settings")
					)
			toggle_two_factor_auth(True, roles=["All"])
		else:
			self.bypass_2fa_for_retricted_ip_users = 0
			self.bypass_restrict_ip_check_if_2fa_enabled = 0

		frappe.flags.update_last_reset_password_date = False
		if self.force_user_to_reset_password and not cint(
			frappe.db.get_single_value("System Settings", "force_user_to_reset_password")
		):
			frappe.flags.update_last_reset_password_date = True

		self.validate_user_pass_login()

	def validate_user_pass_login(self):
		if not self.disable_user_pass_login:
			return

		social_login_enabled = frappe.db.exists("Social Login Key", {"enable_social_login": 1})
		ldap_enabled = frappe.db.get_single_value("LDAP Settings", "enabled")

		if not (social_login_enabled or ldap_enabled):
			frappe.throw(
				_(
					"Please enable atleast one Social Login Key or LDAP before disabling username/password based login."
				)
			)

	def on_update(self):
		self.set_defaults()

		frappe.cache().delete_value("system_settings")
		frappe.cache().delete_value("time_zone")

		if frappe.flags.update_last_reset_password_date:
			update_last_reset_password_date()

	def set_defaults(self):
		from frappe.translate import set_default_language

		for df in self.meta.get("fields"):
			if df.fieldtype not in no_value_fields and self.has_value_changed(df.fieldname):
				frappe.db.set_default(df.fieldname, self.get(df.fieldname))

		if self.language:
			set_default_language(self.language)


def update_last_reset_password_date():
	frappe.db.sql(
		""" UPDATE `tabUser`
		SET
			last_password_reset_date = %s
		WHERE
			last_password_reset_date is null""",
		today(),
	)


@frappe.whitelist()
def load():
	from frappe.utils.momentjs import get_all_timezones

	if not "System Manager" in frappe.get_roles():
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	all_defaults = frappe.db.get_defaults()
	defaults = {}

	for df in frappe.get_meta("System Settings").get("fields"):
		if df.fieldtype in ("Select", "Data"):
			defaults[df.fieldname] = all_defaults.get(df.fieldname)

	return {"timezones": get_all_timezones(), "defaults": defaults}
