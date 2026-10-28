# What the index draws for an app and a record: the app's title and logo, a record's plain title.

from html import unescape

import frappe
from frappe import _
from frappe.desk.link_title import get_link_titles
from frappe.utils import cstr, strip_html


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

	try:
		titles = get_link_titles(doctype, meta.title_field or "name", set(names))
	except Exception:
		frappe.log_error(title=f"Readable titles failed for {doctype}")
		return {}

	return {name: plain_text(title) or name for name, title in titles.items()}


def plain_text(value) -> str:
	"""A title field may be a Text Editor; a chip draws text."""
	return unescape(strip_html(cstr(value))).strip()
