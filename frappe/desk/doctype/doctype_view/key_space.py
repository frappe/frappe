# One doctype's view keys: every layer's saved views share them, so a key names one view.

import re
import unicodedata

import frappe

from .doctype_view import PLAIN_VIEW, SITE_ROW, VIEW_TYPES

# `/<doctype>/view/<type>` is that type's own page, so a type's name is never a key; Kanban's before it exists.
# `/<doctype>/view/record` is the standard page of the record named "view".
RESERVED_KEYS = frozenset({type.lower() for type in VIEW_TYPES} | {"kanban", "record"})

KEY_LENGTH_LIMIT = 60
RANDOM_KEY_LENGTH = 8


class KeySpace:
	"""The keys of one doctype's saved views, across each person's rows and the site's."""

	def __init__(self, doctype: str):
		self.doctype = doctype

	def find(self, key: str, user: str | None = None) -> frappe._dict | None:
		"""The view at `key` that `user` sees: their own, else the site's."""
		found = find_views([(self.doctype, key)], user)
		return found.get((self.doctype, key))

	def claim(self, wanted: str) -> str:
		"""A free key from `wanted` made URL-safe, with a suffix when taken; hold `lock` until the insert commits."""
		base = url_safe(wanted) or frappe.generate_hash(length=RANDOM_KEY_LENGTH)
		taken = self.taken(base)
		if base not in taken:
			return base

		suffix = 2
		while f"{base}-{suffix}" in taken:
			suffix += 1
		return f"{base}-{suffix}"

	def taken(self, base: str) -> set[str]:
		"""The keys a new view cannot have that start with `base`: reserved names, and every person's and the site's."""
		view = frappe.qb.DocType("Doctype View")
		# A locking read sees keys committed after this transaction's snapshot; a plain one misses them.
		keys = (
			frappe.qb.from_(view)
			.select(view.key)
			.where(view.reference_doctype == self.doctype)
			.where((view.key == base) | view.key.like(f"{base}-%"))
			.for_update()
			.run(pluck=True)
		)
		return set(keys) | RESERVED_KEYS

	def lock(self):
		"""Hold the doctype's own row, so two new views of it cannot claim one key at once."""
		frappe.db.get_value("DocType", self.doctype, "name", for_update=True)


def find_views(
	targets: list[tuple[str, str]], user: str | None = None
) -> dict[tuple[str, str], frappe._dict]:
	"""`{(doctype, key): view}` for each target `user` sees, their own before the site's; one query."""
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
	found = {}
	for row in sorted(rows, key=lambda row: row.user != SITE_ROW):
		found[(row.reference_doctype, row.key)] = row  # the site's first, so the person's own overwrites it
	return {target: found[target] for target in targets if target in found}


def url_safe(label: str) -> str:
	"""The label in lower-case ASCII letters and digits, words joined by `-`; blank when none are left."""
	ascii_label = unicodedata.normalize("NFKD", label or "").encode("ascii", "ignore").decode()
	words = re.sub(r"[^a-z0-9]+", "-", ascii_label.lower()).strip("-")
	return words[:KEY_LENGTH_LIMIT].rstrip("-")
