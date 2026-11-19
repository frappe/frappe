# The index's Favourites: the person's starred records, lists and saved views, newest first.

from urllib.parse import quote

import frappe
from frappe import _
from frappe.desk.doctype.favourite.favourite import LIST, may_read_list, readable_views

from .doctypes import get_doctype_owners
from .links import canonical_path
from .permissions import has_app_permission
from .titles import app_screen, readable_titles

# Chips drawn at boot; one more row is read to tell whether a "More" chip is drawn.
SHOWN = 8
# Rows the "More" chip reads after the first `SHOWN`.
MORE_LIMIT = 50


def index_favourites() -> dict:
	"""Boot's keys: the chips of the person's first `SHOWN` favourites, and whether more rows exist."""
	rows = favourite_rows(0, SHOWN + 1)
	return {"favourites": Chips(rows[:SHOWN]).draw(), "more_favourites": len(rows) > SHOWN}


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def more_favourites() -> list[dict]:
	"""The chips after the first `SHOWN`, at most `MORE_LIMIT` rows, with boot's read checks."""
	# `@frappe.whitelist()` only excludes Guest; a Website User has no index.
	if not has_app_permission("frappe"):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	return Chips(favourite_rows(SHOWN, MORE_LIMIT)).draw()


def favourite_rows(start: int, limit: int) -> list[frappe._dict]:
	return frappe.get_all(
		"Favourite",
		filters={"user": frappe.session.user},
		fields=["reference_doctype", "reference_name", "view"],
		# `name` breaks ties, so the More call's offset continues boot's order exactly.
		order_by="creation desc, name desc",
		limit_start=start,
		limit_page_length=limit,
	)


class Chips:
	"""Chips for Favourite rows, less those whose record, list or view the person can no longer open."""

	def __init__(self, rows: list[frappe._dict]):
		self.rows = rows
		self.owners = get_doctype_owners()
		self.views = readable_views([(row.reference_name, row.view) for row in rows if row.view])
		self.apps: dict[str, bool] = {}
		self.titles = self.record_titles()

	def draw(self) -> list[dict]:
		chips = []
		for row in self.rows:
			target = self.target(row)
			if target is None:
				continue

			doctype, chip = target
			screen = app_screen(self.owners[doctype])
			chips.append(
				{
					"doctype": row.reference_doctype,
					"name": row.reference_name,
					**chip,
					"app": self.owners[doctype],
					"app_title": screen["title"],
					"app_logo": screen["logo"],
				}
			)
		return chips

	def target(self, row: frappe._dict) -> tuple[str, dict] | None:
		"""The doctype whose app the chip belongs to, and its kind, title and route; None if unreadable."""
		if row.reference_doctype == LIST and row.view:
			return self.view_chip(row.reference_name, row.view)
		if row.reference_doctype == LIST:
			return self.list_chip(row.reference_name)
		return self.record_chip(row.reference_doctype, row.reference_name)

	def record_chip(self, doctype: str, name: str) -> tuple[str, dict] | None:
		title = self.titles.get(doctype, {}).get(name)
		if title is None:
			return None
		return doctype, {"kind": "record", "title": title, "route": canonical_path(doctype, name)}

	def list_chip(self, doctype: str) -> tuple[str, dict] | None:
		if not self.may_open(doctype) or not may_read_list(doctype):
			return None
		return doctype, {"kind": "list", "title": _(doctype), "route": canonical_path(doctype)}

	def view_chip(self, doctype: str, key: str) -> tuple[str, dict] | None:
		view = self.views.get((doctype, key))
		if view is None or not self.may_open(doctype):
			return None

		route = f"{canonical_path(doctype)}/view/{quote(key, safe='')}"
		return doctype, {"view": key, "kind": "view", "title": view.label, "route": route}

	def record_titles(self) -> dict[str, dict[str, str]]:
		names_by_doctype: dict[str, list[str]] = {}
		for row in self.rows:
			if row.reference_doctype != LIST:
				names_by_doctype.setdefault(row.reference_doctype, []).append(row.reference_name)

		return {
			doctype: readable_titles(doctype, names)
			for doctype, names in names_by_doctype.items()
			if self.may_open(doctype)
		}

	def may_open(self, doctype: str) -> bool:
		"""The doctype has an address, and the person may enter the app that owns it."""
		app = self.owners.get(doctype)
		if app and app not in self.apps:
			self.apps[app] = has_app_permission(app)
		return bool(app and self.apps[app])
