# SETTINGS BLOCK — one `Settings Block` row with its JSON columns read.

import json
from functools import cached_property

import frappe
from frappe import _

BINDING_TYPES = ("Single", "Record")
NAME_RESOLVERS = ("session_user",)
KINDS = ("Generated", "Component")
# The columns only a component uses; a generated block shows `fields` and leaves these blank.
COMPONENT_COLUMNS = ("saves_fields", "bindings", "search_entries")
JSON_COLUMNS = ("fields", "saves_fields", "bindings", "search_entries", "anchors", "roles")


class Refusal(Exception):
	def __init__(self, title: str, detail: str, across: bool = False):
		super().__init__(detail)
		self.title = title
		self.detail = detail
		self.across = across


class Block:
	"""One block row with its JSON columns read, each raising a `Refusal` when it holds the wrong shape."""

	def __init__(self, record, row):
		self.record = record
		self.row = row
		self.app = record.app
		self.key = row.key
		self.pane = row.pane
		self.save_mode = row.save_mode or "auto"

	def read_columns(self):
		"""Read every JSON column this kind of block uses, so a wrong shape raises here."""
		columns = ["fields", "anchors", "roles"]
		if self.is_component:
			columns = ["fields", "bindings", "search_entries", "anchors", "roles"]
		for column in columns:
			getattr(self, column)

	@property
	def is_component(self) -> bool:
		return self.row.kind == "Component"

	@cached_property
	def bindings(self) -> dict[str, dict]:
		bindings = self._column("bindings", dict)
		for binding in bindings.values():
			if not isinstance(binding, dict):
				raise self._bad_json("bindings")
			check_binding(binding.get("type"), binding.get("doctype"), binding.get("resolver"))
		return bindings

	@cached_property
	def fields(self) -> list[str]:
		"""What the block lists: the fields a generated block shows, the fields a component saves."""
		return self._column("saves_fields" if self.is_component else "fields", list, str)

	@cached_property
	def roles(self) -> list[str]:
		roles = self._column("roles", list, str)
		if not all(role.strip() for role in roles):
			raise self._bad_json("roles")
		return roles

	@cached_property
	def anchors(self) -> list[dict]:
		anchors = self._column("anchors", list, dict)
		if any(
			len(anchor) != 1 or not isinstance(anchor.get("after") or anchor.get("before"), str)
			for anchor in anchors
		):
			raise self._bad_json("anchors")
		return anchors

	@cached_property
	def search_entries(self) -> list[dict]:
		entries = self._column("search_entries", list, dict)
		if not all(isinstance(entry.get("label"), str) and entry["label"].strip() for entry in entries):
			raise self._bad_json("search_entries")
		return entries

	@cached_property
	def doctypes(self) -> list[str]:
		if self.row.binding_type:
			return [self.row.document_type]
		return [binding["doctype"] for binding in self.bindings.values()]

	@cached_property
	def addresses(self) -> set[tuple[str, str]]:
		"""`(doctype, resolver)` per named binding: one draft each, in this block's pane."""
		if not self.is_component:
			return set()
		return {(binding["doctype"], binding.get("resolver") or "") for binding in self.bindings.values()}

	@cached_property
	def owned_fields(self) -> set[str]:
		return set(self.fields) if self.addresses else set()

	def _column(self, fieldname: str, shape: type, item: type | None = None):
		raw = self.row.get(fieldname)
		try:
			value = json.loads(raw) if raw else shape()
		except (TypeError, ValueError):
			raise self._bad_json(fieldname) from None

		if not isinstance(value, shape) or (item and not all(isinstance(entry, item) for entry in value)):
			raise self._bad_json(fieldname)
		return value

	def _bad_json(self, fieldname: str) -> Refusal:
		return Refusal(
			_("Invalid JSON"),
			_("{0} does not hold the JSON it should.").format(frappe.bold(label_of(fieldname))),
		)


def label_of(fieldname: str) -> str:
	return frappe.get_meta("Settings Block").get_label(fieldname)


def upgrade_row(values: dict) -> dict:
	"""A block row as a file may hold it, in today's shape.

	A file may still use the old shape (no `kind`; a component's `fields` and `settings`) and may hold
	its JSON columns as native values; the columns are text in the database.
	"""
	row = dict(values)

	if not row.get("kind"):
		row["kind"] = "Component" if row.get("component") else "Generated"
		if "settings" in row:
			row["search_entries"] = row.pop("settings")
		if row["kind"] == "Component" and "fields" in row:
			row["saves_fields"] = row.pop("fields")

	for column in JSON_COLUMNS:
		if isinstance(row.get(column), list | dict):
			row[column] = json.dumps(row[column])

	return row


def native_row(values: dict) -> dict:
	"""A block row for a file: its JSON columns as native values, so the file reads without escapes, and no blank column."""
	row = {column: value for column, value in values.items() if value not in (None, "")}

	for column in JSON_COLUMNS:
		if isinstance(row.get(column), str) and row[column].strip():
			try:
				row[column] = json.loads(row[column])
			except ValueError:
				pass

	return row


def check_binding(binding_type: str | None, doctype: str | None, resolver: str | None):
	if binding_type not in BINDING_TYPES or not doctype or not isinstance(doctype, str):
		raise Refusal(
			_("Invalid Binding"),
			_("A binding needs a type ({0}) and a doctype.").format(", ".join(BINDING_TYPES)),
		)

	if resolver is not None and not isinstance(resolver, str):
		raise Refusal(_("Invalid Binding"), _("A name resolver is a string."))

	if binding_type == "Record" and resolver not in NAME_RESOLVERS:
		raise Refusal(
			_("Invalid Binding"),
			_("A Record binding names its record with one of: {0}.").format(", ".join(NAME_RESOLVERS)),
		)

	if binding_type == "Single" and resolver:
		raise Refusal(_("Invalid Binding"), _("A Single binding has no name resolver."))
