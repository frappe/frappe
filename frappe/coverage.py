# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE
"""
	frappe.coverage
	~~~~~~~~~~~~~~~~

	Coverage settings for frappe
"""

STANDARD_INCLUSIONS = ["*.py"]

STANDARD_EXCLUSIONS = [
	"*.js",
	"*.xml",
	"*.pyc",
	"*.css",
	"*.less",
	"*.scss",
	"*.vue",
	"*.html",
	"*/test_*",
	"*/node_modules/*",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
]

FRAPPE_EXCLUSIONS = [
	"*/tests/*",
	"*/commands/*",
	"*/frappe/change_log/*",
	"*/frappe/exceptions*",
	"*/frappe/coverage.py",
	"*frappe/setup.py",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
]


class CodeCoverage:
	def __init__(self, with_coverage, app):
		self.with_coverage = with_coverage
		self.app = app or "frappe"

	def __enter__(self):
		if self.with_coverage:
			import os

			from coverage import Coverage

			from frappe.utils import get_bench_path

			# Generate coverage report only for app that is being tested
			source_path = os.path.join(get_bench_path(), "apps", self.app)
			omit = STANDARD_EXCLUSIONS[:]

			if self.app == "frappe":
				omit.extend(FRAPPE_EXCLUSIONS)

			self.coverage = Coverage(source=[source_path], omit=omit, include=STANDARD_INCLUSIONS)
			self.coverage.start()

	def __exit__(self, exc_type, exc_value, traceback):
		if self.with_coverage:
			self.coverage.stop()
			self.coverage.save()
			self.coverage.xml_report()
