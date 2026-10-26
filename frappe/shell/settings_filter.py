# SETTINGS FILTERING — which panes, blocks and fields of the merged pane list one user may see.

# The rail's one role pass and the meta's permlevel rows, never a per-row `has_permission`;
# DocPerm on the v2 document routes stays the boundary for every read and save.

import frappe
from frappe.desk.form.activity import readable_permlevels
from frappe.model import display_fieldtypes

from .navigation_filter import NavigationContext
from .permissions import has_app_permission


class SettingsFilter:
	"""One user's view of the merged panes, and the search label index over what is left."""

	def __init__(self):
		self.user = frappe.session.user
		self.navigation = NavigationContext("frappe")
		self.index: list[dict] = []
		self._access: dict[str, "FieldAccess"] = {}
		self._apps: dict[str, bool] = {}
		self._records: dict[str, bool] = {}

	def filter(self, panes: list[dict]) -> dict:
		visible = [shown for pane in panes if (shown := self.pane(pane))]
		return {"panes": visible, "index": self.index}

	def pane(self, pane: dict) -> dict | None:
		"""The pane with the blocks this user may see, or None when it is left with none."""
		blocks = [shown for block in pane["blocks"] if (shown := self.block(pane, block))]
		return {**pane, "blocks": blocks} if blocks else None

	def block(self, pane: dict, block: dict) -> dict | None:
		if "binding" in block:
			return self.generated_block(pane, block)

		return self.component_block(pane, block)

	def generated_block(self, pane: dict, block: dict) -> dict | None:
		binding = block["binding"]
		if not self.may_use(binding):
			return None

		shown, fields = self.access(binding["doctype"]).shape(block)
		for field in fields:
			self.add_entry(
				pane, block, fieldname=field.fieldname, label=field.label, description=field.description
			)

		return shown

	def component_block(self, pane: dict, block: dict) -> dict | None:
		"""Shown when every binding it declares may be used; with none, to whoever may enter its app."""
		bindings = block.get("bindings")
		allowed = (
			all(self.may_use(binding) for binding in bindings.values())
			if bindings
			else self.app_permitted(block["app"])
		)
		if not allowed:
			return None

		shown = dict(block)
		for setting in shown.pop("settings", []):
			self.add_entry(pane, block, label=setting["label"], keywords=setting.get("keywords"))

		return shown

	def may_use(self, binding: dict) -> bool:
		"""Read on the doctype; a Record not created yet also needs create, except the user's own `User`."""
		doctype = binding["doctype"]
		if doctype == "User" and binding.get("resolver") == "session_user":
			return True

		if not self.navigation.may_read(doctype):
			return False

		return binding["type"] != "Record" or self.record_exists(doctype) or self.access(doctype).creates

	def record_exists(self, doctype: str) -> bool:
		"""Whether the session user's record exists; `session_user` is the only name resolver."""
		if doctype not in self._records:
			self._records[doctype] = bool(frappe.db.exists(doctype, self.user))

		return self._records[doctype]

	def app_permitted(self, app: str) -> bool:
		if app not in self._apps:
			self._apps[app] = has_app_permission(app)

		return self._apps[app]

	def access(self, doctype: str) -> "FieldAccess":
		if doctype not in self._access:
			self._access[doctype] = FieldAccess(doctype, self.user)

		return self._access[doctype]

	def add_entry(self, pane: dict, block: dict, **entry):
		where = {"app": pane["app"], "pane": pane["key"], "block": block["key"]}
		self.index.append({**where, **{key: value for key, value in entry.items() if value}})


class FieldAccess:
	"""What one user may do with a doctype's fields, by permlevel."""

	def __init__(self, doctype: str, user: str):
		self.meta = frappe.get_meta(doctype)
		self.user = user
		# None: the doctype has no permission rows, so no permlevel is held back.
		self.readable = readable_permlevels(self.meta)
		self.writable = self._permlevels("write", shared=True)
		self.creates = self._holds(self._permlevels("create"), 0)

	def shape(self, block: dict) -> tuple[dict | None, list]:
		"""The block with unreadable fields left out and unwritable ones marked, and its readable fields."""
		authored = block.get("fields")
		drawn = [self.meta.get_field(name) for name in authored] if authored else self._layout_fields()
		readable = [field for field in drawn if field and self.reads(field)]
		if not readable:
			return None, []

		shown = dict(block)
		if authored:
			shown["fields"] = [field.fieldname for field in readable]
		elif left_out := [field.fieldname for field in self.meta.fields if not self.reads(field)]:
			shown["left_out_fields"] = left_out

		if not self._holds(self.writable, 0):
			shown["read_only"] = True
		elif read_only := [field.fieldname for field in readable if not self.writes(field)]:
			shown["read_only_fields"] = read_only

		return shown, readable

	def reads(self, field) -> bool:
		return self._holds(self.readable, field.permlevel or 0)

	def writes(self, field) -> bool:
		return self._holds(self.writable, field.permlevel or 0)

	def _layout_fields(self) -> list:
		"""The fields a block drawing the doctype's whole layout shows as rows."""
		return [
			field
			for field in self.meta.fields
			if field.fieldtype not in display_fieldtypes and not field.hidden
		]

	def _permlevels(self, right: str, shared: bool = False) -> set[int] | None:
		"""`readable_permlevels` for another right; a `shared` right holds permlevel 0 without a role row."""
		if not self.meta.get_permissions():
			return None

		levels = set(self.meta.get_permlevel_access(right, user=self.user))
		if (
			shared
			and 0 not in levels
			and frappe.share.get_shared(self.meta.name, self.user, [right], limit=1)
		):
			levels.add(0)

		return levels

	@staticmethod
	def _holds(levels: set[int] | None, permlevel: int) -> bool:
		return levels is None or permlevel in levels
