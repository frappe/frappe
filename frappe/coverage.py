import ast
import inspect
from typing import List, Tuple

import frappe
from frappe.model.base_document import get_controller


def get_exclude_list() -> List[str]:
	"""Returns list of file patterns that should be excluded from coverage analysis."""
	return [
		*get_standard_exclusions(),
		*get_empty_controller_files()
	]


def get_standard_exclusions() -> List[str]:
	return ["*/tests/*", "*/commands/*"]


def get_empty_controller_files() -> List[str]:
	"""Returns a list of files found in app/controllers that don't contain any controller methods, including module functions."""
	empty_controllers = []
	modules = frappe.get_all("Module Def", {"app_name": "frappe"}, pluck="name")
	doctypes = frappe.get_all("DocType", {"module": ("in", modules)}, pluck="name")

	for dt in doctypes:
		try:
			doctype_controller = get_controller(dt)
		except ImportError:
			continue

		controller_path = inspect.getfile(doctype_controller)
		methods_defined_in_controller = any(
			x for x in doctype_controller.__dict__ if x not in {"__module__", "__doc__"}
		)

		if methods_defined_in_controller:
			continue

		num_classes, num_func, num_assign = get_pystats(controller_path)
		classes_defined = num_classes > 1
		functions_defined = num_func > 0
		variables_defined = num_assign > 0

		should_be_included = any([functions_defined, classes_defined, variables_defined])

		if not should_be_included:
			empty_controllers.append(controller_path)

	return empty_controllers


def get_pystats(path: str) -> Tuple:
	parsed = ast.parse(open(path).read())
	counter = NodeCrawler()
	counter.visit(parsed)
	return counter.classes_count, counter.functions_count, counter.assignments_count


class NodeCrawler(ast.NodeVisitor):
	functions_count = 0
	classes_count = 0
	assignments_count = 0

	def visit_ClassDef(self, node):
		self.classes_count += 1

	def visit_FunctionDef(self, node):
		self.functions_count += 1

	def visit_Assign(self, node):
		self.assignments_count += 1
