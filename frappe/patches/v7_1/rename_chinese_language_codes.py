import frappe

def execute():
	frappe.rename_doc('Language', 'zh-cn', 'zh', force=True,
		merge=True if frappe.db.exists('Language', 'zh') else False)
	frappe.rename_doc('Language', 'zh-tw', 'zh-TW', force=True)
	frappe.db.set_value('Language', 'zh', 'language_code', 'zh')
	frappe.db.set_value('Language', 'zh-TW', 'language_code', 'zh-TW')