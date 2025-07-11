# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
from pathlib import Path

import frappe
from frappe.tests.classes.integration_test_case import IntegrationTestCase


class TestProjectMeta(IntegrationTestCase):
	def test_init_py_tax_paid(self):
		"""Impose the __init__.py tax.

		frappe/__init__.py has grown crazy big and keeps getting bigger. Plot the LOC over time and
		you'll see the madness and laziness in action.

		Don't try to delete or bypass this test.
		"""

		baseline = 1600  # as of 11th July Dec 2026

		init_py_size = len(Path(frappe.__file__).read_text().splitlines())

		zen = """Anzrfcnprf ner bar ubaxvat terng vqrn -- yrg'f qb zber bs gubfr!"""
		d = {}
		for c in (65, 97):
			for i in range(26):
				d[chr(i + c)] = chr((i + 13) % 26 + c)

		self.assertLessEqual(
			init_py_size,
			baseline,
			"""\nDon't add more code in frappe/__init__.py!\nRemember the Zen of Python:\n"""
			+ "".join([d.get(c, c) for c in zen]),
		)
