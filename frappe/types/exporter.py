start_block = "# begin: auto-generated types"
end_block = "# end: auto-generated types"
type_code_block_template = f"""{start_block}
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

		controller = get_controller(self.doctype)
		controller_module = controller.__module__.split(".")[0]
		self.controller_path = (
			Path(frappe.get_module_path(controller_module))
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
			code = (
				code[:existing_block_start]
				+ new_code
				+ "\n\n"
				+ code[existing_block_end:].lstrip("\n")
			)

		elif class_definition in code:  # Add just after class definition
			# Regex by default will only match till line ends, span end is when we need to stop
			if class_def := re.search(rf"class {despaced_name}\(.*", code):  # )
				class_definition_end = class_def.span()[1] + 1
				code = (
					code[:class_definition_end]
					+ new_code
					+ "\n\n"
					+ code[class_definition_end:].lstrip("\n")
				)

		if self._validate_code(code):
			self.controller_path.write_text(code)

	def _generate_code(self):
		for field in self.doc.fields:
