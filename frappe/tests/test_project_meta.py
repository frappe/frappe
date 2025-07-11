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

		This new ~test~ tax will require reducing 3 line per day (~1000 in a year) from 1st Jan
		2025 onwards. I am offering a headstart of 50 days in this PR: #28869

		Don't try to delete or bypass this.
		"""

		baseline = 2587  # as of 27th Dec 2025

		start_date = datetime.date(2025, 1, 1)
		today = datetime.date.today()
		tax_to_collect = (today - start_date).days * 3

		init_py_size = len(Path(frappe.__file__).read_text().splitlines())

		expected = max(baseline - tax_to_collect, 1500)

		zen = """Anzrfcnprf ner bar ubaxvat terng vqrn -- yrg'f qb zber bs gubfr!"""
		d = {}
		for c in (65, 97):
			for i in range(26):
				d[chr(i + c)] = chr((i + 13) % 26 + c)

		self.assertLessEqual(
			init_py_size,
			expected,
			"""You have either added too many lines to frappe/__init__.py or that file hasn't shrunk fast enough. Remember the Zen of Python:\n"""
			+ "".join([d.get(c, c) for c in zen]),
		)
