# Copyright (c) 2017, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import validate_email_add

def execute():
	''' update/delete the email group member with the wrong email '''

	email_group_members = frappe.get_all("Email Group Member", fields=["name", "email"])
	for member in email_group_members:
		validated_email = validate_email_add(member.email)
		if (validated_email==member.email):
			pass
		else:
			try:
				frappe.db.set_value("Email Group Member", member.name, "email", validated_email)
			except Exception:
				frappe.delete_doc(doctype="Email Group Member", name=member.name, force=1, ignore_permissions=True)