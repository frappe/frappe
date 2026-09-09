# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Tests for the per-site controller resolution seam in import_controller.

A controller class may define a classmethod `resolve_controller` that
returns the concrete class to use for the current site. The result is
cached per site by `get_controller`.
"""

import frappe
from frappe.model.base_document import _resolve_controller, import_controller
from frappe.tests import IntegrationTestCase


class Plain:
	pass


class Declared:
	@classmethod
	def resolve_controller(cls):
		return Concrete


class Concrete(Declared):
	pass


class SelfResolver:
	@classmethod
	def resolve_controller(cls):
		return cls


class BadResolver:
	@classmethod
	def resolve_controller(cls):
		return Plain


class NonClassResolver:
	@classmethod
	def resolve_controller(cls):
		return "not a class"


class TestControllerResolution(IntegrationTestCase):
	def test_class_without_resolve_controller_is_unchanged(self):
		self.assertIs(_resolve_controller(Plain), Plain)

	def test_resolve_controller_returns_subclass(self):
		self.assertIs(_resolve_controller(Declared), Concrete)

	def test_resolve_controller_may_return_the_class_itself(self):
		self.assertIs(_resolve_controller(SelfResolver), SelfResolver)

	def test_foreign_class_is_rejected(self):
		self.assertIs(_resolve_controller(BadResolver), BadResolver)

	def test_non_class_result_is_rejected(self):
		self.assertIs(_resolve_controller(NonClassResolver), NonClassResolver)

	def test_import_controller_wires_resolution(self):
		"""import_controller must call resolve_controller on the final class."""
		from frappe.desk.doctype.todo.todo import ToDo

		class SiteToDo(ToDo):
			pass

		ToDo.resolve_controller = classmethod(lambda cls: SiteToDo)
		try:
			self.assertIs(import_controller("ToDo"), SiteToDo)
		finally:
			del ToDo.resolve_controller

	def test_import_controller_unchanged_without_resolver(self):
		from frappe.desk.doctype.todo.todo import ToDo

		self.assertIs(import_controller("ToDo"), ToDo)
