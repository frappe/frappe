import os
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import click

import frappe
from frappe.commands import get_site, pass_context
from frappe.utils.bench_helper import CliCtxObj

if TYPE_CHECKING:
	import unittest

	from frappe.testing import TestRunner


def main(
	site: str | None = None,
	app: str | None = None,
	module: str | None = None,
	doctype: str | None = None,
	module_def: str | None = None,
	verbose: bool = False,
	tests: tuple = (),
	force: bool = False,
	profile: bool = False,
	junit_xml_output: str | None = None,
	doctype_list_path: str | None = None,
	failfast: bool = False,
	case: str | None = None,
	skip_before_tests: bool = False,
	pdb_on_exceptions: bool = False,
	selected_categories: list[str] | None = None,
) -> None:
	"""Main function to run tests"""
	import logging

	from frappe.testing import (
		TestConfig,
		TestRunner,
		discover_all_tests,
		discover_doctype_tests,
		discover_module_tests,
	)
	from frappe.testing.environment import _cleanup_after_tests, _initialize_test_environment

	testing_module_logger = logging.getLogger("frappe.testing")
	testing_module_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
	start_time = time.time()

	# Check for mutually exclusive arguments
	exclusive_args = [doctype, doctype_list_path, module_def, module]
	if sum(arg is not None for arg in exclusive_args) > 1:
		raise click.UsageError(
			"Error: The following arguments are mutually exclusive: "
			"doctype, doctype_list_path, module_def, and module. "
			"Please specify only one of these."
		)

	# Prepare debug log message
	debug_params = []
	for param_name in [
		"site",
		"app",
		"module",
		"doctype",
		"module_def",
		"verbose",
		"tests",
		"force",
		"profile",
		"junit_xml_output",
		"doctype_list_path",
		"failfast",
		"case",
		"skip_before_tests",
		"pdb_on_exceptions",
		"selected_categories",
	]:
		param_value = locals()[param_name]
		if param_value is not None:
			debug_params.append(f"{param_name}={param_value}")

	if debug_params:
		click.secho(f"Starting test run with parameters: {', '.join(debug_params)}", fg="cyan", bold=True)
		testing_module_logger.info(f"started with: {', '.join(debug_params)}")
	else:
		click.secho("Starting test run with no specific parameters", fg="cyan", bold=True)
		testing_module_logger.info("started with no specific parameters")
	for handler in testing_module_logger.handlers:
		if file := getattr(handler, "baseFilename", None):
			click.secho(
				f"Detailed logs{' (augment with --verbose)' if not verbose else ''}: {click.style(file, bold=True)}"
			)

	test_config = TestConfig(
		profile=profile,
		failfast=failfast,
		tests=tests,
		case=case,
		pdb_on_exceptions=pdb_on_exceptions,
		selected_categories=selected_categories or [],
		skip_before_tests=skip_before_tests,
	)

	_initialize_test_environment(site, test_config)

	xml_output_file = _setup_xml_output(junit_xml_output)

	try:
		# Create TestRunner instance
		runner = TestRunner(
			verbosity=2 if testing_module_logger.getEffectiveLevel() < logging.INFO else 1,
			tb_locals=testing_module_logger.getEffectiveLevel() <= logging.INFO,
			cfg=test_config,
			buffer=not bool(pdb_on_exceptions),
		)

		if doctype or doctype_list_path:
			doctype = _load_doctype_list(doctype_list_path) if doctype_list_path else doctype
			discover_doctype_tests(doctype, runner, app, force)
		elif module_def:
			_run_module_def_tests(app, module_def, runner, force)
		elif module:
			discover_module_tests(module, runner, app)
		else:
			apps = [app] if app else frappe.get_installed_apps()
			discover_all_tests(apps, runner)

		results = []
		for app, category, suite in runner.iterRun():
			click.secho(
				f"\nRunning {suite.countTestCases()} {category} tests for {app}", fg="cyan", bold=True
			)
			results.append([app, category, runner.run(suite)])

		success = all(r.wasSuccessful() for _, _, r in results)
		click.secho("\nTest Results:", fg="cyan", bold=True)

		def _print_result(app, category, result):
			tests_run = result.testsRun
			failures = len(result.failures)
			errors = len(result.errors)
			click.echo(
				f"\n{click.style(f'{category} Tests in {app}:', bold=True)}\n"
				f"  Ran: {click.style(f'{tests_run:<3}', fg='cyan')}"
				f"  Failures: {click.style(f'{failures:<3}', fg='red' if failures else 'green')}"
				f"  Errors: {click.style(f'{errors:<3}', fg='red' if errors else 'green')}"
			)

			if failures > 0:
				click.echo(f"\n{click.style(category + ' Test Failures:', fg='red', bold=True)}")
				for i, failure in enumerate(result.failures, 1):
					click.echo(f"  {i}. {click.style(str(failure[0]), fg='yellow')}")

			if errors > 0:
				click.echo(f"\n{click.style(category + ' Test Errors:', fg='red', bold=True)}")
				for i, error in enumerate(result.errors, 1):
					click.echo(f"  {i}. {click.style(str(error[0]), fg='yellow')}")
					click.echo(click.style("     " + str(error[1]).split("\n")[-2], fg="red"))

		for app, category, result in results:
			_print_result(frappe.unscrub(app or "Unspecified App"), frappe.unscrub(category), result)

		if success:
			click.echo(f"\n{click.style('All tests passed successfully!', fg='green', bold=True)}")
		else:
			click.echo(f"\n{click.style('Some tests failed or encountered errors.', fg='red', bold=True)}")

		if not success:
			sys.exit(1)

		return results

	finally:
		_cleanup_after_tests()
		if xml_output_file:
			xml_output_file.close()

		end_time = time.time()
		testing_module_logger.debug(f"Total test run time: {end_time - start_time:.3f} seconds")


def _setup_xml_output(junit_xml_output):
	"""Setup XML output for test results if specified"""
	global unittest_runner
	import unittest

	if junit_xml_output:
		xml_output_file = open(junit_xml_output, "wb")
		try:
			import xmlrunner

			unittest_runner = xmlrunner.XMLTestRunner(output=xml_output_file)
		except ImportError:
			print("xmlrunner not found. Please install it to use XML output.")
			unittest_runner = unittest.TextTestRunner()
		return xml_output_file
	else:
		unittest_runner = unittest.TextTestRunner()
		return None


def _load_doctype_list(doctype_list_path):
	"""Load the list of doctypes from the specified file"""
	app, path = doctype_list_path.split(os.path.sep, 1)
	with open(frappe.get_app_path(app, path)) as f:
		return f.read().strip().splitlines()


def _run_module_def_tests(app, module_def, runner: "TestRunner", force) -> "TestRunner":
	"""Run tests for the specified module definition"""
	from frappe.testing import discover_doctype_tests

	doctypes = _get_doctypes_for_module_def(app, module_def)
	return discover_doctype_tests(doctypes, runner, app, force)


def _get_doctypes_for_module_def(app, module_def):
	"""Get the list of doctypes for the specified module definition"""
	doctypes = []
	doctypes_ = frappe.get_list(
		"DocType",
		filters={"module": module_def, "istable": 0},
		fields=["name", "module"],
		as_list=True,
	)
	from frappe.modules import get_module_name

	for doctype, module in doctypes_:
		test_module = get_module_name(doctype, module, "test_", app=app)
		try:
			import importlib

			importlib.import_module(test_module)
			doctypes.append(doctype)
		except Exception:
			pass
	return doctypes


@click.command("run-tests")
@click.option("--app", help="For App")
@click.option("--doctype", help="For DocType")
@click.option("--module-def", help="For all Doctypes in Module Def")
@click.option("--case", help="Select particular TestCase")
@click.option(
	"--doctype-list-path",
	help="Path to .txt file for list of doctypes. Example erpnext/tests/server/agriculture.txt",
)
@click.option("--test", multiple=True, help="Specific test")
@click.option("--module", help="Run tests in a module")
@click.option("--pdb", is_flag=True, default=False, help="Open pdb on AssertionError")
@click.option("--profile", is_flag=True, default=False)
@click.option("--coverage", is_flag=True, default=False)
@click.option("--skip-test-records", is_flag=True, default=False, help="DEPRECATED")
@click.option("--skip-before-tests", is_flag=True, default=False, help="Don't run before tests hook")
@click.option("--junit-xml-output", help="Destination file path for junit xml report")
@click.option(
	"--failfast", is_flag=True, default=False, help="Stop the test run on the first error or failure"
)
@click.option(
	"--test-category",
	type=click.Choice(["unit", "integration", "all"]),
	default="all",
	help="Select test category to run",
)
@pass_context
def run_tests(
	context: CliCtxObj,
	app=None,
	module=None,
	doctype=None,
	module_def=None,
	test=(),
	profile=False,
	coverage=False,
	junit_xml_output=False,
	doctype_list_path=None,
	skip_test_records=False,
	skip_before_tests=False,
	failfast=False,
	case=None,
	test_category="all",
	pdb=False,
):
	"""Run python unit-tests"""

	pdb_on_exceptions = None
	if pdb:
		pdb_on_exceptions = (AssertionError,)

	from frappe.coverage import CodeCoverage

	with CodeCoverage(coverage, app):
		import frappe

		tests = test
		site = get_site(context)

		frappe.init(site)
		allow_tests = frappe.get_conf().allow_tests

		if not (allow_tests or os.environ.get("CI")):
			click.secho("Testing is disabled for the site!", bold=True)
			click.secho("You can enable tests by entering following command:")
			click.secho(f"bench --site {site} set-config allow_tests true", fg="green")
			return

		if skip_test_records:
			click.secho("--skip-test-records is deprecated and without effect!", bold=True)
			click.secho("All records are loaded lazily on first use, so the flag is useless, now.")
			click.secho("Simply remove the flag.", fg="green")
			return

		main(
			site,
			app,
			module,
			doctype,
			module_def,
			context.verbose,
			tests=tests,
			force=context.force,
			profile=profile,
			junit_xml_output=junit_xml_output,
			doctype_list_path=doctype_list_path,
			failfast=failfast,
			case=case,
			skip_before_tests=skip_before_tests,
			pdb_on_exceptions=pdb_on_exceptions,
			selected_categories=[] if test_category == "all" else test_category,
		)


@click.command("run-parallel-tests")
@click.option("--app", help="For App", default="frappe")
@click.option("--build-number", help="Build number", default=1)
@click.option("--total-builds", help="Total number of builds", default=1)
@click.option(
	"--with-coverage",
	is_flag=True,
	help="Build coverage file",
	envvar="CAPTURE_COVERAGE",
)
@click.option("--use-orchestrator", is_flag=True, help="Use orchestrator to run parallel tests")
@click.option("--dry-run", is_flag=True, default=False, help="Dont actually run tests")
@pass_context
def run_parallel_tests(
	context: CliCtxObj,
	app,
	build_number,
	total_builds,
	with_coverage=False,
	use_orchestrator=False,
	dry_run=False,
):
	from traceback_with_variables import activate_by_import

	from frappe.coverage import CodeCoverage

	with CodeCoverage(with_coverage, app):
		site = get_site(context)
		if use_orchestrator:
			from frappe.parallel_test_runner import ParallelTestWithOrchestrator

			ParallelTestWithOrchestrator(app, site=site)
		else:
			from frappe.parallel_test_runner import ParallelTestRunner

			runner = ParallelTestRunner(
				app,
				site=site,
				build_number=build_number,
				total_builds=total_builds,
				dry_run=dry_run,
			)
			runner.setup_and_run()


@click.command(
	"run-ui-tests",
	context_settings=dict(
		ignore_unknown_options=True,
	),
)
@click.argument("app")
@click.argument("cypressargs", nargs=-1, type=click.UNPROCESSED)
@click.option("--headless", is_flag=True, help="Run UI Test in headless mode")
@click.option("--parallel", is_flag=True, help="Run UI Test in parallel mode")
@click.option("--with-coverage", is_flag=True, help="Generate coverage report")
@click.option("--browser", default="chrome", help="Browser to run tests in")
@click.option("--ci-build-id")
@pass_context
def run_ui_tests(
	context: CliCtxObj,
	app,
	headless=False,
	parallel=True,
	with_coverage=False,
	browser="chrome",
	ci_build_id=None,
	cypressargs=None,
):
	"Run UI tests"
	site = get_site(context)
	frappe.init(site)
	app_base_path = frappe.get_app_source_path(app)
	site_url = frappe.utils.get_site_url(site)
	admin_password = frappe.get_conf().admin_password

	# override baseUrl using env variable
	site_env = f"CYPRESS_baseUrl={site_url}"
	password_env = f"CYPRESS_adminPassword={admin_password}" if admin_password else ""
	coverage_env = f"CYPRESS_coverage={str(with_coverage).lower()}"

	os.chdir(app_base_path)

	node_bin = subprocess.getoutput("(cd ../frappe && yarn bin)")
	cypress_path = f"{node_bin}/cypress"
	drag_drop_plugin_path = f"{node_bin}/../@4tw/cypress-drag-drop"
	real_events_plugin_path = f"{node_bin}/../cypress-real-events"
	testing_library_path = f"{node_bin}/../@testing-library"
	coverage_plugin_path = f"{node_bin}/../@cypress/code-coverage"

	# check if cypress in path...if not, install it.
	if not (
		os.path.exists(cypress_path)
		and os.path.exists(drag_drop_plugin_path)
		and os.path.exists(real_events_plugin_path)
		and os.path.exists(testing_library_path)
		and os.path.exists(coverage_plugin_path)
	):
		# install cypress & dependent plugins
		click.secho("Installing Cypress...", fg="yellow")
		packages = " ".join(
			[
				"cypress@^13",
				"@4tw/cypress-drag-drop@^2",
				"cypress-real-events",
				"@testing-library/cypress@^10",
				"@testing-library/dom@8.17.1",
				"@cypress/code-coverage@^3",
			]
		)
		frappe.commands.popen(f"(cd ../frappe && yarn add {packages} --no-lockfile)")

	# run for headless mode
	run_or_open = f"run --browser {browser}" if headless else "open"
	formatted_command = f"{site_env} {password_env} {coverage_env} {cypress_path} {run_or_open}"

	if os.environ.get("CYPRESS_RECORD_KEY"):
		formatted_command += " --record"

	if parallel:
		formatted_command += " --parallel"

	if ci_build_id:
		formatted_command += f" --ci-build-id {ci_build_id}"

	if cypressargs:
		formatted_command += " " + " ".join(cypressargs)

	click.secho("Running Cypress...", fg="yellow")
	frappe.commands.popen(formatted_command, cwd=app_base_path, raise_err=True)


commands = [
	run_tests,
	run_parallel_tests,
	run_ui_tests,
]

if __name__ == "__main__":
	main()
