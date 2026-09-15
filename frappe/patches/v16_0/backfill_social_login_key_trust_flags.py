import frappe


def execute():
	"""Preserve existing Social Login Key behavior."""
	frappe.reload_doctype("Social Login Key")

	social_login_key = frappe.qb.DocType("Social Login Key")

	frappe.qb.update(social_login_key).set(social_login_key.trust_email_without_verified_claim, 1).where(
		social_login_key.trust_email_without_verified_claim == 0
	).run()

	frappe.qb.update(social_login_key).set(social_login_key.trust_any_tenant, 1).where(
		(social_login_key.social_login_provider == "Office 365")
		& (social_login_key.trust_any_tenant == 0)
		& (social_login_key.tenant_id.isnull() | (social_login_key.tenant_id == ""))
	).run()
