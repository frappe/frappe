# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.desk.doctype.view_type import view_type
from frappe.model.document import Document

# Blank, not `None`: every `NULL` is distinct to the unique index, so a nullable column
# would let one doctype hold two site rows for one view.
SITE_ROW = ""
PLAIN_VIEW = ""

# Inserts a key may lose to other views of its doctype before the save is refused.
KEY_CLAIM_ATTEMPTS = 5

# Bytes of stored JSON; a list's columns, sort and quick filters fit in well under one.
SETTINGS_SIZE_LIMIT = 16 * 1024


class DuplicateViewError(frappe.ValidationError):
	pass


class DoctypeView(Document):
	"""One view of one doctype at one scope; `settings` is the view type's own shape."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		key: DF.Data
		key_slot: DF.Data | None
		label: DF.Data
		reference_doctype: DF.Link
		settings: DF.JSON | None
		type: DF.Data
		user: DF.Link
	# end: auto-generated types

	def before_insert(self):
		self.key = self.claim_key() if self.label else PLAIN_VIEW
		self.key_slot = self.key if self.key and not self.overrides_app_view() else None

	def validate(self):
		self.user = self.user or SITE_ROW
		self.label = self.label or PLAIN_VIEW
		self.key = self.key or PLAIN_VIEW
		self.validate_type()
		self.refuse_another_type_over_an_app_view()
		self.validate_settings()
		self.refuse_a_label_that_moves_the_view()
		self.refuse_a_second_row_at_this_address()

	def db_insert(self, *args, **kwargs):
		"""Insert the row; when another view took its key after `claim_key` read, claim the next one."""
		lost = set()
		while True:
			try:
				return self.insert_row(*args, **kwargs)
			except frappe.UniqueValidationError:
				if not self.key_slot:
					raise
				lost.add(self.key)
				self.refuse_a_lost_key(len(lost))
				self.key = self.key_slot = self.space().claim(self.flags.wanted_key, frozenset(lost))

	def insert_row(self, *args, **kwargs):
		"""`db_insert` in a savepoint, since Postgres aborts the transaction on a unique error."""
		# Its own name: a hash-name retry calls `db_insert` again, and MariaDB would reuse one savepoint.
		savepoint = f"doctype_view_{frappe.generate_hash(length=8)}"
		frappe.db.savepoint(savepoint)
		muted = frappe.flags.mute_messages
		# The unique index's "must be unique" message would reach the person even when a retry succeeds.
		frappe.flags.mute_messages = muted or bool(self.key_slot)
		try:
			super().db_insert(*args, **kwargs)
		except frappe.UniqueValidationError:
			frappe.db.rollback(save_point=savepoint)
			raise
		finally:
			frappe.flags.mute_messages = muted
		frappe.db.release_savepoint(savepoint)

	def refuse_a_lost_key(self, attempts: int):
		if attempts >= KEY_CLAIM_ATTEMPTS:
			frappe.throw(
				_("{0} already has a {1} view at this address.").format(
					frappe.bold(self.reference_doctype), self.type
				),
				title=_("Already Exists"),
				exc=DuplicateViewError,
			)

	def on_trash(self):
		if self.overridden_app_view():
			return  # the app view answers at this key again, so its stars and defaults still resolve
		if self.key:
			frappe.db.delete(
				"Favourite",
				{"reference_doctype": "DocType", "reference_name": self.reference_doctype, "view": self.key},
			)
		if self.key and self.user:
			frappe.db.delete(
				"Default View",
				{"reference_doctype": self.reference_doctype, "user": self.user, "view": self.key},
			)

	def claim_key(self) -> str:
		"""A key no layer of the doctype uses, from the key given or else the label."""
		if self.overrides_app_view():
			self.refuse_a_second_override()
			return self.key
		self.flags.wanted_key = self.key or self.label
		return self.space().claim(self.flags.wanted_key)

	def space(self):
		from .key_space import KeySpace

		return KeySpace(self.reference_doctype)

	def refuse_a_second_override(self):
		existing = frappe.db.get_value(
			self.doctype, {"reference_doctype": self.reference_doctype, "user": SITE_ROW, "key": self.key}
		)
		if existing:
			frappe.throw(
				_("The site already overrides the app view {0}. Edit {1} instead.").format(
					frappe.bold(self.key), frappe.bold(existing)
				),
				title=_("Already Exists"),
				exc=DuplicateViewError,
			)

	def overrides_app_view(self) -> bool:
		"""A site row at an app view's key keeps that key unclaimed, so a person's older view may share it."""
		return not self.user and bool(self.overridden_app_view())

	def overridden_app_view(self):
		"""The app view at this row's key, which a site row replaces whole and a person's own hides for them."""
		from .app_views import app_views

		return app_views(self.reference_doctype).get(self.key) if self.key else None

	def validate_type(self):
		if self.type not in view_type.view_types():
			frappe.throw(
				_("{0} is not a view type.").format(frappe.bold(self.type)), title=_("Unknown View Type")
			)
		view_type.refuse_where_it_does_not_apply(self.type, self.reference_doctype)

	def refuse_another_type_over_an_app_view(self):
		"""A site row at an app view's key replaces it for everyone, so it keeps the app view's type."""
		app_view = None if self.user else self.overridden_app_view()
		if app_view and app_view.type != self.type:
			frappe.throw(
				_("{0} overrides an app's {1} view, so it stays a {1} view.").format(
					frappe.bold(self.label), app_view.type
				),
				title=_("Wrong View Type"),
			)

	def validate_settings(self):
		"""One JSON object under the size cap, then the view type's own check of what is inside it."""
		stored = self.settings if isinstance(self.settings, str) else json.dumps(self.settings or {})

		if len(stored.encode()) > SETTINGS_SIZE_LIMIT:
			frappe.throw(
				_("The settings of this view are larger than {0} KB.").format(SETTINGS_SIZE_LIMIT // 1024),
				title=_("Settings Too Large"),
			)

		try:
			parsed = frappe.parse_json(stored)
		except ValueError:
			parsed = None

		if not isinstance(parsed, dict):
			frappe.throw(_("The settings of a view are one object."), title=_("Not Settings"))

		view_type.validate_settings(self.type, self.reference_doctype, parsed)

	def refuse_a_label_that_moves_the_view(self):
		"""A saved view keeps a label and the plain view has none: the key, set once, says which it is."""
		if bool(self.label) != bool(self.key):
			frappe.throw(
				_("A saved view needs a label, and the plain view cannot have one."),
				title=_("Label Not Allowed"),
			)

	def refuse_a_second_row_at_this_address(self):
		"""Refuse the duplicate here: `db_insert` would read the unique index's refusal as a lost key and move on."""
		existing = frappe.db.get_value(self.doctype, self.address())

		if existing and existing != self.name:
			frappe.throw(
				_("{0} already has a {1} view at this address. Edit {2} instead.").format(
					frappe.bold(self.reference_doctype), self.type, frappe.bold(existing)
				),
				title=_("Already Exists"),
				exc=DuplicateViewError,
			)

	def address(self) -> dict:
		return {
			"reference_doctype": self.reference_doctype,
			"type": self.type,
			"user": self.user,
			"key": self.key,
		}


def on_doctype_update():
	"""One row per address and one saved view per key, held by the schema; one person's views by `user`."""
	frappe.db.add_unique(
		"Doctype View",
		("reference_doctype", "type", "user", "key"),
		constraint_name="unique_view_address",
	)
	frappe.db.add_unique("Doctype View", ("reference_doctype", "key_slot"), constraint_name="unique_view_key")
	frappe.db.add_index("Doctype View", ["user", "reference_doctype"])


def is_site_administrator(user: str | None = None) -> bool:
	user = user or frappe.session.user

	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def has_permission(doc, ptype="read", user=None, debug=False):
	"""A System Manager may see every row; everyone else the site's rows and their own."""
	user = user or frappe.session.user
	if is_site_administrator(user):
		return True

	if ptype == "read":
		return doc.user in (SITE_ROW, user)

	return bool(doc.user) and doc.user == user


def get_permission_query_conditions(user=None, doctype="Doctype View"):
	"""The list-query half of `has_permission`: reports, the API and export go through this."""
	user = user or frappe.session.user
	if is_site_administrator(user):
		return None

	return frappe.qb.DocType(doctype).user.isin([SITE_ROW, user])
