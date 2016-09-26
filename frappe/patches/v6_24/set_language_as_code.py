import frappe

from frappe.translate import get_lang_dict

# migrate language from name to code
def execute():
	language = frappe.db.get_value('System Settings', None, 'language')
	if language:
		system_settings = frappe.get_doc('System Settings', 'System Settings')
		if get_lang_dict().get(language, language) != system_settings.language:
			system_settings.language = get_lang_dict().get(language, language)
			system_settings.flags.ignore_mandatory=True
			system_settings.save()

	for user in frappe.get_all('User', fields=['name', 'language']):
		if user.language:
			frappe.db.set_value('User', user.name, 'language',
				get_lang_dict().get(user.language, user.language), update_modified=False)
