# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE
"""
<<<<<<< HEAD
	frappe.coverage
	~~~~~~~~~~~~~~~~

	Coverage settings for frappe
=======
frappe.coverage
~~~~~~~~~~~~~~~~

Coverage settings for frappe
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
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

# tested via commands' test suite
TESTED_VIA_CLI = [
	"*/frappe/installer.py",
<<<<<<< HEAD
=======
	"*/frappe/utils/install.py",
	"*/frappe/utils/scheduler.py",
	"*/frappe/utils/doctor.py",
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	"*/frappe/build.py",
	"*/frappe/database/__init__.py",
	"*/frappe/database/db_manager.py",
	"*/frappe/database/**/setup_db.py",
]

FRAPPE_EXCLUSIONS = [
	"*/tests/*",
	"*/commands/*",
	"*/frappe/change_log/*",
	"*/frappe/exceptions*",
<<<<<<< HEAD
=======
	"*/frappe/desk/page/setup_wizard/setup_wizard.py",
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	"*/frappe/coverage.py",
	"*frappe/setup.py",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
	*TESTED_VIA_CLI,
]


class CodeCoverage:
<<<<<<< HEAD
	def __init__(self, with_coverage, app):
		self.with_coverage = with_coverage
		self.app = app or "frappe"
=======
	"""
	Context manager for handling code coverage.

	This class sets up code coverage measurement for a specific app,
	applying the appropriate inclusion and exclusion patterns.
	"""

	def __init__(self, with_coverage, app, outfile="coverage.xml"):
		self.with_coverage = with_coverage
		self.app = app or "frappe"
		self.outfile = outfile
>>>>>>> beab110ce9 (fix: clarify error message for child tables)

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
<<<<<<< HEAD
=======
		return self
>>>>>>> beab110ce9 (fix: clarify error message for child tables)

	def __exit__(self, exc_type, exc_value, traceback):
		if self.with_coverage:
			self.coverage.stop()
			self.coverage.save()
<<<<<<< HEAD
			self.coverage.xml_report()
=======
			self.coverage.xml_report(outfile=self.outfile)
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			print("Saved Coverage")
