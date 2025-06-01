# Copyright (c) 2021, nts Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE
"""
	nts.coverage
	~~~~~~~~~~~~~~~~

	Coverage settings for nts
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
	"*/nts/installer.py",
	"*/nts/build.py",
	"*/nts/database/__init__.py",
	"*/nts/database/db_manager.py",
	"*/nts/database/**/setup_db.py",
]

nts_EXCLUSIONS = [
	"*/tests/*",
	"*/commands/*",
	"*/nts/change_log/*",
	"*/nts/exceptions*",
	"*/nts/coverage.py",
	"*nts/setup.py",
	"*/doctype/*/*_dashboard.py",
	"*/patches/*",
	*TESTED_VIA_CLI,
]


class CodeCoverage:
	def __init__(self, with_coverage, app):
		self.with_coverage = with_coverage
		self.app = app or "nts"

	def __enter__(self):
		if self.with_coverage:
			import os

			from coverage import Coverage

			from nts.utils import get_bench_path

			# Generate coverage report only for app that is being tested
			source_path = os.path.join(get_bench_path(), "apps", self.app)
			omit = STANDARD_EXCLUSIONS[:]

			if self.app == "nts":
				omit.extend(nts_EXCLUSIONS)

			self.coverage = Coverage(source=[source_path], omit=omit, include=STANDARD_INCLUSIONS)
			self.coverage.start()

	def __exit__(self, exc_type, exc_value, traceback):
		if self.with_coverage:
			self.coverage.stop()
			self.coverage.save()
			self.coverage.xml_report()
			print("Saved Coverage")
