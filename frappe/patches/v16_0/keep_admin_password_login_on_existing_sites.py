import click

import frappe
from frappe.utils.password import set_admin_password_login_setting


def execute():
	"""Keep Administrator password login working on existing sites."""
	set_admin_password_login_setting(0)
	click.secho(
		f"Warning: Administrator password login is left enabled on {frappe.local.site}, so the account is open to brute force attacks.\n"
		"Turn on 'Disable Administrator Password Login' in System Settings to prevent them.",
		fg="yellow",
	)
