# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.core.doctype.user.user import update_gravatar

def execute():
	for name in frappe.db.sql_list("select name from `tabUser` where ifnull(user_image, '')=''"):
		user = frappe.get_doc("User", name)
		update_gravatar(user.name)
		user.db_set("user_image", user.user_image)
