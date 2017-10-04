from __future__ import unicode_literals, absolute_import, print_function
import click
import json, os, sys
from distutils.spawn import find_executable
import frappe
from frappe.commands import pass_context, get_site
from frappe.utils import update_progress_bar

@click.command('build')
@click.option('--make-copy', is_flag=True, default=False, help='Copy the files instead of symlinking')
@click.option('--restore', is_flag=True, default=False, help='Copy the files instead of symlinking with force')
@click.option('--verbose', is_flag=True, default=False, help='Verbose')
def build(make_copy=False, restore = False, verbose=False):
	"Minify + concatenate JS and CSS files, build translations"
	import frappe.build
	import frappe
	frappe.init('')
	frappe.build.bundle(False, make_copy=make_copy, restore = restore, verbose=verbose)

@click.command('watch')
def watch():
	"Watch and concatenate JS and CSS files as and when they change"
	# if os.environ.get('CI'):
	# 	return
	import frappe.build
	frappe.init('')
	frappe.build.watch(True)

@click.command('clear-cache')
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

@click.command('clear-website-cache')
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

@click.command('destroy-all-sessions')
@click.option('--reason')
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


@click.command('reset-perms')
@pass_context
def reset_perms(context):
	"Reset permissions for all doctypes"
	from frappe.permissions import reset_perms
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			for d in frappe.db.sql_list("""select name from `tabDocType`
				where istable=0 and custom=0"""):
					frappe.clear_cache(doctype=d)
					reset_perms(d)
		finally:
			frappe.destroy()

@click.command('execute')
@click.argument('method')
@click.option('--args')
@click.option('--kwargs')
@pass_context
def execute(context, method, args=None, kwargs=None):
	"Execute a function"
	for site in context.sites:
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

			ret = frappe.get_attr(method)(*args, **kwargs)

			if frappe.db:
				frappe.db.commit()
		finally:
			frappe.destroy()
		if ret:
			print(json.dumps(ret))


@click.command('add-to-email-queue')
@click.argument('email-path')
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
					kwargs['delayed'] = True
					frappe.sendmail(**kwargs)
					frappe.db.commit()


@click.command('export-doc')
@click.argument('doctype')
@click.argument('docname')
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

@click.command('export-json')
@click.argument('doctype')
@click.argument('path')
@click.option('--name', help='Export only one document')
@pass_context
def export_json(context, doctype, path, name=None):
	"Export doclist as json to the given path, use '-' as name for Singles."
	from frappe.core.page.data_import_tool import data_import_tool
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			data_import_tool.export_json(doctype, path, name=name)
		finally:
			frappe.destroy()

@click.command('export-csv')
@click.argument('doctype')
@click.argument('path')
@pass_context
def export_csv(context, doctype, path):
	"Export data import template with data for DocType"
	from frappe.core.page.data_import_tool import data_import_tool
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			data_import_tool.export_csv(doctype, path)
		finally:
			frappe.destroy()

@click.command('export-fixtures')
@pass_context
def export_fixtures(context):
	"Export fixtures"
	from frappe.utils.fixtures import export_fixtures
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			export_fixtures()
		finally:
			frappe.destroy()

@click.command('import-doc')
@click.argument('path')
@pass_context
def import_doc(context, path, force=False):
	"Import (insert/update) doclist. If the argument is a directory, all files ending with .json are imported"
	from frappe.core.page.data_import_tool import data_import_tool

	if not os.path.exists(path):
		path = os.path.join('..', path)
	if not os.path.exists(path):
		print('Invalid path {0}'.format(path))
		sys.exit(1)

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			data_import_tool.import_doc(path, overwrite=context.force)
		finally:
			frappe.destroy()

@click.command('import-csv')
@click.argument('path')
@click.option('--only-insert', default=False, is_flag=True, help='Do not overwrite existing records')
@click.option('--submit-after-import', default=False, is_flag=True, help='Submit document after importing it')
@click.option('--ignore-encoding-errors', default=False, is_flag=True, help='Ignore encoding errors while coverting to unicode')
@click.option('--no-email', default=True, is_flag=True, help='Send email if applicable')

@pass_context
def import_csv(context, path, only_insert=False, submit_after_import=False, ignore_encoding_errors=False, no_email=True):
	"Import CSV using data import tool"
	from frappe.core.page.data_import_tool import importer
	from frappe.utils.csvutils import read_csv_content
	site = get_site(context)

	if not os.path.exists(path):
		path = os.path.join('..', path)
	if not os.path.exists(path):
		print('Invalid path {0}'.format(path))
		sys.exit(1)

	with open(path, 'r') as csvfile:
		content = read_csv_content(csvfile.read())

	frappe.init(site=site)
	frappe.connect()

	try:
		importer.upload(content, submit_after_import=submit_after_import, no_email=no_email,
			ignore_encoding_errors=ignore_encoding_errors, overwrite=not only_insert,
			via_console=True)
		frappe.db.commit()
	except Exception:
		print(frappe.get_traceback())

	frappe.destroy()

@click.command('bulk-rename')
@click.argument('doctype')
@click.argument('path')
@pass_context
def _bulk_rename(context, doctype, path):
	"Rename multiple records via CSV file"
	from frappe.model.rename_doc import bulk_rename
	from frappe.utils.csvutils import read_csv_content

	site = get_site(context)

	with open(path, 'r') as csvfile:
		rows = read_csv_content(csvfile.read())

	frappe.init(site=site)
	frappe.connect()

	bulk_rename(doctype, rows, via_console = True)

	frappe.destroy()

@click.command('mysql')
@pass_context
def mysql(context):
	"Start Mariadb console for a site"
	site = get_site(context)
	frappe.init(site=site)
	msq = find_executable('mysql')
	os.execv(msq, [msq, '-u', frappe.conf.db_name, '-p'+frappe.conf.db_password, frappe.conf.db_name, '-h', frappe.conf.db_host or "localhost", "-A"])

@click.command('console')
@pass_context
def console(context):
	"Start ipython console for a site"
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	frappe.local.lang = frappe.db.get_default("lang")
	import IPython
	IPython.embed()

@click.command('run-tests')
@click.option('--app', help="For App")
@click.option('--doctype', help="For DocType")
@click.option('--test', multiple=True, help="Specific test")
@click.option('--driver', help="For Travis")
@click.option('--ui-tests', is_flag=True, default=False, help="Run UI Tests")
@click.option('--module', help="Run tests in a module")
@click.option('--profile', is_flag=True, default=False)
@click.option('--junit-xml-output', help="Destination file path for junit xml report")
@pass_context
def run_tests(context, app=None, module=None, doctype=None, test=(),
	driver=None, profile=False, junit_xml_output=False, ui_tests = False):
	"Run tests"
	import frappe.test_runner
	tests = test

	site = get_site(context)
	frappe.init(site=site)

	ret = frappe.test_runner.main(app, module, doctype, context.verbose, tests=tests,
		force=context.force, profile=profile, junit_xml_output=junit_xml_output,
		ui_tests = ui_tests)
	if len(ret.failures) == 0 and len(ret.errors) == 0:
		ret = 0

	if os.environ.get('CI'):
		sys.exit(ret)

@click.command('run-ui-tests')
@click.option('--app', help="App to run tests on, leave blank for all apps")
@click.option('--test', help="File name of the test you want to run")
@click.option('--profile', is_flag=True, default=False)
@pass_context
def run_ui_tests(context, app=None, test=False, profile=False):
	"Run UI tests"
	import frappe.test_runner

	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()

	ret = frappe.test_runner.run_ui_tests(app=app, test=test, verbose=context.verbose,
		profile=profile)
	if len(ret.failures) == 0 and len(ret.errors) == 0:
		ret = 0

	if os.environ.get('CI'):
		sys.exit(ret)

@click.command('run-setup-wizard-ui-test')
@click.option('--app', help="App to run tests on, leave blank for all apps")
@click.option('--profile', is_flag=True, default=False)
@pass_context
def run_setup_wizard_ui_test(context, app=None, profile=False):
	"Run setup wizard UI test"
	import frappe.test_runner

	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()

	ret = frappe.test_runner.run_setup_wizard_ui_test(app=app, verbose=context.verbose,
		profile=profile)
	if len(ret.failures) == 0 and len(ret.errors) == 0:
		ret = 0

	if os.environ.get('CI'):
		sys.exit(ret)

@click.command('serve')
@click.option('--port', default=8000)
@click.option('--profile', is_flag=True, default=False)
@pass_context
def serve(context, port=None, profile=False, sites_path='.', site=None):
	"Start development web server"
	import frappe.app

	if not context.sites:
		site = None
	else:
		site = context.sites[0]

	frappe.app.serve(port=port, profile=profile, site=site, sites_path='.')

@click.command('request')
@click.option('--args', help='arguments like `?cmd=test&key=value` or `/api/request/method?..`')
@click.option('--path', help='path to request JSON')
@pass_context
def request(context, args=None, path=None):
	"Run a request as an admin"
	import frappe.handler
	import frappe.api
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
				with open(os.path.join('..', path), 'r') as f:
					args = json.loads(f.read())

				frappe.local.form_dict = frappe._dict(args)

			frappe.handler.execute_cmd(frappe.form_dict.cmd)

			print(frappe.response)
		finally:
			frappe.destroy()

@click.command('make-app')
@click.argument('destination')
@click.argument('app_name')
def make_app(destination, app_name):
	"Creates a boilerplate app"
	from frappe.utils.boilerplate import make_boilerplate
	make_boilerplate(destination, app_name)

@click.command('set-config')
@click.argument('key')
@click.argument('value')
@click.option('--as-dict', is_flag=True, default=False)
@pass_context
def set_config(context, key, value, as_dict=False):
	"Insert/Update a value in site_config.json"
	from frappe.installer import update_site_config
	import ast
	if as_dict:
		value = ast.literal_eval(value)
	for site in context.sites:
		frappe.init(site=site)
		update_site_config(key, value, validate=False)
		frappe.destroy()

@click.command('version')
def get_version():
	"Show the versions of all the installed apps"
	frappe.init('')
	for m in sorted(frappe.get_all_apps()):
		module = frappe.get_module(m)
		if hasattr(module, "__version__"):
			print("{0} {1}".format(m, module.__version__))



@click.command('setup-global-help')
@click.option('--mariadb_root_password')
def setup_global_help(mariadb_root_password=None):
	'''setup help table in a separate database that will be
	shared by the whole bench and set `global_help_setup` as 1 in
	common_site_config.json'''

	from frappe.installer import update_site_config

	frappe.local.flags = frappe._dict()
	frappe.local.flags.in_setup_help = True
	frappe.local.flags.in_install = True
	frappe.local.lang = 'en'
	frappe.local.conf = frappe.get_site_config(sites_path='.')

	update_site_config('global_help_setup', 1,
		site_config_path=os.path.join('.', 'common_site_config.json'))

	if mariadb_root_password:
		frappe.local.conf.root_password = mariadb_root_password

	from frappe.utils.help import sync
	sync()

@click.command('setup-help')
@pass_context
def setup_help(context):
	'''Setup help table in the current site (called after migrate)'''
	from frappe.utils.help import sync

	for site in context.sites:
		try:
			frappe.init(site)
			frappe.connect()
			sync()
		finally:
			frappe.destroy()

@click.command('rebuild-global-search')
@pass_context
def rebuild_global_search(context):
	'''Setup help table in the current site (called after migrate)'''
	from frappe.utils.global_search import (get_doctypes_with_global_search, rebuild_for_doctype)

	for site in context.sites:
		try:
			frappe.init(site)
			frappe.connect()
			doctypes = get_doctypes_with_global_search()
			for i, doctype in enumerate(doctypes):
				rebuild_for_doctype(doctype)
				update_progress_bar('Rebuilding Global Search', i, len(doctypes))

		finally:
			frappe.destroy()


commands = [
	build,
	clear_cache,
	clear_website_cache,
	console,
	destroy_all_sessions,
	execute,
	export_csv,
	export_doc,
	export_fixtures,
	export_json,
	get_version,
	import_csv,
	import_doc,
	make_app,
	mysql,
	request,
	reset_perms,
	run_tests,
	run_ui_tests,
	run_setup_wizard_ui_test,
	serve,
	set_config,
	watch,
	_bulk_rename,
	add_to_email_queue,
	setup_global_help,
	setup_help,
	rebuild_global_search
]
