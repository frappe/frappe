"""Creates/Updates types in python controller when schema is updated.

Design goal:
	- Developer should be able to see schema in same file.
	- Type checkers should assist with field names and basic validation in same file.
	- `get_doc` outside of same file without explicit annotation is out of scope.
	- Customizations like change of fieldtype and addition of fields are out of scope.
"""

import ast
import inspect
import json
import re
import textwrap
import tokenize
from keyword import iskeyword
from pathlib import Path

import frappe
from frappe import scrub
from frappe.types import DF

field_template = "{field}: {type}"

start_block = "# begin: auto-generated types"
end_block = "# end: auto-generated types"

type_code_block_template = """{start_block}
# This code is auto-generated. Do not modify anything in this block.

from typing import TYPE_CHECKING

if TYPE_CHECKING:
{imports}

{fields}
{end_block}"""


non_nullable_types = {
	"Check",
	"Currency",
	"Float",
	"Int",
	"Percent",
	"Rating",
	"Select",
	"Table",
	"Table MultiSelect",
}


class TypeExporter:
	def __init__(self, doc):
		from frappe.model.base_document import get_controller

		self.doc = doc
		self.doctype = doc.name
		self.field_types = {}

		self.imports = {"from frappe.types import DF"}
		self.indent = "\t"
		self.controller_path = (
			Path(frappe.get_module_path(doc.module))
			/ "doctype"
			/ scrub(self.doctype)
			/ f"{scrub(self.doctype)}.py"
		)

	def export_types(self):
		self._guess_indentation()
		new_code = self._generate_code()
		self._replace_or_add_code(new_code)

	def _replace_or_add_code(self, new_code: str):
		despaced_name = self.doctype.replace(" ", "")

		class_definition = f"class {despaced_name}("  # )
		code = self.controller_path.read_text()

		first_line, *_, last_line = new_code.splitlines()
		if first_line in code and last_line in code:  # Replace
			existing_block_start = code.find(first_line)
			existing_block_end = code.find(last_line) + len(last_line)

			code = code[:existing_block_start] + new_code + "\n\n" + code[existing_block_end:].lstrip("\n")
		elif class_definition in code:  # Add just after class definition
			# Regex by default will only match till line ends, span end is when we need to stop
			if class_def := re.search(rf"class {despaced_name}\(.*", code):  # )
				class_definition_end = class_def.span()[1] + 1
				code = (
					code[:class_definition_end] + new_code + "\n\n" + code[class_definition_end:].lstrip("\n")
				)

		if self._validate_code(code):
			self.controller_path.write_text(code)

	def _generate_code(self):
		for field in self.doc.fields:
			if iskeyword(field.fieldname):
				continue
			if field.is_virtual and not field.options:
				continue
			if python_type := self._map_fieldtype(field):
				self.field_types[field.fieldname] = python_type

		if self.doc.istable:
			for parent_field in ("parent", "parentfield", "parenttype"):
				self.field_types[parent_field] = "DF.Data"

		if self.doc.autoname == "autoincrement":
			self.field_types["name"] = "DF.Int | None"

		fields_code_block = self._create_fields_code_block()
		imports = self._create_imports_block()

		return textwrap.indent(
			type_code_block_template.format(
				start_block=start_block,
				end_block=end_block,
				fields=textwrap.indent(fields_code_block, self.indent),
				imports=textwrap.indent(imports, self.indent),
			),
			self.indent,
		)

	def _create_fields_code_block(self):
		return "\n".join(
			sorted(
				[
					field_template.format(field=field, type=typehint)
					for field, typehint in self.field_types.items()
				]
			)
		)

	def _create_imports_block(self) -> str:
		return "\n".join(sorted(self.imports))

	def _get_doctype_imports(self, doctype):
		from frappe.model.base_document import get_controller

		doctype_module = get_controller(doctype)

		filepath = doctype_module.__module__
		class_name = doctype_module.__name__

		return f"from {filepath} import {class_name}", class_name

	def _map_fieldtype(self, field) -> str | None:
		fieldtype = field.fieldtype.replace(" ", "")
		field_definition = ""

		if fieldtype == "Select":
			field_definition += "DF.Literal"
		elif getattr(DF, fieldtype, None):
			field_definition += f"DF.{fieldtype}"
		else:
			return

		if parameter_definition := self._generic_parameters(field):
			field_definition += parameter_definition

		if self._is_nullable(field):
			field_definition += " | None"

		return field_definition

	def _is_nullable(self, field) -> bool:
		"""If value can be `None`"""

		if field.fieldtype in non_nullable_types:
			return False

		if field.not_nullable:
			return False

		return not bool(field.reqd)

	def _generic_parameters(self, field) -> str | None:
		"""If field is container type then return element type."""
		if field.fieldtype in ("Table", "Table MultiSelect"):
			doctype = field.options
			if not doctype:
				return

			import_statment, cls_name = self._get_doctype_imports(doctype)
			self.imports.add(import_statment)
			return f"[{cls_name}]"

		elif field.fieldtype == "Select":
			if not field.options:
				# Could be dynamic
				return "[None]"
			options = [o.strip() for o in field.options.split("\n")]
			return json.dumps(options)

	@staticmethod
	def _validate_code(code) -> bool:
		"""Make sure whatever code Frappe adds dynamically is valid python."""
		try:
			ast.parse(code)
			return True
		except Exception:
			frappe.msgprint(frappe._("Failed to export python type hints"), alert=True)
			return False

	def _guess_indentation(
		self,
	) -> None:
		from token import INDENT

		with self.controller_path.open() as f:
			for token in tokenize.generate_tokens(f.readline):
				if token.type == INDENT:
					if "\t" in token.string:
						self.indent = "\t"
					else:
						# TODO: any other custom indent not supported
						# Ideally this should be longest common substring but I don't l33tc0de.
						# If someone really needs it, add support via hooks.
						self.indent = " " * 4
					break
