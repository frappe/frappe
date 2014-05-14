# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from collections import Counter
from frappe.core.doctype.user.user import STANDARD_USERS

def execute():
	if frappe.db.get_value("System Settings", "System Settings", "language"):
		return

	# find most common language
	lang = frappe.db.sql_list("""select language from `tabUser`
		where ifnull(language, '')!='' and language not like "Loading%%" and name not in ({standard_users})""".format(
		standard_users=", ".join(["%s"]*len(STANDARD_USERS))), tuple(STANDARD_USERS))
	lang = Counter(lang).most_common(1)
	lang = (len(lang) > 0) and lang[0][0] or "english"

	# set language in System Settings
	system_settings = frappe.get_doc("System Settings")
	system_settings.language = lang
	system_settings.ignore_mandatory = True
	system_settings.save()
