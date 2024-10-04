"""
Code Coverage and Parallel Test Runner Script

This script is designed to run parallel tests for Frappe applications with optional code coverage.
It sets up the test environment, handles code coverage configuration, and executes tests using
either a local parallel test runner or an orchestrator-based runner.

Key features:
- Configurable code coverage for specific apps
- Support for local parallel testing and orchestrator-based testing
- Customizable inclusion and exclusion patterns for coverage
- Environment variable based configuration

Usage:
This script is typically run as part of a CI/CD pipeline or for local development testing.
It can be configured using environment variables such as SITE, ORCHESTRATOR_URL, WITH_COVERAGE, etc.
"""

# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

import json
import os
from pathlib import Path

# Define standard patterns for file inclusions and exclusions in coverage
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
	".github/*",
]

# Files that are tested via command line interface
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

# Additional exclusions specific to the Frappe app
FRAPPE_EXCLUSIONS = [
	"*/tests/*",
	"*/commands/*",
	"*/frappe/change_log/*",
	"*/frappe/exceptions*",
	"*/frappe/desk/page/setup_wizard/setup_wizard.py",
	"*/frappe/coverage.py",
	"*frappe/setup.py",
	"*/frappe/hooks.py",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
	"*/.github/helper/ci.py",
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

	def __init__(self, with_coverage, app):
		self.with_coverage = with_coverage
		self.app = app or "frappe"

	def __enter__(self):
		if self.with_coverage:
			import os
			from coverage import Coverage

			# Set up coverage for the specific app
			source_path = os.path.join(get_bench_path(), "apps", self.app)
			print(f"Source path: {source_path}")
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


if __name__ == "__main__":
	# Configuration
	app = "frappe"
	site = os.environ.get("SITE") or "test_site"
	use_orchestrator = bool(os.environ.get("ORCHESTRATOR_URL"))
	with_coverage = json.loads(os.environ.get("WITH_COVERAGE", "true").lower())
	build_number = 1
	total_builds = 1

	# Parse build information from environment variables
	try:
		build_number = int(os.environ.get("BUILD_NUMBER"))
	except Exception:
		pass

	try:
		total_builds = int(os.environ.get("TOTAL_BUILDS"))
	except Exception:
		pass

	# Run tests with code coverage
	with CodeCoverage(with_coverage=with_coverage, app=app):
		# Add ASCII banner at the end
		if use_orchestrator:
			from frappe.parallel_test_runner import ParallelTestWithOrchestrator

			runner = ParallelTestWithOrchestrator(app, site=site)
		else:
			from frappe.parallel_test_runner import ParallelTestRunner

			runner = ParallelTestRunner(app, site=site, build_number=build_number, total_builds=total_builds)

		mode = "Orchestrator" if use_orchestrator else "Parallel"
		banner = f"""
		╔════════════════════════════════════════════╗
		║     CI Helper Script Execution Summary     ║
		╠════════════════════════════════════════════╣
		║ Mode:           {mode:<26} ║
		║ App:            {app:<26} ║
		║ Site:           {site:<26} ║
		║ Build Number:   {build_number:<26} ║
		║ Total Builds:   {total_builds:<26} ║
		║ Tests in Build: ~{runner.total_tests:<25} ║
		╚════════════════════════════════════════════╝
		"""
		print(banner)
		runner.setup_and_run()
