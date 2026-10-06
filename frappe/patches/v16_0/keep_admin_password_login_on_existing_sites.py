import frappe
from frappe.core.doctype.system_settings.system_settings import set_admin_password_login_setting
from frappe.utils.install import warn_admin_password_login_enabled


def execute():
	"""Keep Administrator password login working on existing sites."""
	set_admin_password_login_setting(0)
	warn_admin_password_login_enabled(
		f"Warning: Administrator password login is left enabled on {frappe.local.site}, so the account is open to brute force attacks.\n"
		"Turn on 'Disable Administrator Password Login' in System Settings to prevent them."
	)
