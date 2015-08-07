# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def execute():
	language_map = {
		"中国（简体）": "簡體中文",
		"中國（繁體）": "正體中文"
	}

	language_in_system_settings = frappe.db.get_single_value("System Settings", "language")
	if language_in_system_settings in language_map:
		new_language_name = language_map[language_in_system_settings]
		frappe.db.set_value("System Settings", "System Settings", "language", new_language_name)

	for old_name, new_name in language_map.items():
		frappe.db.sql("""update `tabUser` set language=%(new_name)s where language=%(old_name)s""",
			{ "old_name": old_name, "new_name": new_name })
