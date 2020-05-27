from __future__ import unicode_literals
import frappe

def execute():
	if frappe.db.get_single_value('System Settings', 'language') == 'zh-TW':
		frappe.db.set_value('System Settings', 'System Settings', 'language', 'zh_tw')

	frappe.db.sql("UPDATE `tabUser` SET `language`='zh_tw' WHERE `language`='zh-TW'")

	frappe.delete_doc('Language', 'zh-TW')