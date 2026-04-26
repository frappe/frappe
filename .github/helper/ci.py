"""
Script to run Python tests while capturing accurte coverage.

Enabling coverage after `frappe` is imported leaves out a lot of lines that are imported by
default.

This is essentially a copy of `frappe/coverage.py` BUT also triggers test runner with desired
configuration.
"""

import json
import sys
import os
from pathlib import Path
from coverage import Coverage

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
	"*/test_*/*",
	"*/node_modules/*",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
	".github/*",
]

# tested via commands' test suite
TESTED_VIA_CLI = [
	"*/frappe/installer.py",
	"*/frappe/utils/install.py",
	"*/frappe/utils/scheduler.py",
	"*/frappe/utils/doctor.py",
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
	"*/frappe/desk/page/setup_wizard/setup_wizard.py",
	"*/frappe/coverage.py",
	"*frappe/setup.py",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
	"*/frappe/database/postgres/*",
	"*/.github/helper/ci.py",
	"*/frappe/database/sqlite/*",
	*TESTED_VIA_CLI,
]


def get_bench_path():
	"""Get the path to the bench directory."""
	return Path(__file__).resolve().parents[4]


class CodeCoverage:
	"""
	Context manager for handling code coverage.

	This class sets up code coverage measurement for a specific app,
	applying the appropriate inclusion and exclusion patterns.
	"""

	def __init__(self, with_coverage, app, outfile="coverage.xml"):
		self.with_coverage = with_coverage
		self.app = app or "frappe"
		self.outfile = outfile

	def __enter__(self):
		if self.with_coverage:
			# Generate coverage report only for app that is being tested
			source_path = os.path.join(get_bench_path(), "apps", self.app)
			omit = STANDARD_EXCLUSIONS[:]

			if self.app == "frappe":
				omit.extend(FRAPPE_EXCLUSIONS)

			self.coverage = Coverage(source=[source_path], omit=omit, include=STANDARD_INCLUSIONS)

			assert "frappe" not in sys.modules, "frappe already imported, coverage will be inaccurate"
			self.coverage.start()
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		if self.with_coverage:
			self.coverage.stop()
			self.coverage.save()
			self.coverage.xml_report(outfile=self.outfile)
			print("Saved Coverage")


if __name__ == "__main__":
	app = "frappe"
	site = os.environ.get("SITE") or "test_site"
	with_coverage = json.loads(os.environ.get("CAPTURE_COVERAGE", "true").lower())

	# Parse build information from environment variables
	build_number = int(os.environ.get("BUILD_NUMBER"))
	total_builds = int(os.environ.get("TOTAL_BUILDS"))

	# Run tests with code coverage
	with CodeCoverage(with_coverage=with_coverage, app=app):
		from frappe.parallel_test_runner import ParallelTestRunner

		runner = ParallelTestRunner(app, site=site, build_number=build_number, total_builds=total_builds)
		runner.setup_and_run()
