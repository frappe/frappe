from __future__ import unicode_literals
import frappe

def execute():
	frappe.rename_doc('Language', 'zh-cn', 'zh', force=True,
		merge=True if frappe.db.exists('Language', 'zh') else False)
	if frappe.db.get_value('Language', 'zh-tw') == 'zh-tw':
		frappe.rename_doc('Language', 'zh-tw', 'zh-TW', force=True)

	frappe.db.set_value('Language', 'zh', 'language_code', 'zh')
	frappe.db.set_value('Language', 'zh-TW', 'language_code', 'zh-TW')