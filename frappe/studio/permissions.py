"""Who may read an AI chat: the user it belongs to, and Administrator. A Studio User's role
rows open the DocTypes; these hooks keep other users' conversations out."""

import frappe


def has_session_permission(doc, ptype: str, user: str) -> bool:
	if user in (doc.user, "Administrator"):
		return True
	# deleting a page takes every chat on it with it, whoever they belong to
	return ptype == "delete" and frappe.has_permission("Studio Page", "delete", doc.page, user=user)


def session_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	return f"(`tabStudio AI Session`.`user` = {frappe.db.escape(user)})"


def has_message_permission(doc, ptype: str, user: str) -> bool:
	if user == "Administrator":
		return True
	return frappe.has_permission("Studio AI Session", ptype, doc.session, user=user)


def message_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	sessions = f"select `name` from `tabStudio AI Session` where `user` = {frappe.db.escape(user)}"
	return f"(`tabStudio AI Message`.`session` in ({sessions}))"
