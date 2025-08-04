import faulthandler
import json
import os
import re
import signal
import sys
import time
import unittest
import warnings

import click
import requests

import frappe
from frappe.tests.utils import make_test_records, toggle_test_mode

from .testing.environment import _decorate_all_methods_and_functions_with_type_checker
from .testing.result import TestResult

click_ctx = click.get_current_context(True)
if click_ctx:
	click_ctx.color = True

TEST_WEIGHT_OVERRIDES = {
	# XXX: command tests are significantly overweight, need a better heuristic than test count
	# Possible better solution: stats from previous test runs.
	"test_commands.py": 10,
}


class ParallelTestRunner:
	def __init__(self, app, site, build_number=1, total_builds=1, dry_run=False, lightmode=False):
		self.app = app
		self.site = site
		self.build_number = frappe.utils.cint(build_number) or 1
		self.total_builds = frappe.utils.cint(total_builds)
		self.dry_run = dry_run
		self.lightmode = lightmode
		self.test_file_list = []
		self.total_test_weight = 0
		self.test_result = None
		self.setup_test_file_list()

	def setup_and_run(self):
		self.setup_test_site()
		self.run_tests()
		self.print_result()

	def setup_test_site(self):
		frappe.init(self.site)
		if not frappe.db:
			frappe.connect()

		if self.dry_run:
			return

		toggle_test_mode(True)
		frappe.clear_cache()
		frappe.utils.scheduler.disable_scheduler()
		if not self.lightmode:
			_decorate_all_methods_and_functions_with_type_checker()
			self.before_test_setup()

	def before_test_setup(self):
		start_time = time.monotonic()
		for fn in frappe.get_hooks("before_tests", app_name=self.app):
			frappe.get_attr(fn)()

		test_module = frappe.get_module(f"{self.app}.tests")

		if hasattr(test_module, "global_test_dependencies"):
			for doctype in test_module.global_test_dependencies:
				make_test_records(doctype, commit=True)

		elapsed = time.monotonic() - start_time
		elapsed = click.style(f" ({elapsed:.03}s)", fg="red")
		click.echo(f"Before Test {elapsed}")

	def setup_test_file_list(self):
		self.test_file_list = self.get_test_file_list()
		self.total_test_weight = sum(self.get_test_weight(test) for test in self.test_file_list)

	def run_tests(self):
		self.test_result = TestResult(stream=sys.stderr, descriptions=True, verbosity=2)

		for test_file_info in self.test_file_list:
			self.run_tests_for_file(test_file_info)

	def run_tests_for_file(self, file_info):
		if not file_info:
			return

		if self.dry_run:
			print("running tests from", "/".join(file_info))
			return

		if frappe.session.user != "Administrator":
			from frappe.deprecation_dumpster import deprecation_warning

			deprecation_warning(
				"2024-11-13",
				"v17",
				"Setting the test environment user to 'Administrator' by the test runner is deprecated. The UnitTestCase now ensures a consistent user environment on set up and tear down at the class level. ",
			)
			frappe.set_user("Administrator")
		path, filename = file_info
		module = self.get_module(path, filename)

		if not self.lightmode:
			from frappe.deprecation_dumpster import compat_preload_test_records_upfront

			compat_preload_test_records_upfront([(module, path, filename)])

		test_suite = unittest.TestSuite()
		module_test_cases = unittest.TestLoader().loadTestsFromModule(module)
		test_suite.addTest(module_test_cases)
		self.test_result.startTestRun()
		test_suite(self.test_result)
		self.test_result.stopTestRun()

	def get_module(self, path, filename):
		app_path = frappe.get_app_path(self.app)
		relative_path = os.path.relpath(path, app_path)
		if relative_path == ".":
			module_name = self.app
		else:
			relative_path = relative_path.replace("/", ".")
			module_name = os.path.splitext(filename)[0]
			module_name = f"{self.app}.{relative_path}.{module_name}"

		return frappe.get_module(module_name)

	def print_result(self):
		# XXX: Added to debug tests getting stuck AFTER completion
		# the process should terminate before this, we don't need to reset the signal.
		signal.alarm(60)
		faulthandler.register(signal.SIGALRM)

		self.test_result.printErrors()
		click.echo(self.test_result)
		if self.test_result.failures or self.test_result.errors:
			if os.environ.get("CI"):
				sys.exit(1)

	def get_test_file_list(self):
		# Load balance based on total # of tests ~ each runner should get roughly same # of tests.
		test_list = get_all_tests(self.app)

		test_counts = [self.get_test_weight(test) for test in test_list]
		test_chunks = split_by_weight(test_list, test_counts, chunk_count=self.total_builds)

		return test_chunks[self.build_number - 1]

	@staticmethod
	def get_test_weight(test):
		"""Get approximate count of tests inside a file"""
		file_name = "/".join(test)

		test_weight = TEST_WEIGHT_OVERRIDES.get(test[-1]) or 1

		with open(file_name) as f:
			test_count = f.read().count("def test_") * test_weight

		return test_count


def split_by_weight(work, weights, chunk_count):
	"""Roughly split work by respective weight while keep ordering."""
	expected_weight = sum(weights) // chunk_count

	chunks = [[] for _ in range(chunk_count)]

	chunk_no = 0
	chunk_weight = 0

	for task, weight in zip(work, weights, strict=False):
		if chunk_weight > expected_weight:
			chunk_weight = 0
			chunk_no += 1
			assert chunk_no < chunk_count

		chunks[chunk_no].append(task)
		chunk_weight += weight

	assert len(work) == sum(len(chunk) for chunk in chunks)
	assert len(chunks) == chunk_count

	return chunks


def get_all_tests(app):
	test_file_list = []
	for path, folders, files in os.walk(frappe.get_app_path(app)):
		for dontwalk in ("node_modules", "locals", ".git", "public", "__pycache__"):
			if dontwalk in folders:
				folders.remove(dontwalk)

		# for predictability
		folders.sort()
		files.sort()

		if os.path.sep.join(["doctype", "doctype", "boilerplate"]) in path:
			# in /doctype/doctype/boilerplate/
			continue

		test_file_list.extend(
			[path, filename]
			for filename in files
			if filename.startswith("test_") and filename.endswith(".py") and filename != "test_runner.py"
		)
	return test_file_list


class ParallelTestWithOrchestrator(ParallelTestRunner):
	"""
	This can be used to balance-out test time across multiple instances
	This is dependent on external orchestrator which returns next test to run

	orchestrator endpoints
	- register-instance (<build_id>, <instance_id>, test_spec_list)
	- get-next-test-spec (<build_id>, <instance_id>)
	- test-completed (<build_id>, <instance_id>)
	"""

	def __init__(self, app, site):
		self.orchestrator_url = os.environ.get("ORCHESTRATOR_URL")
		if not self.orchestrator_url:
			click.echo("ORCHESTRATOR_URL environment variable not found!")
			click.echo("Pass public URL after hosting https://github.com/frappe/test-orchestrator")
			sys.exit(1)

		self.ci_build_id = os.environ.get("CI_BUILD_ID")
		self.ci_instance_id = os.environ.get("CI_INSTANCE_ID") or frappe.generate_hash(length=10)
		if not self.ci_build_id:
			click.echo("CI_BUILD_ID environment variable not found!")
			sys.exit(1)

		ParallelTestRunner.__init__(self, app, site)

	def run_tests(self):
		self.test_status = "ongoing"
		self.register_instance()
		super().run_tests()

	def get_test_file_list(self):
		while self.test_status == "ongoing":
			yield self.get_next_test()

	def register_instance(self):
		test_spec_list = get_all_tests(self.app)
		response_data = self.call_orchestrator("register-instance", data={"test_spec_list": test_spec_list})
		self.is_master = response_data.get("is_master")

	def get_next_test(self):
		response_data = self.call_orchestrator("get-next-test-spec")
		self.test_status = response_data.get("status")
		return response_data.get("next_test")

	def print_result(self):
		self.call_orchestrator("test-completed")
		return super().print_result()

	def call_orchestrator(self, endpoint, data=None):
		if data is None:
			data = {}
		# add repo token header
		# build id in header
		headers = {
			"CI-BUILD-ID": self.ci_build_id,
			"CI-INSTANCE-ID": self.ci_instance_id,
			"REPO-TOKEN": "2948288382838DE",
		}
		url = f"{self.orchestrator_url}/{endpoint}"
		res = requests.get(url, json=data, headers=headers)
		res.raise_for_status()
		response_data = {}
		if "application/json" in res.headers.get("content-type"):
			response_data = res.json()

		return response_data
