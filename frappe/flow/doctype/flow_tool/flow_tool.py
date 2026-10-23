# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import ast
import re

import frappe
from frappe import _
from frappe.flow.utils.system_generated import block_delete, block_rename, validate_immutable
from frappe.model.document import Document

SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
IMPORT_PATH_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)+$")
MAIN_FUNCTION_NAME = "main"


class FlowTool(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		background: DF.Check
		code: DF.Code | None
		description: DF.LongText
		enabled: DF.Check
		import_path: DF.Data | None
		is_system_generated: DF.Check
		requires_confirmation: DF.Check
		slug: DF.Data
		summary: DF.SmallText | None
		title: DF.Data
		type: DF.Literal["Imported", "Script", "Server"]
	# end: auto-generated types

	def validate(self):
		self._normalize()
		self._validate_slug()
		self._validate_type_fields()
		if self.type == "Script":
			self._validate_code()
		validate_immutable(
			self, ("type", "import_path", "description", "requires_confirmation", "background")
		)

	def on_update(self):
		"""`enabled` and `code` are the two edits the flow server would have to be told about."""
		from frappe.flow.lib.session import warn_existing_sessions

		if self.has_value_changed("enabled") or self.has_value_changed("code"):
			agents = frappe.get_all("Flow Agent Tool", filters={"tool": self.name}, pluck="parent")
			warn_existing_sessions(agents)

	def on_trash(self):
		from frappe.flow.tools.builtins import BUILTIN_TOOLS

		block_delete(self, always=self.name in {tool.name for tool in BUILTIN_TOOLS})

	def before_rename(self, old: str, _new: str, _merge: bool = False) -> None:
		block_rename(self, old)

	def to_tool(self):
		"""Resolve this row into a runtime Tool the Agent can call."""
		from frappe.flow.lib.resolver import resolve_tool

		return resolve_tool(self)

	def _normalize(self):
		for field in ("title", "slug", "import_path"):
			value = self.get(field)
			if isinstance(value, str):
				self.set(field, value.strip())

	def _validate_slug(self):
		if not SLUG_PATTERN.match(self.slug or ""):
			frappe.throw(
				_(
					"Slug must be snake_case: start with a lowercase letter, then lowercase letters, digits or underscores."
				),
				title=_("Invalid Slug"),
			)

	def _validate_type_fields(self):
		if self.type == "Imported":
			if not self.import_path:
				frappe.throw(_("Import Path is required for Imported tools."), title=_("Missing Import Path"))
			if not IMPORT_PATH_PATTERN.match(self.import_path):
				frappe.throw(
					_(
						"Import Path must be a dotted Python path (e.g. <code>frappe.flow.tools.builtins.search</code>)."
					),
					title=_("Invalid Import Path"),
				)
			if self.code:
				frappe.throw(_("Imported tools must not define inline code."), title=_("Unexpected Code"))
		elif self.type == "Script":
			if not self.code:
				frappe.throw(_("Code is required for Script tools."), title=_("Missing Code"))
			if self.import_path:
				frappe.throw(
					_("Script tools must not specify an Import Path."),
					title=_("Unexpected Import Path"),
				)
		elif self.type == "Server":
			if not self.is_system_generated:
				frappe.throw(
					_("Server tools come from the flow server's extensions; add an extension instead."),
					title=_("Server Tool"),
				)
			if self.import_path or self.code:
				frappe.throw(
					_("Server tools have no code here; the flow server provides them."),
					title=_("Unexpected Code"),
				)
		else:
			frappe.throw(_("Type must be Imported, Script or Server."), title=_("Invalid Type"))

	def _validate_code(self):
		try:
			tree = ast.parse(self.code, filename=f"<ai_tool:{self.slug}>")
		except SyntaxError as e:
			frappe.throw(
				_("Code has invalid Python syntax: {0}").format(str(e)),
				title=_("Invalid Code"),
			)

		main_function: ast.FunctionDef | None = None
		for node in tree.body:
			if isinstance(node, ast.FunctionDef) and node.name == MAIN_FUNCTION_NAME:
				main_function = node
				break

		if main_function is None:
			frappe.throw(
				_("Code must define a top-level <code>main</code> function."),
				title=_("Missing main()"),
			)

		fn_args = main_function.args
		if fn_args.vararg is not None or fn_args.kwarg is not None:
			frappe.throw(
				_("<code>main</code> must not accept <code>*args</code> or <code>**kwargs</code>."),
				title=_("Invalid Signature"),
			)

		for node in ast.walk(tree):
			if (
				isinstance(node, ast.Call)
				and isinstance(node.func, ast.Name)
				and node.func.id == MAIN_FUNCTION_NAME
			):
				frappe.throw(
					_("Code must not call <code>main()</code> directly (line {0}).").format(node.lineno),
					title=_("Invalid Code"),
				)


def sync_server_tools() -> None:
	"""Mirror this site's extension tools as Server rows: add new ones, refresh
	descriptions, and delete rows whose tool is gone along with the agent rows naming them."""
	from frappe.flow.daemon import lifecycle

	folder = lifecycle.site_extensions_dir()
	rows = lifecycle.extension_tools([folder]) if folder.is_dir() else []
	live = {row["name"]: row["description"] for row in rows}
	mirrored = set(frappe.get_all("Flow Tool", {"type": "Server"}, pluck="name"))
	for name in mirrored - set(live):
		frappe.db.delete("Flow Agent Tool", {"tool": name})
		frappe.delete_doc("Flow Tool", name, ignore_permissions=True)
	for name, description in live.items():
		if name in mirrored:
			frappe.db.set_value("Flow Tool", name, "description", description)
		elif not SLUG_PATTERN.match(name):
			frappe.log_error(title=f"Extension tool {name!r} is not a valid slug; skipped")
		elif frappe.db.exists("Flow Tool", name):
			frappe.log_error(title=f"Flow Tool {name!r} is not a Server tool; extension tool skipped")
		else:
			frappe.get_doc(
				{
					"doctype": "Flow Tool",
					"slug": name,
					"title": name.replace("_", " ").title(),
					"type": "Server",
					"description": description,
					"is_system_generated": 1,
				}
			).insert(ignore_permissions=True)
