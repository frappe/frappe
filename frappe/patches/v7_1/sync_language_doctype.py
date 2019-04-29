from __future__ import unicode_literals
import frappe
from frappe.translate import get_lang_dict

def execute():
	frappe.reload_doc('core', 'doctype', 'language')

	from frappe.core.doctype.language.language import sync_languages
	sync_languages()

	# move language from old style to new style for old accounts
	# i.e. from "english" to "en"

	lang_dict = get_lang_dict()
	language = frappe.db.get_value('System Settings', None, 'language')
	if language:
		frappe.db.set_value('System Settings', None, 'language', lang_dict.get('language') or 'en')

	for user in frappe.get_all('User', fields=['name', 'language']):
		if user.language:
			frappe.db.set_value('User', user.name, 'language',
				lang_dict.get('language') or 'en', update_modified=False)
