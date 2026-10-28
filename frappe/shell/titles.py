# What the index draws for an app and a record: the app's title and logo, a record's plain title.

import frappe
from frappe import _
from frappe.desk.record_title import RecordTitles


def app_screen(app: str, screen: dict | None = None) -> dict:
	"""The app's title and logo, from its `add_to_apps_screen` entry."""
	if screen is None:
		screen = (frappe.get_hooks("add_to_apps_screen", app_name=app) or [{}])[0]
	return {
		"title": _(screen.get("title") or app.replace("_", " ").title()),
		"logo": screen.get("logo"),
	}


def readable_titles(doctype: str, names: list[str]) -> dict[str, str]:
	"""`{name: title}` for the records of `names` this person may read; a raising doctype lists none."""
	meta = frappe.get_meta(doctype)
	if meta.is_virtual or not frappe.has_permission(doctype, "read"):
		return {}

	if meta.issingle:
		return {doctype: _(doctype)} if doctype in names else {}

	names = list(set(names))
	titles = RecordTitles(doctype)
	try:
		rows = frappe.get_list(
			doctype, filters={"name": ("in", names)}, fields=["name", *titles.columns], limit=len(names)
		)
		return titles.of(rows)
	except Exception:
		frappe.log_error(title=f"Readable titles failed for {doctype}")
		return {}
