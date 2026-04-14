# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_datetime, now_datetime
from frappe.utils.user import get_users_with_role


def check_security_txt_expiry():
	security_settings = frappe.get_doc("Security Settings")
	if not security_settings.public_expires:
		return
	expires = security_settings.public_expires
	if isinstance(expires, str):
		expires = get_datetime(expires)
	now = now_datetime()
	days_until_expiry = (expires - now).days
	alert_days = [30, 15, 7, 1]
	if days_until_expiry in alert_days:
		send_expiry_alert(frappe.local.site, expires, days_until_expiry)


def send_expiry_alert(site: str, expires, days_until_expiry: int):
	recipients = get_users_with_role("System Manager")
	if not recipients:
		return
	subject = get_email_subject(site, days_until_expiry)
	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		template="security_txt_expiry_alert",
		args={
			"site": site,
			"expires": expires,
			"days_remaining": days_until_expiry,
		},
	)


def get_email_subject(site: str, days_until_expiry: int) -> str:
	if days_until_expiry == 1:
		return f"[URGENT] Security.txt expires in 1 day - {site}"
	return f"Security.txt expires in {days_until_expiry} days - {site}"
