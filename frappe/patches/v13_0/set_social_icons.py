import frappe
from frappe.doctypes import SocialLoginKey


def execute():
	providers = frappe.get_all("Social Login Key")

	for provider in providers:
		doc = SocialLoginKey.docs.get(provider)
		doc.set_icon()
		doc.save()
