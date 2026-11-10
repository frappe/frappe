# What the index draws for an app and a record: the app's title and logo, a record's plain title.

import frappe
from frappe import _
from frappe.desk.record_title import RecordTitles
from frappe.utils.caching import request_cache

BRAND_KEYS = ("title", "logo", "favicon")


def app_screen(app: str, screen: dict | None = None) -> dict:
	"""The app's title and logo: its `add_to_apps_screen` entry, over what its `brand` hook returns."""
	if screen is None:
		screen = (frappe.get_hooks("add_to_apps_screen", app_name=app) or [{}])[0]
	brand = app_brand(app)
	return {
		"title": brand.get("title") or _(screen.get("title") or app.replace("_", " ").title()),
		"logo": brand.get("logo") or screen.get("logo"),
	}


@request_cache
def app_brand(app: str) -> dict:
	"""The strings of `{title, logo, favicon}` that the `brand` of the app's `add_to_apps_screen` entry returns.

	A hook that raises, or returns no dict, brands nothing and is logged.
	"""
	screen = (frappe.get_hooks("add_to_apps_screen", app_name=app) or [{}])[0]
	if not screen.get("brand"):
		return {}

	try:
		brand = frappe.get_attr(screen["brand"])()
		if not isinstance(brand, dict):
			raise TypeError(f"brand returned {type(brand).__name__}, not a dict")
	except Exception:
		frappe.log_error(title=f"add_to_apps_screen brand failed for {app}")
		return {}

	return {key: brand[key] for key in BRAND_KEYS if brand.get(key) and isinstance(brand[key], str)}


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
