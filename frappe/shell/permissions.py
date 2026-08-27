# The front door of a prefix.
#
# #42112: the gate buys a decent page, not security. Every whitelisted endpoint behind
# it is directly callable, so doctype permissions remain the real boundary. What this
# decides is whether a user gets the shell document or a refusal.

from urllib.parse import urlencode

import frappe
from frappe import _


def default_app_permission() -> bool:
	""" "Is a System User" — what `/desk` has always meant.

	This reproduces `frappe/www/desk.py:20-27` rather than reusing
	`add_to_apps_screen[].has_permission`, which would *narrow* it: frappe's entry
	there is `check_app_permission`, System User **and** System Manager, because the
	apps-screen hook means tile visibility rather than access.
	"""
	if frappe.session.user == "Guest":
		return False

	# The session carries `user_type` during an ordinary request, and that is the
	# cheap read. It is absent off-request — background jobs, tests, `bench execute` —
	# where falling back to the User record answers the same question rather than
	# silently denying everyone.
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
		# Deliberately asymmetric with `app_boot`, which degrades (#42070). A broken
		# contributor costs its boot keys; a broken gate costs the door, because
		# failing open is the one outcome a gate may not have.
		frappe.log_error(title=f"app_permission failed for {app}")
		return False


def guard_prefix(app: str, path: str):
	"""Raise the right refusal for a user who may not enter this prefix.

	Guest is bounced to login carrying a `redirect-to`; anyone else gets a 403 through
	`NotPermittedPage`. Both paths already exist and are reached through the seam
	`serve.py` maps exceptions to, so the shell adds no new error surface.
	"""
	if has_app_permission(app):
		return

	if frappe.session.user == "Guest":
		frappe.response["status_code"] = 403
		frappe.msgprint(_("Log in to access this page."))
		frappe.redirect(f"/login?{urlencode({'redirect-to': path})}")

	frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)
