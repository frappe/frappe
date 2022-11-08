# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
from distutils.spawn import find_executable

import click

import frappe
from frappe.commands import get_site, pass_context
from frappe.exceptions import SiteNotSpecifiedError
from frappe.utils import cint, get_bench_path, update_progress_bar


@click.command("build")
@click.option("--app", help="Build assets for app")
@click.option(
	"--hard-link", is_flag=True, default=False, help="Copy the files instead of symlinking"
)
@click.option(
	"--make-copy",
	is_flag=True,
	default=False,
	help="[DEPRECATED] Copy the files instead of symlinking",
)
@click.option(
	"--restore",
	is_flag=True,
	default=False,
	help="[DEPRECATED] Copy the files instead of symlinking with force",
)
@click.option("--verbose", is_flag=True, default=False, help="Verbose")
@click.option(
	"--force", is_flag=True, default=False, help="Force build assets instead of downloading available"
)
def build(app=None, hard_link=False, make_copy=False, restore=False, verbose=False, force=False):
	"Minify + concatenate JS and CSS files, build translations"
	from frappe.build import bundle, download_frappe_assets

	frappe.init("")
	# don't minify in developer_mode for faster builds
	no_compress = frappe.local.conf.developer_mode or False

	# dont try downloading assets if force used, app specified or running via CI
	if not (force or app or os.environ.get("CI")):
		# skip building frappe if assets exist remotely
		skip_frappe = download_frappe_assets(verbose=verbose)
	else:
		skip_frappe = False

	if make_copy or restore:
		hard_link = make_copy or restore
		click.secho(
			"bench build: --make-copy and --restore options are deprecated in favour of --hard-link",
			fg="yellow",
		)

	bundle(
		skip_frappe=skip_frappe,
		no_compress=no_compress,
		hard_link=hard_link,
		verbose=verbose,
		app=app,
	)


@click.command("watch")
def watch():
	"Watch and concatenate JS and CSS files as and when they change"
	from frappe.build import watch

	frappe.init("")
	watch(True)


@click.command("clear-cache")
@pass_context
def clear_cache(context):
	"Clear cache, doctype cache and defaults"
	import frappe.sessions
	import frappe.website.render
	from frappe.desk.notifications import clear_notifications

	for site in context.sites:
		try:
			frappe.connect(site)
			frappe.clear_cache()
			clear_notifications()
			frappe.website.render.clear_cache()
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("clear-website-cache")
@pass_context
def clear_website_cache(context):
	"Clear website cache"
	import frappe.website.render

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.website.render.clear_cache()
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("destroy-all-sessions")
@click.option("--reason")
@pass_context
def destroy_all_sessions(context, reason=None):
	"Clear sessions of all users (logs them out)"
	import frappe.sessions

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.sessions.clear_all_sessions(reason)
			frappe.db.commit()
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("show-config")
@click.option("--format", "-f", type=click.Choice(["text", "json"]), default="text")
@pass_context
def show_config(context, format):
	"Print configuration file to STDOUT in speified format"

	if not context.sites:
		raise SiteNotSpecifiedError

	sites_config = {}
	sites_path = os.getcwd()

	from frappe.utils.commands import render_table

	def transform_config(config, prefix=None):
		prefix = f"{prefix}." if prefix else ""
		site_config = []

		for conf, value in config.items():
			if isinstance(value, dict):
				site_config += transform_config(value, prefix=f"{prefix}{conf}")
			else:
				log_value = json.dumps(value) if isinstance(value, list) else value
				site_config += [[f"{prefix}{conf}", log_value]]

		return site_config

	for site in context.sites:
		frappe.init(site)

		if len(context.sites) != 1 and format == "text":
			if context.sites.index(site) != 0:
				click.echo()
			click.secho(f"Site {site}", fg="yellow")

		configuration = frappe.get_site_config(sites_path=sites_path, site_path=site)

		if format == "text":
			data = transform_config(configuration)
			data.insert(0, ["Config", "Value"])
			render_table(data)

		if format == "json":
			sites_config[site] = configuration

		frappe.destroy()

	if format == "json":
		click.echo(frappe.as_json(sites_config))


@click.command("reset-perms")
@pass_context
def reset_perms(context):
	"Reset permissions for all doctypes"
	from frappe.permissions import reset_perms

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			for d in frappe.db.sql_list(
				"""select name from `tabDocType`
				where istable=0 and custom=0"""
			):
				frappe.clear_cache(doctype=d)
				reset_perms(d)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("execute")
@click.argument("method")
@click.option("--args")
@click.option("--kwargs")
@click.option("--profile", is_flag=True, default=False)
@pass_context
def execute(context, method, args=None, kwargs=None, profile=False):
	"Execute a function"
	for site in context.sites:
		ret = ""
		try:
			frappe.init(site=site)
			frappe.connect()

			if args:
				try:
					args = eval(args)
				except NameError:
					args = [args]
			else:
				args = ()

			if kwargs:
				kwargs = eval(kwargs)
			else:
				kwargs = {}

			if profile:
				import cProfile

				pr = cProfile.Profile()
				pr.enable()

			try:
				ret = frappe.get_attr(method)(*args, **kwargs)
			except Exception:
				ret = frappe.safe_eval(
					method + "(*args, **kwargs)", eval_globals=globals(), eval_locals=locals()
				)

			if profile:
				import pstats

				from six import StringIO

				pr.disable()
				s = StringIO()
				pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(0.5)
				print(s.getvalue())

			if frappe.db:
				frappe.db.commit()
		finally:
			frappe.destroy()
		if ret:
			from frappe.utils.response import json_handler

			print(json.dumps(ret, default=json_handler))

	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("add-to-email-queue")
@click.argument("email-path")
@pass_context
def add_to_email_queue(context, email_path):
	"Add an email to the Email Queue"
	site = get_site(context)

	if os.path.isdir(email_path):
		with frappe.init_site(site):
			frappe.connect()
			for email in os.listdir(email_path):
				with open(os.path.join(email_path, email)) as email_data:
					kwargs = json.load(email_data)
					kwargs["delayed"] = True
					frappe.sendmail(**kwargs)
					frappe.db.commit()


@click.command("export-doc")
@click.argument("doctype")
@click.argument("docname")
@pass_context
def export_doc(context, doctype, docname):
	"Export a single document to csv"
	import frappe.modules

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.modules.export_doc(doctype, docname)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("export-json")
@click.argument("doctype")
@click.argument("path")
@click.option("--name", help="Export only one document")
@pass_context
def export_json(context, doctype, path, name=None):
	"Export doclist as json to the given path, use '-' as name for Singles."
	from frappe.core.doctype.data_import.data_import import export_json

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			export_json(doctype, path, name=name)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("export-csv")
@click.argument("doctype")
@click.argument("path")
@pass_context
def export_csv(context, doctype, path):
	"Export data import template with data for DocType"
	from frappe.core.doctype.data_import.data_import import export_csv

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			export_csv(doctype, path)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("export-fixtures")
@click.option("--app", default=None, help="Export fixtures of a specific app")
@pass_context
def export_fixtures(context, app=None):
	"Export fixtures"
	from frappe.utils.fixtures import export_fixtures

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			export_fixtures(app=app)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("import-doc")
@click.argument("path")
@pass_context
def import_doc(context, path, force=False):
	"Import (insert/update) doclist. If the argument is a directory, all files ending with .json are imported"
	from frappe.core.doctype.data_import.data_import import import_doc

	if not os.path.exists(path):
		path = os.path.join("..", path)
	if not os.path.exists(path):
		print("Invalid path {0}".format(path))
		sys.exit(1)

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			import_doc(path)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("import-csv")
@click.argument("path")
@click.option(
	"--only-insert", default=False, is_flag=True, help="Do not overwrite existing records"
)
@click.option(
	"--submit-after-import", default=False, is_flag=True, help="Submit document after importing it"
)
@click.option(
	"--ignore-encoding-errors",
	default=False,
	is_flag=True,
	help="Ignore encoding errors while coverting to unicode",
)
@click.option("--no-email", default=True, is_flag=True, help="Send email if applicable")
@pass_context
def import_csv(
	context,
	path,
	only_insert=False,
	submit_after_import=False,
	ignore_encoding_errors=False,
	no_email=True,
):
	"Import CSV using data import"
	from frappe.core.doctype.data_import_legacy import importer
	from frappe.utils.csvutils import read_csv_content

	site = get_site(context)

	if not os.path.exists(path):
		path = os.path.join("..", path)
	if not os.path.exists(path):
		print("Invalid path {0}".format(path))
		sys.exit(1)

	with open(path, "r") as csvfile:
		content = read_csv_content(csvfile.read())

	frappe.init(site=site)
	frappe.connect()

	try:
		importer.upload(
			content,
			submit_after_import=submit_after_import,
			no_email=no_email,
			ignore_encoding_errors=ignore_encoding_errors,
			overwrite=not only_insert,
			via_console=True,
		)
		frappe.db.commit()
	except Exception:
		print(frappe.get_traceback())

	frappe.destroy()


@click.command("data-import")
@click.option(
	"--file", "file_path", type=click.Path(), required=True, help="Path to import file (.csv, .xlsx)"
)
@click.option("--doctype", type=str, required=True)
@click.option(
	"--type",
	"import_type",
	type=click.Choice(["Insert", "Update"], case_sensitive=False),
	default="Insert",
	help="Insert New Records or Update Existing Records",
)
@click.option(
	"--submit-after-import", default=False, is_flag=True, help="Submit document after importing it"
)
@click.option("--mute-emails", default=True, is_flag=True, help="Mute emails during import")
@pass_context
def data_import(
	context, file_path, doctype, import_type=None, submit_after_import=False, mute_emails=True
):
	"Import documents in bulk from CSV or XLSX using data import"
	from frappe.core.doctype.data_import.data_import import import_file

	site = get_site(context)

	frappe.init(site=site)
	frappe.connect()
	import_file(doctype, file_path, import_type, submit_after_import, console=True)
	frappe.destroy()


@click.command("bulk-rename")
@click.argument("doctype")
@click.argument("path")
@pass_context
def bulk_rename(context, doctype, path):
	"Rename multiple records via CSV file"
	from frappe.model.rename_doc import bulk_rename
	from frappe.utils.csvutils import read_csv_content

	site = get_site(context)

	with open(path, "r") as csvfile:
		rows = read_csv_content(csvfile.read())

	frappe.init(site=site)
	frappe.connect()

	bulk_rename(doctype, rows, via_console=True)

	frappe.destroy()


@click.command("mariadb")
@pass_context
def mariadb(context):
	"""
	Enter into mariadb console for a given site.
	"""
	import os

	site = get_site(context)
	if not site:
		raise SiteNotSpecifiedError
	frappe.init(site=site)

	# This is assuming you're within the bench instance.
	mysql = find_executable("mysql")
	os.execv(
		mysql,
		[
			mysql,
			"-u",
			frappe.conf.db_name,
			"-p" + frappe.conf.db_password,
			frappe.conf.db_name,
			"-h",
			frappe.conf.db_host or "localhost",
			"--pager=less -SFX",
			"--safe-updates",
			"-A",
		],
	)


@click.command("postgres")
@pass_context
def postgres(context):
	"""
	Enter into postgres console for a given site.
	"""
	site = get_site(context)
	frappe.init(site=site)
	# This is assuming you're within the bench instance.
	psql = find_executable("psql")
	subprocess.run([psql, "-d", frappe.conf.db_name])


@click.command("jupyter")
@pass_context
def jupyter(context):
	installed_packages = (
		r.split("==")[0]
		for r in subprocess.check_output([sys.executable, "-m", "pip", "freeze"], encoding="utf8")
	)

	if "jupyter" not in installed_packages:
		subprocess.check_output([sys.executable, "-m", "pip", "install", "jupyter"])

	site = get_site(context)
	frappe.init(site=site)

	jupyter_notebooks_path = os.path.abspath(frappe.get_site_path("jupyter_notebooks"))
	sites_path = os.path.abspath(frappe.get_site_path(".."))

	try:
		os.stat(jupyter_notebooks_path)
	except OSError:
		print("Creating folder to keep jupyter notebooks at {}".format(jupyter_notebooks_path))
		os.mkdir(jupyter_notebooks_path)
	bin_path = os.path.abspath("../env/bin")
	print(
		"""
Starting Jupyter notebook
Run the following in your first cell to connect notebook to frappe
```
import frappe
frappe.init(site='{site}', sites_path='{sites_path}')
frappe.connect()
frappe.local.lang = frappe.db.get_default('lang')
frappe.db.connect()
```
	""".format(
			site=site, sites_path=sites_path
		)
	)
	os.execv(
		"{0}/jupyter".format(bin_path),
		[
			"{0}/jupyter".format(bin_path),
			"notebook",
			jupyter_notebooks_path,
		],
	)


@click.command("console")
@pass_context
def console(context):
	"Start ipython console for a site"
	import warnings

	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	frappe.local.lang = frappe.db.get_default("lang")

	import IPython

	all_apps = frappe.get_installed_apps()
	failed_to_import = []

	for app in all_apps:
		try:
			locals()[app] = __import__(app)
		except ModuleNotFoundError:
			failed_to_import.append(app)
			all_apps.remove(app)

	print("Apps in this namespace:\n{}".format(", ".join(all_apps)))
	if failed_to_import:
		print("\nFailed to import:\n{}".format(", ".join(failed_to_import)))

	warnings.simplefilter("ignore")
	IPython.embed(display_banner="", header="", colors="neutral")


@click.command("run-tests")
@click.option("--app", help="For App")
@click.option("--doctype", help="For DocType")
@click.option("--case", help="Select particular TestCase")
@click.option(
	"--doctype-list-path",
	help="Path to .txt file for list of doctypes. Example erpnext/tests/server/agriculture.txt",
)
@click.option("--test", multiple=True, help="Specific test")
@click.option("--ui-tests", is_flag=True, default=False, help="Run UI Tests")
@click.option("--module", help="Run tests in a module")
@click.option("--profile", is_flag=True, default=False)
@click.option("--coverage", is_flag=True, default=False)
@click.option("--skip-test-records", is_flag=True, default=False, help="Don't create test records")
@click.option(
	"--skip-before-tests", is_flag=True, default=False, help="Don't run before tests hook"
)
@click.option("--junit-xml-output", help="Destination file path for junit xml report")
@click.option(
	"--failfast", is_flag=True, default=False, help="Stop the test run on the first error or failure"
)
@pass_context
def run_tests(
	context,
	app=None,
	module=None,
	doctype=None,
	test=(),
	profile=False,
	coverage=False,
	junit_xml_output=False,
	ui_tests=False,
	doctype_list_path=None,
	skip_test_records=False,
	skip_before_tests=False,
	failfast=False,
	case=None,
):

	"Run tests"
	import frappe.test_runner

	tests = test

	site = get_site(context)

	allow_tests = frappe.get_conf(site).allow_tests

	if not (allow_tests or os.environ.get("CI")):
		click.secho("Testing is disabled for the site!", bold=True)
		click.secho("You can enable tests by entering following command:")
		click.secho("bench --site {0} set-config allow_tests true".format(site), fg="green")
		return

	frappe.init(site=site)

	frappe.flags.skip_before_tests = skip_before_tests
	frappe.flags.skip_test_records = skip_test_records

	if coverage:
		from coverage import Coverage

		from frappe.coverage import FRAPPE_EXCLUSIONS, STANDARD_EXCLUSIONS, STANDARD_INCLUSIONS

		# Generate coverage report only for app that is being tested
		source_path = os.path.join(get_bench_path(), "apps", app or "frappe")
		omit = STANDARD_EXCLUSIONS[:]

		if not app or app == "frappe":
			omit.extend(FRAPPE_EXCLUSIONS)

		ret = frappe.test_runner.main(
			app,
			module,
			doctype,
			context.verbose,
			tests=tests,
			force=context.force,
			profile=profile,
			junit_xml_output=junit_xml_output,
			ui_tests=ui_tests,
			doctype_list_path=doctype_list_path,
			failfast=failfast,
			case=case,
		)

		cov = Coverage(source=[source_path], omit=omit, include=STANDARD_INCLUSIONS)
		cov.start()

	ret = frappe.test_runner.main(
		app,
		module,
		doctype,
		context.verbose,
		tests=tests,
		force=context.force,
		profile=profile,
		junit_xml_output=junit_xml_output,
		ui_tests=ui_tests,
		doctype_list_path=doctype_list_path,
		failfast=failfast,
	)

	if coverage:
		cov.stop()
		cov.save()

	if len(ret.failures) == 0 and len(ret.errors) == 0:
		ret = 0

	if os.environ.get("CI"):
		sys.exit(ret)


@click.command("run-parallel-tests")
@click.option("--app", help="For App", default="frappe")
@click.option("--build-number", help="Build number", default=1)
@click.option("--total-builds", help="Total number of builds", default=1)
@click.option("--with-coverage", is_flag=True, help="Build coverage file")
@click.option("--use-orchestrator", is_flag=True, help="Use orchestrator to run parallel tests")
@pass_context
def run_parallel_tests(
	context, app, build_number, total_builds, with_coverage=False, use_orchestrator=False
):
	site = get_site(context)
	if use_orchestrator:
		from frappe.parallel_test_runner import ParallelTestWithOrchestrator

		ParallelTestWithOrchestrator(app, site=site, with_coverage=with_coverage)
	else:
		from frappe.parallel_test_runner import ParallelTestRunner

		ParallelTestRunner(
			app,
			site=site,
			build_number=build_number,
			total_builds=total_builds,
			with_coverage=with_coverage,
		)


@click.command("run-ui-tests")
@click.argument("app")
@click.option("--headless", is_flag=True, help="Run UI Test in headless mode")
@click.option("--parallel", is_flag=True, help="Run UI Test in parallel mode")
@click.option("--ci-build-id")
@pass_context
def run_ui_tests(context, app, headless=False, parallel=True, ci_build_id=None):
	"Run UI tests"
	site = get_site(context)
	app_base_path = os.path.abspath(os.path.join(frappe.get_app_path(app), ".."))
	site_url = frappe.utils.get_site_url(site)
	admin_password = frappe.get_conf(site).admin_password

	# override baseUrl using env variable
	site_env = f"CYPRESS_baseUrl={site_url}"
	password_env = f"CYPRESS_adminPassword={admin_password}" if admin_password else ""

	os.chdir(app_base_path)

	node_bin = subprocess.getoutput("npm bin")
	cypress_path = f"{node_bin}/cypress"
	plugin_path = f"{node_bin}/../cypress-file-upload"
	testing_library_path = f"{node_bin}/../@testing-library"

	# check if cypress in path...if not, install it.
	if not (
		os.path.exists(cypress_path)
		and os.path.exists(plugin_path)
		and os.path.exists(testing_library_path)
		and cint(subprocess.getoutput("npm view cypress version")[:1]) >= 6
	):
		# install cypress
		click.secho("Installing Cypress...", fg="yellow")
		frappe.commands.popen(
			"yarn add cypress@^6 cypress-file-upload@^5 @4tw/cypress-drag-drop@^2 @testing-library/cypress@^8 --no-lockfile"
		)

	# run for headless mode
	run_or_open = "run --browser chrome --record" if headless else "open"
	command = "{site_env} {password_env} {cypress} {run_or_open}"
	formatted_command = command.format(
		site_env=site_env, password_env=password_env, cypress=cypress_path, run_or_open=run_or_open
	)

	if parallel:
		formatted_command += " --parallel"

	if ci_build_id:
		formatted_command += f" --ci-build-id {ci_build_id}"

	click.secho("Running Cypress...", fg="yellow")
	frappe.commands.popen(formatted_command, cwd=app_base_path, raise_err=True)


@click.command("serve")
@click.option("--port", default=8000)
@click.option("--profile", is_flag=True, default=False)
@click.option("--noreload", "no_reload", is_flag=True, default=False)
@click.option("--nothreading", "no_threading", is_flag=True, default=False)
@pass_context
def serve(
	context, port=None, profile=False, no_reload=False, no_threading=False, sites_path=".", site=None
):
	"Start development web server"
	import frappe.app

	if not context.sites:
		site = None
	else:
		site = context.sites[0]

	frappe.app.serve(
		port=port,
		profile=profile,
		no_reload=no_reload,
		no_threading=no_threading,
		site=site,
		sites_path=".",
	)


@click.command("request")
@click.option("--args", help="arguments like `?cmd=test&key=value` or `/api/request/method?..`")
@click.option("--path", help="path to request JSON")
@pass_context
def request(context, args=None, path=None):
	"Run a request as an admin"
	import frappe.api
	import frappe.handler

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			if args:
				if "?" in args:
					frappe.local.form_dict = frappe._dict([a.split("=") for a in args.split("?")[-1].split("&")])
				else:
					frappe.local.form_dict = frappe._dict()

				if args.startswith("/api/method"):
					frappe.local.form_dict.cmd = args.split("?")[0].split("/")[-1]
			elif path:
				with open(os.path.join("..", path), "r") as f:
					args = json.loads(f.read())

				frappe.local.form_dict = frappe._dict(args)

			frappe.handler.execute_cmd(frappe.form_dict.cmd)

			print(frappe.response)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("make-app")
@click.argument("destination")
@click.argument("app_name")
def make_app(destination, app_name):
	"Creates a boilerplate app"
	from frappe.utils.boilerplate import make_boilerplate

	make_boilerplate(destination, app_name)


@click.command("set-config")
@click.argument("key")
@click.argument("value")
@click.option(
	"-g", "--global", "global_", is_flag=True, default=False, help="Set value in bench config"
)
@click.option("-p", "--parse", is_flag=True, default=False, help="Evaluate as Python Object")
@click.option("--as-dict", is_flag=True, default=False, help="Legacy: Evaluate as Python Object")
@pass_context
def set_config(context, key, value, global_=False, parse=False, as_dict=False):
	"Insert/Update a value in site_config.json"
	from frappe.installer import update_site_config

	if as_dict:
		from frappe.utils.commands import warn

		warn(
			"--as-dict will be deprecated in v14. Use --parse instead", category=PendingDeprecationWarning
		)
		parse = as_dict

	if parse:
		import ast

		value = ast.literal_eval(value)

	if global_:
		sites_path = os.getcwd()
		common_site_config_path = os.path.join(sites_path, "common_site_config.json")
		update_site_config(key, value, validate=False, site_config_path=common_site_config_path)
	else:
		for site in context.sites:
			frappe.init(site=site)
			update_site_config(key, value, validate=False)
			frappe.destroy()


@click.command("version")
@click.option(
	"-f",
	"--format",
	"output",
	type=click.Choice(["plain", "table", "json", "legacy"]),
	help="Output format",
	default="legacy",
)
def get_version(output):
	"""Show the versions of all the installed apps."""
	from git import Repo
	from git.exc import InvalidGitRepositoryError

	from frappe.utils.change_log import get_app_branch
	from frappe.utils.commands import render_table

	frappe.init("")
	data = []

	for app in sorted(frappe.get_all_apps()):
		module = frappe.get_module(app)
		app_hooks = frappe.get_module(app + ".hooks")

		app_info = frappe._dict()

		try:
			app_info.commit = Repo(frappe.get_app_path(app, "..")).head.object.hexsha[:7]
		except InvalidGitRepositoryError:
			app_info.commit = ""

		app_info.app = app
		app_info.branch = get_app_branch(app)
		app_info.version = getattr(app_hooks, f"{app_info.branch}_version", None) or module.__version__

		data.append(app_info)

	{
		"legacy": lambda: [click.echo(f"{app_info.app} {app_info.version}") for app_info in data],
		"plain": lambda: [
			click.echo(f"{app_info.app} {app_info.version} {app_info.branch} ({app_info.commit})")
			for app_info in data
		],
		"table": lambda: render_table(
			[["App", "Version", "Branch", "Commit"]]
			+ [[app_info.app, app_info.version, app_info.branch, app_info.commit] for app_info in data]
		),
		"json": lambda: click.echo(json.dumps(data, indent=4)),
	}[output]()


@click.command("rebuild-global-search")
@click.option(
	"--static-pages", is_flag=True, default=False, help="Rebuild global search for static pages"
)
@pass_context
def rebuild_global_search(context, static_pages=False):
	"""Setup help table in the current site (called after migrate)"""
	from frappe.utils.global_search import (
		add_route_to_global_search,
		get_doctypes_with_global_search,
		get_routes_to_index,
		rebuild_for_doctype,
		sync_global_search,
	)

	for site in context.sites:
		try:
			frappe.init(site)
			frappe.connect()

			if static_pages:
				routes = get_routes_to_index()
				for i, route in enumerate(routes):
					add_route_to_global_search(route)
					frappe.local.request = None
					update_progress_bar("Rebuilding Global Search", i, len(routes))
				sync_global_search()
			else:
				doctypes = get_doctypes_with_global_search()
				for i, doctype in enumerate(doctypes):
					rebuild_for_doctype(doctype)
					update_progress_bar("Rebuilding Global Search", i, len(doctypes))

		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


commands = [
	build,
	clear_cache,
	clear_website_cache,
	jupyter,
	console,
	destroy_all_sessions,
	execute,
	export_csv,
	export_doc,
	export_fixtures,
	export_json,
	get_version,
	import_csv,
	data_import,
	import_doc,
	make_app,
	mariadb,
	postgres,
	request,
	reset_perms,
	run_tests,
	run_ui_tests,
	serve,
	set_config,
	show_config,
	watch,
	bulk_rename,
	add_to_email_queue,
	rebuild_global_search,
	run_parallel_tests,
]
