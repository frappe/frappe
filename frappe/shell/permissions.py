# The front door of a prefix: whether a user gets the shell document or a refusal.
# The gate buys a decent page, not security; doctype permissions remain the real boundary.

from urllib.parse import urlencode

import frappe
from frappe import _


def default_app_permission() -> bool:
	"""What `/desk` has always meant: "Is a System User"."""
	# Not `add_to_apps_screen[].has_permission`: frappe's entry there also wants System Manager.
	if frappe.session.user == "Guest":
		return False

	# `user_type` is on the session in a request and absent off-request (jobs, tests, `bench execute`).
	user_type = frappe.session.data.get("user_type") if frappe.session.data else None
	if not user_type:
		user_type = frappe.get_cached_value("User", frappe.session.user, "user_type")

	return user_type == "System User"


def has_app_permission(app: str) -> bool:
	handler = frappe.get_hooks("app_permission", app_name=app)
	if not handler:
		return default_app_permission()

	try:
		return bool(frappe.get_attr(handler[0])())
	except Exception:
		# A broken gate fails closed, unlike a broken `app_boot` contributor, which only loses its keys.
		frappe.log_error(title=f"app_permission failed for {app}")
		return False


def guard_prefix(app: str, path: str):
	"""Raise the right refusal: Guest is bounced to login, anyone else gets a 403."""
	if has_app_permission(app):
		return

	if frappe.session.user == "Guest":
		frappe.response["status_code"] = 403
		frappe.msgprint(_("Log in to access this page."))
		frappe.redirect(f"/login?{urlencode({'redirect-to': path})}")

	frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)
