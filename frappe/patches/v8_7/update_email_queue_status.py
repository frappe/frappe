from __future__ import unicode_literals
import frappe
from frappe.email.smtp import get_default_outgoing_email_account

def execute():
	# set the email queue status to Not Sent if google_analytics_id is UA-8911157-19
	default_email_account = get_default_outgoing_email_account()

	if frappe.conf.get("google_analytics_id") == "UA-8911157-19" or \
		(default_email_account and default_email_account.email_id == "notifications@erpnext.com"):

		frappe.db.sql("""update `tabEmail Queue` set status='Not Sent' where
			creation>=DATE_SUB(NOW(), INTERVAL 16 HOUR)""")