# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import ast
import re

import frappe
from frappe import _
from frappe.model.document import Document

SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
IMPORT_PATH_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)+$")
MAIN_FUNCTION_NAME = "main"


class AITool(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		code: DF.Code | None
		description: DF.LongText
		enabled: DF.Check
		import_path: DF.Data | None
		kind: DF.Literal["Module", "Script"]
		pauses_for_user_input: DF.Check
		slug: DF.Data
		summary: DF.SmallText | None
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		self._normalize()
		self._validate_slug()
		self._validate_kind_fields()
		if self.kind == "Script":
			self._validate_code()

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

	def _validate_kind_fields(self):
		if self.kind == "Module":
			if not self.import_path:
				frappe.throw(_("Import Path is required for Module tools."), title=_("Missing Import Path"))
			if not IMPORT_PATH_PATTERN.match(self.import_path):
				frappe.throw(
					_(
						"Import Path must be a dotted Python path (e.g. <code>frappe.ai.tools.builtins.search</code>)."
					),
					title=_("Invalid Import Path"),
				)
			if self.code:
				frappe.throw(_("Module tools must not define inline code."), title=_("Unexpected Code"))
		elif self.kind == "Script":
			if not self.code:
				frappe.throw(_("Code is required for Script tools."), title=_("Missing Code"))
			if self.import_path:
				frappe.throw(
					_("Script tools must not specify an Import Path."),
					title=_("Unexpected Import Path"),
				)
		else:
			frappe.throw(_("Kind must be Module or Script."), title=_("Invalid Kind"))

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
