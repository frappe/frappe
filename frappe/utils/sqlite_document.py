# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See license.txt

"""Base controller for DocTypes whose rows live in the site's SQLite log database.

The connection itself, and the helpers that open and shape it, are in
:mod:`frappe.utils.logging`. This module holds only the `Document` subclass that routes
a DocType's persistence through it.
"""

import json

import frappe
from frappe.database.utils import commit_after_response
from frappe.model.document import Document
from frappe.utils.logging import ensure_log_table, get_log_db, log_table


class SQLiteLogDocument(Document):
	"""Base controller for log DocTypes that store their rows in the log database.
	Log DocTypes are declared `is_virtual`, which tells the framework it owns no table
	for them in the site's primary database, and routes persistence and listing through
	the controller. This class implements that contract against :func:`get_log_db`,
	so a log DocType only has to subclass it.

	Writes commit immediately on the log connection. That is the point of the design:
	a record of a failure has to outlive the primary transaction that failed.
	"""

	# ============ instance methods ============

	def db_insert(self, *args, **kwargs):
		"""Insert this document into the log database."""
		from frappe.model.naming import set_new_name

		if not self.name:
			set_new_name(self)

		# `BaseDocument.db_insert` stamps these when they are unset, and callers rely on it:
		# `make_access_log` reaches for `db_insert` directly rather than `insert`, which is the
		# path that would otherwise have filled them in. Without this the row lands with a NULL
		# `creation`, which hides it from retention (`creation < cutoff` never matches) and from
		# the default `creation desc` ordering.
		if not self.creation:
			self.creation = self.modified = frappe.utils.now()
			self.owner = self.modified_by = frappe.session.user

		d = self.get_valid_dict(convert_dates_to_str=True, ignore_virtual=True)

		qb, table = log_table(self.doctype)
		db = get_log_db()

		try:
			db.sql(qb.into(table).columns(*d.keys()).insert(*d.values()))
		except Exception as e:
			# Mirrors `BaseDocument.db_insert`. Log DocTypes are named by hash, and a collision
			# has to be retried with a fresh name rather than surfacing -- `_handle_hash_conflict`
			# clears `name` and calls back in here, giving up after five tries. Anything else is
			# re-raised as `DuplicateEntryError` so callers that retry on it keep working
			# (`make_access_log` is decorated with exactly that retry).
			if not db.is_primary_key_violation(e):
				raise

			if self.meta.autoname == "hash":
				return self._handle_hash_conflict()

			raise frappe.DuplicateEntryError(self.doctype, self.name, e) from e

		db.commit()

		self.set("__islocal", False)

	def db_update(self, *args, **kwargs):
		"""Update this document in the log database."""
		if self.get("__islocal") or not self.name:
			self.db_insert()
			return

		d = self.get_valid_dict(convert_dates_to_str=True, ignore_virtual=True)

		# `name` addresses the row rather than being updated.
		name = d.pop("name")

		qb, table = log_table(self.doctype)
		query = qb.update(table)

		for fieldname, value in d.items():
			query = query.set(table[fieldname], value)

		db = get_log_db()
		db.sql(query.where(table.name == name))
		db.commit()

	def db_set(self, fieldname, value=None, update_modified=True, notify=False, commit=False):
		"""Write specific fields straight to the log database.

		`Document.db_set` goes through `frappe.db.set_value`, which targets the primary
		database -- where a log DocType has no table. The field handling, `modified` bump and
		`before_change` / `on_change` hooks are kept identical; only the UPDATE moves.

		`commit` is accepted for signature compatibility but ignored: the log connection is
		committed here regardless, and committing the primary transaction is not this
		method's business.
		"""
		if isinstance(fieldname, dict):
			self.update(fieldname)
		else:
			self.set(fieldname, value)

		if update_modified and (self.doctype, self.name) not in frappe.flags.currently_saving:
			self.set("modified", frappe.utils.now())
			self.set("modified_by", frappe.session.user)

		if not self.get_doc_before_save():
			self.load_doc_before_save()

		self.run_method("before_change")

		if self.name is None:
			return

		columns = list(fieldname) if isinstance(fieldname, dict) else [fieldname]
		if update_modified:
			columns += ["modified", "modified_by"]

		qb, table = log_table(self.doctype)
		query = qb.update(table)

		for column in columns:
			query = query.set(table[column], self.get(column))

		db = get_log_db()
		db.sql(query.where(table.name == self.name))
		db.commit()

		self.run_method("on_change")

		if notify:
			self.notify_update()

	def load_from_db(self):
		"""Populate this document from its row in the log database.

		`name` is usually the row's name, but `Document.load_from_db` also accepts anything
		else as a set of filters, and callers rely on that: `frappe.get_doc("Activity Log",
		row)` where `row` came straight out of `frappe.get_all` passes `{"name": "..."}`.
		Comparing the `name` column against a dict would render the dict into the SQL, so the
		two cases are kept apart exactly as the base class keeps them apart.
		"""
		db = get_log_db()

		if isinstance(self.name, str | int):
			qb, table = log_table(self.doctype)
			rows = db.sql(
				qb.from_(table).select(table.star).where(table.name == self.name),
				as_dict=True,
			)
			row = rows[0] if rows else None
		else:
			ensure_log_table(self.doctype)
			row = db.get_value(self.doctype, filters=self.name, fieldname="*", as_dict=True)

		if not row:
			raise frappe.DoesNotExistError(doctype=self.doctype)

		# Bypass Document.__init__, which would try to load the document again.
		super(Document, self).__init__(row)

	def delete(self, *args, **kwargs):
		"""Delete this document from the log database."""
		qb, table = log_table(self.doctype)

		db = get_log_db()
		db.sql(qb.from_(table).where(table.name == self.name).delete())
		db.commit()

	def _set_log_column(self, column: str, value) -> None:
		"""Write one column on this row, touching nothing else.

		Unlike :meth:`db_set` this runs no hooks and does not bump `modified`. It exists for
		the framework's bookkeeping columns, which are updated as a side effect of reading a
		document and must not make it look edited.
		"""
		qb, table = log_table(self.doctype)

		db = get_log_db()
		db.sql(qb.update(table).set(table[column], value).where(table.name == self.name))
		db.commit()

	def add_seen(self, user=None):
		"""Record that `user` has opened this document, in the log database.

		`Document.add_seen` writes `_seen` with `frappe.db.set_value`, which targets the
		primary database -- where a log DocType has no table, so opening the form would either
		raise or silently update a leftover table nobody reads. Same payload and the same
		deferral to after the response; only the connection changes.
		"""
		if not self.meta.track_seen or frappe.flags.read_only or self.meta.issingle:
			return

		user = user or frappe.session.user
		seen = frappe.parse_json(self.get("_seen") or [])

		if user in seen:
			return

		seen.append(user)
		self.set("_seen", json.dumps(seen))
		commit_after_response(lambda: self._set_log_column("_seen", json.dumps(seen)))

	def reset_seen(self):
		"""Reset `_seen` to just the current user. See :meth:`add_seen` for why this is here."""
		if not self.meta.track_seen or self.meta.issingle or self.is_new():
			return

		self._set_log_column("_seen", json.dumps([frappe.session.user]))

	# ============ class/static methods ============

	@staticmethod
	def get_list(
		doctype: str,
		filters=None,
		fields=None,
		order_by=None,
		group_by=None,
		as_list=False,
		pluck=None,
		start=None,
		offset=None,
		limit_start=None,
		page_length=None,
		limit=None,
		limit_page_length=None,
		**kwargs,
	):
		"""Return a page of log rows, for the list view and `frappe.get_all`.

		The query is built by the log connection's own engine, so fields, filters, grouping
		and ordering get the framework's handling -- including its validation of
		caller-supplied identifiers, which cannot be bound as parameters and so have to be
		checked rather than escaped.

		Both spellings of the pagination arguments are accepted because the two virtual
		DocType dispatchers disagree: `frappe.model.qb_query` sends `start`/`page_length`,
		while `frappe.model.db_query` forwards its own `__dict__` and so sends
		`limit_start`/`limit_page_length`. Declaring only one pair would silently ignore
		paging from the other caller.
		"""
		ensure_log_table(doctype)
		db = get_log_db()

		requested = _first_given(page_length, limit, limit_page_length)
		# `0` is Frappe's "no limit" (see frappe.get_all); absent means the usual page.
		page = frappe.utils.cint(20 if requested is None else requested)
		start_at = frappe.utils.cint(_first_given(start, offset, limit_start) or 0)

		query = db._get_query(
			table=doctype,
			fields=fields or ["name"],
			filters=filters,
			order_by=order_by,
			group_by=group_by,
			limit=page or None,
			offset=start_at or None,
		)

		# `as_list` callers index rows positionally, so they must not get dicts back, and a
		# `pluck` caller wants the bare column values. Both dispatchers select the plucked
		# field as the only field, so flattening the first column is all that is left to do --
		# without this, `frappe.get_all(..., pluck="name")` hands back a list of dicts.
		return db.sql(query, as_dict=not (as_list or pluck), pluck=bool(pluck))

	@staticmethod
	def get_count(doctype: str, filters=None, **kwargs) -> int:
		"""Return the total number of matching log rows."""
		ensure_log_table(doctype)

		return frappe.utils.cint(get_log_db().count(doctype, filters))

	@staticmethod
	def get_stats(**kwargs):
		"""Return sidebar stats -- always empty."""
		return {}


def _first_given(*values):
	"""Return the first argument that was actually supplied, or None."""
	for value in values:
		if value is not None:
			return value

	return None
