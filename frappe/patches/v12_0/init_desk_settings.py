from __future__ import unicode_literals

import json
import frappe
from frappe.config import get_modules_from_all_apps_for_user
from frappe.desk.moduleview import get_onboard_items

def execute():
	"""Reset the initial customizations for desk, with modules, indices and links."""
	frappe.reload_doc("core", "doctype", "user")
	frappe.db.sql("""update tabUser set home_settings = ''""")
