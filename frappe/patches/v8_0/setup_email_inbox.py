from __future__ import unicode_literals
import frappe, json
from frappe.core.doctype.user.user import ask_pass_update, setup_user_email_inbox

def execute():
	""" 
		depricate email inbox page if exists
		remove desktop icon for email inbox page if exists
		patch to remove Custom DocPerm for communication
	"""

	if frappe.db.exists("Page", "email_inbox"):
		frappe.delete_doc("Page", "email_inbox")

	desktop_icon = frappe.db.get_value("Desktop Icon", {
		"module_name": "Email",
		"type": "Page",
		"link": "email_inbox"
	})

	if desktop_icon:
		frappe.delete_doc("Desktop Icon", desktop_icon)

	frappe.db.sql("""update `tabCustom DocPerm` set `write`=0, email=1 where parent='Communication'""")

	setup_inbox_from_email_account()

def setup_inbox_from_email_account():
	""" add user inbox child table entry for existing email account in not exists """

	frappe.reload_doc("core", "doctype", "user_email")
	frappe.reload_doc("email", "doctype", "email_account")

	email_accounts = frappe.get_all("Email Account", filters={"enable_incoming": 1},
		fields=["name", "email_id", "awaiting_password", "enable_outgoing"])

	for email_account in email_accounts:
		setup_user_email_inbox(email_account.get("name"), email_account.get("awaiting_password"),
			email_account.get("email_id"), email_account.get("enabled_outgoing"))