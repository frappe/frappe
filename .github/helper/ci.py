# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE
import json
import os
from pathlib import Path

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

FRAPPE_EXCLUSIONS = ["*/tests/*", "*/commands/*", "*/frappe/change_log/*", "*/frappe/exceptions*", "*/frappe/desk/page/setup_wizard/setup_wizard.py", "*/frappe/coverage.py", "*frappe/setup.py", "*/frappe/hooks.py", "*/doctype/*/*_dashboard.py", "*/patches/*", "*/.github/helper/ci.py", *TESTED_VIA_CLI]


def get_bench_path():
	return Path(__file__).resolve().parents[4]


class CodeCoverage:
	def __init__(self, with_coverage, app):
		self.with_coverage = with_coverage
		self.app = app or "frappe"

	def __enter__(self):
		if self.with_coverage:
			import os

			from coverage import Coverage

			# Generate coverage report only for app that is being tested
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
	app = "frappe"
	site = os.environ.get("SITE") or "test_site"
	use_orchestrator = bool(os.environ.get("ORCHESTRATOR_URL"))
	with_coverage = json.loads(os.environ.get("WITH_COVERAGE", "true").lower())
	build_number = 1
	total_builds = 1

	try:
		build_number = int(os.environ.get("BUILD_NUMBER"))
	except Exception:
		pass

	try:
		total_builds = int(os.environ.get("TOTAL_BUILDS"))
	except Exception:
		pass

	with CodeCoverage(with_coverage=with_coverage, app=app):
		if use_orchestrator:
			from frappe.parallel_test_runner import ParallelTestWithOrchestrator

			ParallelTestWithOrchestrator(app, site=site)
		else:
			from frappe.parallel_test_runner import ParallelTestRunner

			ParallelTestRunner(app, site=site, build_number=build_number, total_builds=total_builds)
