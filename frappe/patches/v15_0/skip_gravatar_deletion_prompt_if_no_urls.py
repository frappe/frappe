from frappe.utils.legacy_gravatar_cleanup import skip_gravatar_deletion_prompt_if_no_urls


def execute():
	skip_gravatar_deletion_prompt_if_no_urls()
