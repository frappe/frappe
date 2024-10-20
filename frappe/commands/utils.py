import json
import os
import subprocess
import sys
import typing
from shutil import which

import click

import frappe
from frappe import _
from frappe.bench import Sites
from frappe.commands import pass_context
from frappe.coverage import CodeCoverage
from frappe.utils import cint, update_progress_bar
from frappe.utils.bench_helper import CliCtxObj

EXTRA_ARGS_CTX = {"ignore_unknown_options": True, "allow_extra_args": True}

if typing.TYPE_CHECKING:
	from IPython.terminal.embed import InteractiveShellEmbed


@click.command("build")
@click.option("--app", help="Build assets for app")
@click.option("--apps", help="Build assets for specific apps")
@click.option(
	"--hard-link",
	is_flag=True,
	default=False,
	help="Copy the files instead of symlinking",
	envvar="FRAPPE_HARD_LINK_ASSETS",
)
@click.option("--production", is_flag=True, default=False, help="Build assets in production mode")
@click.option("--verbose", is_flag=True, default=False, help="Verbose")
@click.option(
	"--force", is_flag=True, default=False, help="Force build assets instead of downloading available"
)
@click.option(
	"--save-metafiles",
	is_flag=True,
	default=False,
	help="Saves esbuild metafiles for built assets. Useful for analyzing bundle size. More info: https://esbuild.github.io/api/#metafile",
)
@click.option(
	"--using-cached",
	is_flag=True,
	default=False,
	envvar="USING_CACHED",
	help="Skips build and uses cached build artifacts (cache is set by Bench). Ignored if developer_mode enabled.",
)
@pass_context
def build(
	context: CliCtxObj,
	app=None,
	apps=None,
	hard_link=False,
	production=False,
	verbose=False,
	force=False,
	save_metafiles=False,
	using_cached=False,
):
	"Compile JS and CSS source files"
	from frappe.build import bundle, download_frappe_assets
	from frappe.gettext.translate import compile_translations
	from frappe.utils.synchronization import filelock

	frappe.init(context.bench.sites.site)

	if not apps and app:
		apps = app

	with filelock("bench_build", is_global=True, timeout=10):
		# dont try downloading assets if force used, app specified or running via CI
		if not (force or apps or os.environ.get("CI")):
			# skip building frappe if assets exist remotely
			skip_frappe = download_frappe_assets(verbose=verbose)
		else:
			skip_frappe = False

		# don't minify in developer_mode for faster builds
		development = frappe.local.conf.developer_mode or frappe.local.dev_server
		mode = "development" if development else "production"
		if production:
			mode = "production"

		if development:
			using_cached = False

		bundle(
			mode,
			apps=apps,
			hard_link=hard_link,
			verbose=verbose,
			skip_frappe=skip_frappe,
			save_metafiles=save_metafiles,
			using_cached=using_cached,
		)

		if apps and isinstance(apps, str):
			apps = apps.split(",")

		if not apps:
			apps = frappe.get_all_apps()

		for app in apps:
			print("Compiling translations for", app)
			compile_translations(app, force=force)


@click.command("watch")
@click.option("--apps", help="Watch assets for specific apps")
@pass_context
def watch(context: CliCtxObj, apps=None):
	"Watch and compile JS and CSS files as and when they change"
	from frappe.build import watch

	frappe.init(context.bench.sites.site)
	watch(apps)


@click.command("clear-cache")
@pass_context
def clear_cache(context: CliCtxObj):
	"Clear cache, doctype cache and defaults"
	import frappe.sessions
	from frappe.website.utils import clear_website_cache

	for site in context.bench.sites:
		try:
			frappe.init(site)
			frappe.connect()
			frappe.clear_cache()
			clear_website_cache()
		finally:
			frappe.destroy()


@click.command("clear-website-cache")
@pass_context
def clear_website_cache(context: CliCtxObj):
	"Clear website cache"
	from frappe.website.utils import clear_website_cache

	for site in context.bench.sites:
		try:
			frappe.init(site)
			frappe.connect()
			clear_website_cache()
		finally:
			frappe.destroy()


@click.command("destroy-all-sessions")
@click.option("--reason")
@pass_context
def destroy_all_sessions(context: CliCtxObj, reason=None):
	"Clear sessions of all users (logs them out)"
	import frappe.sessions

	for site in context.bench.sites:
		try:
			frappe.init(site)
			frappe.connect()
			frappe.sessions.clear_all_sessions(reason)
			frappe.db.commit()
		finally:
			frappe.destroy()


@click.command("show-config")
@click.option("--format", "-f", type=click.Choice(["text", "json"]), default="text")
@pass_context
def show_config(context: CliCtxObj, format):
	"Print configuration file to STDOUT in speified format"

	sites_config = {}

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

	for idx, site in enumerate(context.bench.sites):
		frappe.init(site, force=True)

		if len(context.bench.sites) != 1 and format == "text":
			if idx != 0:
				click.echo()
			click.secho(f"Site {site}", fg="yellow")

		if format == "text":
			data = transform_config(site.config)
			data.insert(0, ["Config", "Value"])
			render_table(data)

		if format == "json":
			sites_config[str(site)] = site.config

		frappe.destroy()

	if format == "json":
		click.echo(frappe.as_json(sites_config))


@click.command("reset-perms")
@pass_context
def reset_perms(context: CliCtxObj):
	"Reset permissions for all doctypes"
	from frappe.permissions import reset_perms

	for site in context.bench.sites:
		try:
			frappe.init(site)
			frappe.connect()
			for d in frappe.db.sql_list(
				"""select name from `tabDocType`
				where istable=0 and custom=0"""
			):
				frappe.clear_cache(doctype=d)
				reset_perms(d)
		finally:
			frappe.destroy()


@click.command("execute")
@click.argument("method")
@click.option("--args")
@click.option("--kwargs")
@click.option("--profile", is_flag=True, default=False)
@pass_context
def execute(context: CliCtxObj, method, args=None, kwargs=None, profile=False):
	"Execute a function"
	for site in context.bench.sites:
		ret = ""
		try:
			frappe.init(site)
			frappe.connect()

			if args:
				try:
					fn_args = eval(args)
				except NameError:
					fn_args = [args]
			else:
				fn_args = ()

			if kwargs:
				fn_kwargs = eval(kwargs)
			else:
				fn_kwargs = {}

			if profile:
				import cProfile

				pr = cProfile.Profile()
				pr.enable()

			try:
				ret = frappe.get_attr(method)(*fn_args, **fn_kwargs)
			except Exception:
				# eval is safe here because input is from console
				code = compile(method, "<bench execute>", "eval")
				ret = eval(code, globals(), locals())  # nosemgrep
				if callable(ret):
					suffix = "(*fn_args, **fn_kwargs)"
					code = compile(method + suffix, "<bench execute>", "eval")
					ret = eval(code, globals(), locals())  # nosemgrep

			if profile:
				import pstats
				from io import StringIO

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

			print(json.dumps(ret, default=json_handler).strip('"'))


@click.command("add-to-email-queue")
@click.argument("email-path")
@pass_context
def add_to_email_queue(context: CliCtxObj, email_path):
	"Add an email to the Email Queue"
	if os.path.isdir(email_path):
		frappe.init(context.bench.sites.site)
		frappe.connect()
		for email in os.listdir(email_path):
			with open(os.path.join(email_path, email)) as email_data:
				kwargs = json.load(email_data)
				kwargs["delayed"] = True
				frappe.sendmail(**kwargs)
				frappe.db.commit()
		frappe.destroy()


@click.command("export-doc")
@click.argument("doctype")
@click.argument("docname")
@pass_context
def export_doc(context: CliCtxObj, doctype, docname):
	"Export a single document to csv"
	import frappe.modules

	for site in context.bench.sites:
		try:
			frappe.init(site)
			frappe.connect()
			frappe.modules.export_doc(doctype, docname)
		finally:
			frappe.destroy()


@click.command("export-json")
@click.argument("doctype")
@click.argument("path")
@click.option("--name", help="Export only one document")
@pass_context
def export_json(context: CliCtxObj, doctype, path, name=None):
	"Export doclist as json to the given path, use '-' as name for Singles."
	from frappe.core.doctype.data_import.data_import import export_json

	for site in context.bench.sites:
		try:
			frappe.init(site)
			frappe.connect()
			export_json(doctype, path, name=name)
		finally:
			frappe.destroy()


@click.command("export-csv")
@click.argument("doctype")
@click.argument("path")
@pass_context
def export_csv(context: CliCtxObj, doctype, path):
	"Export data import template with data for DocType"
	from frappe.core.doctype.data_import.data_import import export_csv

	for site in context.bench.sites:
		try:
			frappe.init(site)
			frappe.connect()
			export_csv(doctype, path)
		finally:
			frappe.destroy()


@click.command("export-fixtures")
@click.option("--app", default=None, help="Export fixtures of a specific app")
@pass_context
def export_fixtures(context: CliCtxObj, app=None):
	"Export fixtures"
	from frappe.utils.fixtures import export_fixtures

	for site in context.bench.sites:
		try:
			frappe.init(site)
			frappe.connect()
			export_fixtures(app=app)
		finally:
			frappe.destroy()


@click.command("import-doc")
@click.argument("path")
@pass_context
def import_doc(context: CliCtxObj, path, force=False):
	"Import (insert/update) doclist. If the argument is a directory, all files ending with .json are imported"
	from frappe.core.doctype.data_import.data_import import import_doc

	if not os.path.exists(path):
		path = os.path.join("..", path)
	if not os.path.exists(path):
		print(f"Invalid path {path}")
		sys.exit(1)

	for site in context.bench.sites:
		try:
			frappe.init(site)
			frappe.connect()
			import_doc(path)
		finally:
			frappe.destroy()


@click.command("data-import")
@click.option(
	"--file",
	"file_path",
	type=click.Path(exists=True, dir_okay=False, resolve_path=True),
	required=True,
	help=(
		"Path to import file (.csv, .xlsx)."
		"Consider that relative paths will resolve from 'sites' directory"
	),
)
@click.option("--doctype", type=str, required=True)
@click.option(
	"--type",
	"import_type",
	type=click.Choice(["Insert", "Update"], case_sensitive=False),
	default="Insert",
	help="Insert New Records or Update Existing Records",
)
@click.option("--submit-after-import", default=False, is_flag=True, help="Submit document after importing it")
@click.option("--mute-emails", default=True, is_flag=True, help="Mute emails during import")
@pass_context
def data_import(
	context: CliCtxObj, file_path, doctype, import_type=None, submit_after_import=False, mute_emails=True
):
	"Import documents in bulk from CSV or XLSX using data import"
	from frappe.core.doctype.data_import.data_import import import_file

	frappe.init(context.bench.sites.site)
	frappe.connect()
	import_file(doctype, file_path, import_type, submit_after_import, console=True)
	frappe.destroy()


@click.command("bulk-rename")
@click.argument("doctype")
@click.argument("path")
@pass_context
def bulk_rename(context: CliCtxObj, doctype, path):
	"Rename multiple records via CSV file"
	from frappe.model.rename_doc import bulk_rename
	from frappe.utils.csvutils import read_csv_content

	with open(path) as csvfile:
		rows = read_csv_content(csvfile.read())

	frappe.init(context.bench.sites.site)
	frappe.connect()

	bulk_rename(doctype, rows, via_console=True)

	frappe.destroy()


@click.command("db-console", context_settings=EXTRA_ARGS_CTX)
@click.argument("extra_args", nargs=-1)
@pass_context
def database(context: CliCtxObj, extra_args):
	"""
	Enter into the Database console for given site.
	"""
	frappe.init(context.bench.sites.site)
	_enter_console(extra_args=extra_args)


@click.command("mariadb", context_settings=EXTRA_ARGS_CTX)
@click.argument("extra_args", nargs=-1)
@pass_context
def mariadb(context: CliCtxObj, extra_args):
	"""
	Enter into mariadb console for a given site.
	"""
	site = context.bench.sites.site
	frappe.init(site)
	frappe.conf.db_type = "mariadb"
	_enter_console(site, extra_args=extra_args)


@click.command("postgres", context_settings=EXTRA_ARGS_CTX)
@click.argument("extra_args", nargs=-1)
@pass_context
def postgres(context: CliCtxObj, extra_args):
	"""
	Enter into postgres console for a given site.
	"""
	site = context.bench.sites.site
	frappe.init(site)
	frappe.conf.db_type = "postgres"
	_enter_console(site, extra_args=extra_args)


def _enter_console(site: Sites.Site, extra_args=None):
	from frappe.database import get_command

	if frappe.conf.db_type == "mariadb":
		os.environ["MYSQL_HISTFILE"] = site.bench.logs.get_log_file("mariadb_console.log")
	else:
		os.environ["PSQL_HISTORY"] = site.bench.logs.get_log_file("postgresql_console.log")

	bin, args, bin_name = get_command(
		socket=frappe.conf.db_socket,
		host=frappe.conf.db_host,
		port=frappe.conf.db_port,
		user=frappe.conf.db_user,
		password=frappe.conf.db_password,
		db_name=frappe.conf.db_name,
		extra=list(extra_args) if extra_args else [],
	)
	if not bin:
		frappe.throw(
			_("{} not found in PATH! This is required to access the console.").format(bin_name),
			exc=frappe.ExecutableNotFound,
		)
	os.execv(bin, [bin, *args])


@click.command("jupyter")
@pass_context
def jupyter(context: CliCtxObj):
	"""Start an interactive jupyter notebook"""
	installed_packages = (
		r.split("==", 1)[0]
		for r in subprocess.check_output([sys.executable, "-m", "pip", "freeze"], encoding="utf8")
	)

	if "jupyter" not in installed_packages:
		subprocess.check_output([sys.executable, "-m", "pip", "install", "jupyter"])

	site = context.bench.sites.site

	frappe.init(site)

	jupyter_notebooks_path = frappe.site.path.joinpath("jupyter_notebooks").resolve()

	try:
		os.stat(jupyter_notebooks_path)
	except OSError:
		print(f"Creating folder to keep jupyter notebooks at {jupyter_notebooks_path}")
		os.mkdir(jupyter_notebooks_path)
	jupyter = which("jupyter")
	print(
		f"""
Starting Jupyter notebook
Run the following in your first cell to connect notebook to frappe
```
import frappe
frappe.init('{frappe.site}', sites_path='{frappe.site.path}')
frappe.connect()
frappe.local.lang = frappe.db.get_default('lang')
frappe.db.connect()
```
	"""
	)
	os.execv(
		jupyter,
		[
			jupyter,
			"notebook",
			jupyter_notebooks_path,
		],
	)


def _console_cleanup():
	# Execute after_rollback on console close
	frappe.db.rollback()
	frappe.destroy()


def store_logs(terminal: "InteractiveShellEmbed") -> None:
	from contextlib import suppress

	frappe.log_level = 20  # info
	with suppress(Exception):
		logger = frappe.logger("ipython")
		logger.info("=== bench console session ===")
		for line in terminal.history_manager.get_range():
			logger.info(line[2])
		logger.info("=== session end ===")


@click.command("console")
@click.option("--autoreload", is_flag=True, help="Reload changes to code automatically")
@pass_context
def console(context: CliCtxObj, autoreload=False):
	"Start ipython console for a site"
	frappe.init(context.bench.sites.site)
	frappe.connect()
	frappe.local.lang = frappe.db.get_default("lang")

	from atexit import register

	from IPython.terminal.embed import InteractiveShellEmbed

	register(_console_cleanup)

	terminal = InteractiveShellEmbed.instance()
	if autoreload:
		terminal.extension_manager.load_extension("autoreload")
		terminal.run_line_magic("autoreload", "2")

	all_apps = frappe.get_installed_apps()
	failed_to_import = []
	register(store_logs, terminal)  # Note: atexit runs in reverse order of registration

	for app in list(all_apps):
		try:
			locals()[app] = __import__(app)
		except ModuleNotFoundError:
			failed_to_import.append(app)
			all_apps.remove(app)

	print("Apps in this namespace:\n{}".format(", ".join(all_apps)))
	if failed_to_import:
		print("\nFailed to import:\n{}".format(", ".join(failed_to_import)))

	# ref: https://stackoverflow.com/a/74681224
	try:
		from IPython.core import ultratb

		ultratb.VerboseTB._tb_highlight = "bg:ansibrightblack"
	except Exception:
		pass

	terminal.colors = "neutral"
	terminal.display_banner = False
	terminal()


@click.command("transform-database", help="Change tables' internal settings changing engine and row formats")
@click.option(
	"--table",
	required=True,
	help="Comma separated name of tables to convert. To convert all tables, pass 'all'",
)
@click.option(
	"--engine",
	default=None,
	type=click.Choice(["InnoDB", "MyISAM"]),
	help="Choice of storage engine for said table(s)",
)
@click.option(
	"--row_format",
	default=None,
	type=click.Choice(["DYNAMIC", "COMPACT", "REDUNDANT", "COMPRESSED"]),
	help="Set ROW_FORMAT parameter for said table(s)",
)
@click.option("--failfast", is_flag=True, default=False, help="Exit on first failure occurred")
@pass_context
def transform_database(context: CliCtxObj, table, engine, row_format, failfast):
	"Transform site database through given parameters"
	check_table = []
	add_line = False
	skipped = 0
	frappe.init(context.bench.sites.site)

	if frappe.conf.db_type != "mariadb":
		click.secho("This command only has support for MariaDB databases at this point", fg="yellow")
		sys.exit(1)

	if not (engine or row_format):
		click.secho("Values for `--engine` or `--row_format` must be set")
		sys.exit(1)

	frappe.connect()

	if table == "all":
		information_schema = frappe.qb.Schema("information_schema")
		queried_tables = (
			frappe.qb.from_(information_schema.tables)
			.select("table_name")
			.where(
				(information_schema.tables.row_format != row_format)
				& (information_schema.tables.table_schema == frappe.conf.db_name)
			)
			.run()
		)
		tables = [x[0] for x in queried_tables]
	else:
		tables = [x.strip() for x in table.split(",")]

	total = len(tables)

	for current, table in enumerate(tables):
		values_to_set = ""
		if engine:
			values_to_set += f" ENGINE={engine}"
		if row_format:
			values_to_set += f" ROW_FORMAT={row_format}"

		try:
			frappe.db.sql(f"ALTER TABLE `{table}`{values_to_set}")
			update_progress_bar("Updating table schema", current - skipped, total)
			add_line = True

		except Exception as e:
			check_table.append([table, e.args])
			skipped += 1

			if failfast:
				break

	if add_line:
		print()

	for errored_table in check_table:
		table, err = errored_table
		err_msg = f"{table}: ERROR {err[0]}: {err[1]}"
		click.secho(err_msg, fg="yellow")

	frappe.destroy()


@click.command("serve")
@click.option("--port", default=8000)
@click.option("--profile", is_flag=True, default=False)
@click.option(
	"--proxy",
	is_flag=True,
	default=False,
	help="The development server may be run behind a proxy, e.g. ngrok / localtunnel",
)
@click.option("--noreload", "no_reload", is_flag=True, default=False)
@click.option("--nothreading", "no_threading", is_flag=True, default=False)
@click.option("--with-coverage", is_flag=True, default=False)
@pass_context
def serve(
	context: CliCtxObj,
	port=None,
	profile=False,
	proxy=False,
	no_reload=False,
	no_threading=False,
	sites_path=".",
	site=None,
	with_coverage=False,
):
	"Start development web server"
	import frappe.app

	try:
		site = context.bench.sites.site
	except frappe.BenchNotScopedError:
		site = None
	with CodeCoverage(with_coverage, "frappe"):
		if with_coverage:
			# unable to track coverage with threading enabled
			no_threading = True
			no_reload = True
		frappe.app.serve(
			port=port,
			profile=profile,
			proxy=proxy,
			no_reload=no_reload,
			no_threading=no_threading,
			site=site,
			sites_path=".",
		)


@click.command("request")
@click.option("--args", help="arguments like `?cmd=test&key=value` or `/api/request/method?..`")
@click.option("--path", help="path to request JSON")
@pass_context
def request(context: CliCtxObj, args=None, path=None):
	"Run a request as an admin"
	import frappe.api
	import frappe.handler

	for site in context.bench.sites:
		try:
			frappe.init(site)
			frappe.connect()
			if args:
				if "?" in args:
					frappe.local.form_dict = frappe._dict(
						[a.split("=") for a in args.split("?")[-1].split("&")]
					)
				else:
					frappe.local.form_dict = frappe._dict()

				if args.startswith("/api/method"):
					frappe.local.form_dict.cmd = args.split("?", 1)[0].split("/")[-1]
			elif path:
				with open(os.path.join("..", path)) as f:
					args = json.loads(f.read())

				frappe.local.form_dict = frappe._dict(args)

			frappe.handler.execute_cmd(frappe.form_dict.cmd)

			print(frappe.response)
		finally:
			frappe.destroy()


@click.command("make-app")
@click.argument("destination")
@click.argument("app_name")
@click.option("--no-git", is_flag=True, default=False, help="Do not initialize git repository for the app")
def make_app(destination, app_name, no_git=False):
	"Creates a boilerplate app"
	from frappe.utils.boilerplate import make_boilerplate

	make_boilerplate(destination, app_name, no_git=no_git)


@click.command("create-patch")
def create_patch():
	"Creates a new patch interactively"
	from frappe.utils.boilerplate import PatchCreator

	pc = PatchCreator()
	pc.fetch_user_inputs()
	pc.create_patch_file()


@click.command("set-config")
@click.argument("key")
@click.argument("value")
@click.option("-g", "--global", "global_", is_flag=True, default=False, help="Set value in bench config")
@click.option("-p", "--parse", is_flag=True, default=False, help="Evaluate as Python Object")
@pass_context
def set_config(context: CliCtxObj, key, value, global_=False, parse=False):
	"Insert/Update a value in site_config.json"
	from frappe.installer import update_site_config

	if parse:
		import ast

		value = ast.literal_eval(value)

	if global_:
		context.bench.sites.update_config({key: value})
	else:
		for site in context.bench.sites:
			site.update_config({key, value})


@click.command("version")
@click.option(
	"-f",
	"--format",
	"output",
	type=click.Choice(["plain", "table", "json", "legacy"]),
	help="Output format",
	default="legacy",
)
@pass_context
def get_version(context: CliCtxObj, output):
	"""Show the versions of all the installed apps."""
	from git import Repo
	from git.exc import InvalidGitRepositoryError

	from frappe.utils.change_log import get_app_branch
	from frappe.utils.commands import render_table

	frappe.init(context.bench.sites.site)
	data = []

	for app in sorted(frappe.get_all_apps()):
		module = frappe.get_module(app)
		app_hooks = frappe.get_module(app + ".hooks")

		app_info = frappe._dict()

		try:
			app_info.commit = Repo(frappe.get_app_source_path(app)).head.object.hexsha[:7]
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
@click.option("--static-pages", is_flag=True, default=False, help="Rebuild global search for static pages")
@pass_context
def rebuild_global_search(context: CliCtxObj, static_pages=False):
	"""Setup help table in the current site (called after migrate)"""
	from frappe.utils.global_search import (
		add_route_to_global_search,
		get_doctypes_with_global_search,
		get_routes_to_index,
		rebuild_for_doctype,
		sync_global_search,
	)

	for site in context.bench.sites:
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


@click.command("list-sites")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@pass_context
def list_sites(context: CliCtxObj, output_json=False):
	"List all the sites in current bench"
	bench = context.bench
	default_site = context.bench.sites.config.get("default_site")
	bench.scope(frappe.bench.Sites.ALL_SITES)
	if output_json:
		click.echo(frappe.as_json(bench.sites))
	elif len(bench.sites):
		click.echo("Available sites:")
		for site in bench.sites:
			if site == default_site:
				click.echo(f"* {site}")
			else:
				click.echo(f"  {site}")
	else:
		click.echo("No sites found")


commands = [
	build,
	clear_cache,
	clear_website_cache,
	database,
	transform_database,
	jupyter,
	console,
	destroy_all_sessions,
	execute,
	export_csv,
	export_doc,
	export_fixtures,
	export_json,
	get_version,
	data_import,
	import_doc,
	make_app,
	create_patch,
	mariadb,
	postgres,
	request,
	reset_perms,
	serve,
	set_config,
	show_config,
	watch,
	bulk_rename,
	add_to_email_queue,
	rebuild_global_search,
	list_sites,
]
