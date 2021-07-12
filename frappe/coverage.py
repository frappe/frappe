import ast
import inspect
from typing import List

import frappe
from frappe.model.base_document import get_controller


def get_exclude_list() -> List[str]:
	"""Returns list of file patterns that should be excluded from coverage analysis.
	"""
	return [
		*get_standard_exclusions(),
		*get_empty_controller_files()
	]


def get_standard_exclusions() -> List[str]:
	return ['*/tests/*', '*/commands/*']


def get_empty_controller_files() -> List[str]:
	"""Returns a list of files found in app/controllers that don't contain any controller methods, including module functions.

	Returns:
		List[str]: [description]
	"""
	empty_controllers = []
	modules = frappe.get_all("Module Def", {"app_name": "frappe"}, pluck="name")
	doctypes = frappe.get_all("DocType", {"module": ("in", modules)}, pluck="name")

	for dt in doctypes:
		try:
			doctype_controller = get_controller(dt)
		except ImportError:
			continue

		controller_file = inspect.getfile(doctype_controller)
		info = PythonFileInfo(controller_file)
		classes_defined = info.classes > 1
		functions_defined = info.functions > 0
		variables_defined = info.assignments > 0
		should_be_included = any([functions_defined, classes_defined, variables_defined])

		if not should_be_included:
			empty_controllers.append(controller_file)

	return empty_controllers

class PythonFileInfo:
	def __init__(self, path: str):
		parsed = ast.parse(open(path).read())
		counter = NodeCrawler()
		counter.visit(parsed)
		self.classes = counter.classes_count
		self.functions = counter.functions_count
		self.assignments = counter.assignments_count

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
