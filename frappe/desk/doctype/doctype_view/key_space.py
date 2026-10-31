# One doctype's view keys: every layer's saved views share them, so a key names one view.

import re
import unicodedata

import frappe
from frappe import _
from frappe.desk.doctype.view_type.view_type import type_keys

from .app_views import app_views
from .doctype_view import PLAIN_VIEW, SITE_ROW

# The candidates of "which view types survive" (#45854), held until that grilling rules; a dropped one is released.
SURVIVOR_CANDIDATES = frozenset(
	{"report", "calendar", "gantt", "tree", "image", "inbox", "map", "dashboard", "cards"}
)

# Kanban's before it is a type; `/<doctype>/view/record` is the standard page of the record named "view".
HELD_KEYS = frozenset({"kanban", "record"})

KEY_LENGTH_LIMIT = 60
RANDOM_KEY_LENGTH = 8


class KeySpace:
	"""The keys of one doctype's saved views, across each person's rows and the site's."""

	def __init__(self, doctype: str):
		self.doctype = doctype

	def find(self, key: str, user: str | None = None) -> frappe._dict | None:
		"""The view at `key` that `user` sees: their own, else the site's, else an app's."""
		found = find_views([(self.doctype, key)], user)
		return found.get((self.doctype, key))

	def claim(self, wanted: str, lost: frozenset[str] = frozenset()) -> str:
		"""A free key from `wanted` made URL-safe, with a suffix when taken or `lost` to another insert."""
		base = url_safe(wanted) or frappe.generate_hash(length=RANDOM_KEY_LENGTH)
		taken = self.taken(base) | lost
		if base not in taken:
			return base

		suffix = 2
		while f"{base}-{suffix}" in taken:
			suffix += 1
		return f"{base}-{suffix}"

	def taken(self, base: str) -> set[str]:
		"""The keys a new view cannot have that start with `base`: reserved names, every person's, the site's and the apps'."""
		view = frappe.qb.DocType("Doctype View")
		# A plain read misses keys committed after this transaction's snapshot; the insert's unique index catches those.
		keys = (
			frappe.qb.from_(view)
			.select(view.key)
			.where(view.reference_doctype == self.doctype)
			.where((view.key == base) | view.key.like(f"{base}-%"))
			.run(pluck=True)
		)
		return set(keys) | reserved_keys() | set(app_views(self.doctype))


def reserved_keys() -> frozenset[str]:
	"""Keys no saved view may take: `/<doctype>/view/<type>` is the plain view of each `View Type`."""
	return frozenset(type_keys()) | SURVIVOR_CANDIDATES | HELD_KEYS


def find_views(
	targets: list[tuple[str, str]], user: str | None = None
) -> dict[tuple[str, str], frappe._dict]:
	"""`{(doctype, key): view}` for each target `user` sees, their own before the site's before an app's; one query."""
	user = user or frappe.session.user
	keys = {key for _doctype, key in targets if key and key != PLAIN_VIEW}
	if not keys:
		return {}

	rows = frappe.get_all(
		"Doctype View",
		filters={
			"reference_doctype": ("in", {doctype for doctype, _key in targets}),
			"key": ("in", keys),
			"user": ("in", (user, SITE_ROW)),
		},
		fields=["name", "reference_doctype", "key", "label", "type", "user"],
	)
	found = {target: app_row(*target) for target in targets if target[1] in app_views(target[0])}
	for row in sorted(rows, key=lambda row: row.user != SITE_ROW):
		found[(row.reference_doctype, row.key)] = row  # the site's first, so the person's own overwrites it
	return {target: found[target] for target in targets if target in found}


def app_row(doctype: str, key: str) -> frappe._dict:
	"""An app view in a row's shape; it has no row name and no user."""
	view = app_views(doctype)[key]
	return frappe._dict(
		name=None,
		reference_doctype=doctype,
		key=key,
		label=_(view.label),
		type=view.type,
		user=None,
		app=view.app,
	)


def url_safe(label: str) -> str:
	"""The label in lower-case ASCII letters and digits, words joined by `-`; blank when none are left."""
	ascii_label = unicodedata.normalize("NFKD", label or "").encode("ascii", "ignore").decode()
	words = re.sub(r"[^a-z0-9]+", "-", ascii_label.lower()).strip("-")
	return words[:KEY_LENGTH_LIMIT].rstrip("-")
