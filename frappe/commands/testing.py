import os
import shlex
import subprocess
import sys
import time
import unittest
from typing import TYPE_CHECKING

import click

import frappe
from frappe.commands import get_site, pass_context
from frappe.utils.bench_helper import CliCtxObj

if TYPE_CHECKING:
	from frappe.testing import TestRunner
	from frappe.tests.utils.test_capabilities import TestService


def _parse_test_service(_context, _parameter, value: str | None) -> "TestService | None":
	if value is None:
		return None

	from frappe.tests.utils.test_capabilities import TestService

	try:
		return TestService.from_cli_name(value)
	except ValueError as error:
		raise click.BadParameter(str(error)) from error


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
	debug: bool = False,
	debug_exceptions: tuple[Exception] | None = None,
	selected_categories: list[str] | None = None,
	lightmode: bool = False,
	test_service: "TestService | None" = None,
) -> None:
	"""Main function to run tests"""
	if lightmode:
		from frappe.testing.config import TestParameters

		test_params = TestParameters(
			site=site,
			app=app,
			module=module,
			doctype=doctype,
			module_def=module_def,
			verbose=verbose,
			tests=tests,
			force=force,
			profile=profile,
			junit_xml_output=junit_xml_output,
			doctype_list_path=doctype_list_path,
			failfast=failfast,
			case=case,
			test_service=test_service,
		)
		run_tests_in_light_mode(test_params)
		return

	import logging

	from frappe.testing import (
		TestConfig,
		TestRunner,
		discover_all_tests,
		discover_doctype_tests,
		discover_module_tests,
	)
	from frappe.testing.environment import _cleanup_after_tests, _initialize_test_environment
	from frappe.tests.utils.generators import _clear_test_log

	_clear_test_log()

	if debug and not debug_exceptions:
		debug_exceptions = (Exception,)

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
		"debug_exceptions",
		"debug",
		"selected_categories",
		"test_service",
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
				f"View detailed logs{' (using --verbose)' if not verbose else ''}: {click.style(file, bold=True)}"
			)

	test_config = TestConfig(
		profile=profile,
		failfast=failfast,
		tests=tests,
		case=case,
		pdb_on_exceptions=debug_exceptions,
		selected_categories=selected_categories or [],
		skip_before_tests=skip_before_tests,
		test_service=test_service,
	)

	_initialize_test_environment(site, test_config)

	xml_output_file = _setup_xml_output(junit_xml_output)

	try:
		# Create TestRunner instance
		runner = TestRunner(
			verbosity=2 if testing_module_logger.getEffectiveLevel() < logging.INFO else 1,
			tb_locals=testing_module_logger.getEffectiveLevel() <= logging.INFO,
			cfg=test_config,
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
		global unittest_runner
		for app, category, suite in runner.iterRun():
			click.secho(
				f"\nRunning {suite.countTestCases()} {category} tests for {app}", fg="cyan", bold=True
			)
			main_runner = unittest_runner if junit_xml_output and unittest_runner else runner
			res = main_runner.run(suite)
			results.append([app, category, res])

		success = all(r.wasSuccessful() for _, _, r in results)
		if not success:
			sys.exit(1)

		return results

	finally:
		_cleanup_after_tests()
		if xml_output_file:
			xml_output_file.close()

		end_time = time.time()
		testing_module_logger.debug(f"Total test run time: {end_time - start_time:.3f} seconds")


def run_tests_in_light_mode(test_params):
	import cProfile
	import pstats
	from io import StringIO

	from frappe.testing.loader import FrappeTestLoader
	from frappe.testing.result import FrappeTestResult
	from frappe.tests.utils import toggle_test_mode

	# init environment
	frappe.init(test_params.site)
	if not frappe.db:
		frappe.connect()

	# disable scheduler
	global scheduler_disabled_by_user
	scheduler_disabled_by_user = frappe.utils.scheduler.is_scheduler_disabled(verbose=False)
	if not scheduler_disabled_by_user:
		frappe.utils.scheduler.disable_scheduler()
	frappe.clear_cache()

	toggle_test_mode(True)
	suite = FrappeTestLoader().discover_tests(test_params)

	if test_params.profile:
		pr = cProfile.Profile()
		pr.enable()

	result = unittest.TextTestRunner(failfast=test_params.failfast, resultclass=FrappeTestResult).run(suite)

	if test_params.profile:
		pr.disable()
		s = StringIO()
		ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
		ps.print_stats()
		print(s.getvalue())

	if not result.wasSuccessful():
		sys.exit(1)


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
@click.option(
	"--debug",
	is_flag=True,
	default=False,
	help="Disable buffer and attach to pdb on breakpoint or exception",
)
@click.option("--profile", is_flag=True, default=False)
@click.option("--coverage", is_flag=True, default=False)
@click.option("--skip-test-records", is_flag=True, default=False, help="DEPRECATED")
@click.option("--skip-before-tests", is_flag=True, default=False, help="Don't run before tests hook")
@click.option(
	"--junit-xml-output",
	type=click.Path(dir_okay=False, file_okay=True, resolve_path=True),
	help="Destination file path for junit xml report",
)
@click.option(
	"--failfast", is_flag=True, default=False, help="Stop the test run on the first error or failure"
)
@click.option(
	"--test-category",
	type=click.Choice(["unit", "integration", "all"]),
	default="all",
	help="Select test category to run",
)
@click.option(
	"--test-service",
	callback=_parse_test_service,
	metavar="SERVICE",
	help="Run only tests that declare a required service (for example, web-server).",
)
@click.option("--lightmode", is_flag=True, default=False)
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
	lightmode=False,
	test_service=None,
	debug=False,
):
	"""Run python unit-tests"""

	from frappe.coverage import CodeCoverage

	with CodeCoverage(coverage, app):
		import frappe

		tests = test
		site = get_site(context)

		frappe.init(site)
		allow_tests = frappe.conf.allow_tests

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
			debug=debug,
			selected_categories=[] if test_category == "all" else test_category,
			lightmode=lightmode,
			test_service=test_service,
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
@click.option("--lightmode", is_flag=True, default=False, help="Skips all before test setup")
@click.option("--failfast", is_flag=True, default=False, help="Exit on first failure occurred")
@pass_context
def run_parallel_tests(
	context: CliCtxObj,
	app,
	build_number,
	total_builds,
	with_coverage=False,
	use_orchestrator=False,
	dry_run=False,
	lightmode=False,
	failfast=False,
):
	from traceback_with_variables import activate_by_import

	from frappe.coverage import CodeCoverage

	with CodeCoverage(with_coverage, app) as cc:
		site = get_site(context)
		if use_orchestrator:
			from frappe.parallel_test_runner import ParallelTestWithOrchestrator

			runner = ParallelTestWithOrchestrator(app, site=site)
		else:
			from frappe.parallel_test_runner import ParallelTestRunner

			runner = ParallelTestRunner(
				app,
				site=site,
				build_number=build_number,
				total_builds=total_builds,
				dry_run=dry_run,
				lightmode=lightmode,
				failfast=failfast,
			)
		mode = "Orchestrator" if use_orchestrator else "Parallel"
		banner = f"""
		╔════════════════════════════════════════════╗
		║   Parallel Test Runner Execution Summary   ║
		╠════════════════════════════════════════════╣
		║ Mode:           {mode:<26} ║
		║ App:            {app:<26} ║
		║ Site:           {site:<26} ║
		║ Build Number:   {build_number:<26} ║
		║ Total Builds:   {total_builds:<26} ║"""
		if cc.with_coverage:
			banner += """
			║ Coverage Rep.:  {cc.outfile:<26} ║"""
		banner += """
		╚════════════════════════════════════════════╝
		"""
		print(banner)
		runner.setup_and_run()


PLAYWRIGHT_VERSION = "1.63.0"


def _get_site_url(site: str) -> str:
	# frappe.utils.get_site_url reads the config of the site frappe was initialised with
	conf = frappe.get_site_config(site_path=os.path.join(frappe.local.sites_path, site))
	return conf.host_name or f"http://{site}:{conf.webserver_port}"


@click.command(
	"run-ui-tests",
	context_settings=dict(
		ignore_unknown_options=True,
	),
)
@click.argument("app")
@click.argument("playwrightargs", nargs=-1, type=click.UNPROCESSED)
@click.option("--headless", is_flag=True, help="Run UI Test in headless mode")
@click.option("--browser", help="Browser to run tests in: chromium, firefox or webkit")
@click.option(
	"--parallel-site",
	multiple=True,
	help="Additional site to run tests on in parallel. Each site gets its own worker",
)
@click.option(
	"--spec",
	type=click.Path(dir_okay=False, file_okay=True),
	help="Spec file to run",
)
@pass_context
def run_ui_tests(
	context: CliCtxObj,
	app,
	headless=False,
	browser=None,
	parallel_site=(),
	playwrightargs=None,
	spec=None,
):
	"Run UI tests"
	site = get_site(context)
	frappe.init(site)
	app_base_path = frappe.get_app_source_path(app)
	frappe_path = frappe.get_app_source_path("frappe")
	node_modules_path = os.path.join(frappe_path, "node_modules")
	playwright_path = os.path.join(node_modules_path, ".bin", "playwright")

	if not os.path.exists(playwright_path):
		click.secho("Installing Playwright...", fg="yellow")

		# save package.json, install, then restore to avoid modifications
		package_json_path = os.path.join(frappe_path, "package.json")
		with open(package_json_path) as f:
			package_json_contents = f.read()

		frappe.commands.popen(
			f"yarn add @playwright/test@{PLAYWRIGHT_VERSION} --no-lockfile",
			cwd=frappe_path,
			raise_err=True,
		)

		with open(package_json_path, "w") as f:
			f.write(package_json_contents)

	with_deps = "--with-deps " if os.environ.get("CI") else ""
	frappe.commands.popen(
		f"{playwright_path} install {with_deps}{browser or 'chromium'}",
		cwd=frappe_path,
		raise_err=True,
	)

	command = [playwright_path, "test"]
	if not headless:
		command.append("--ui")
	if browser:
		command.append(f"--browser={browser}")
	if spec:
		command.append(spec)
	command.extend(playwrightargs or [])

	env = {
		"BASE_URL": frappe.utils.get_site_url(site),
		# lets specs of other apps resolve @playwright/test from frappe's node_modules
		"NODE_PATH": node_modules_path,
	}
	if parallel_site:
		env["PARALLEL_BASE_URLS"] = ",".join(_get_site_url(s) for s in parallel_site)
	if admin_password := frappe.get_conf().admin_password:
		env["ADMIN_PASSWORD"] = admin_password

	click.secho("Running Playwright...", fg="yellow")
	try:
		frappe.commands.popen(shlex.join(command), cwd=app_base_path, env=env, raise_err=True)
	except subprocess.CalledProcessError as e:
		click.secho("Playwright tests failed", fg="red")
		raise click.exceptions.Exit(1) from e


commands = [
	run_tests,
	run_parallel_tests,
	run_ui_tests,
]

if __name__ == "__main__":
	main()
