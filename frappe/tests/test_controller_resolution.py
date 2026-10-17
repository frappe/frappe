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
	def test_resolve_controller_returns_the_class_itself_or_a_subclass(self):
		for declared, resolved in ((Plain, Plain), (Declared, Concrete), (SelfResolver, SelfResolver)):
			with self.subTest(declared=declared.__name__):
				self.assertIs(_resolve_controller(declared), resolved)

		# a foreign class or a non-class result is rejected
		for declared in (BadResolver, NonClassResolver):
			with self.subTest(declared=declared.__name__):
				self.assertRaises(ImportError, _resolve_controller, declared)

	def test_import_controller_wires_resolution(self):
		from frappe.desk.doctype.todo.todo import ToDo

		self.assertIs(import_controller("ToDo"), ToDo)

		class SiteToDo(ToDo):
			pass

		ToDo.resolve_controller = classmethod(lambda cls: SiteToDo)
		try:
			self.assertIs(import_controller("ToDo"), SiteToDo)
		finally:
			del ToDo.resolve_controller
