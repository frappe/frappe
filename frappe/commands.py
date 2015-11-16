# Copyright (c) 2015, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, absolute_import
import sys
import os
import json
import click
import hashlib
import cProfile
import StringIO
import pstats
import frappe
import frappe.utils
from frappe.utils import cint
from distutils.spawn import find_executable
from functools import wraps

click.disable_unicode_literals_warning = True

def pass_context(f):
	@wraps(f)
	def _func(ctx, *args, **kwargs):
		profile = ctx.obj['profile']
		if profile:
			pr = cProfile.Profile()
			pr.enable()

		ret = f(frappe._dict(ctx.obj), *args, **kwargs)

		if profile:
			pr.disable()
			s = StringIO.StringIO()
			ps = pstats.Stats(pr, stream=s)\
				.sort_stats('cumtime', 'tottime', 'ncalls')
			ps.print_stats()
			print s.getvalue()

		return ret

	return click.pass_context(_func)

def get_single_site(context):
	if not len(context.sites) == 1:
		print 'please select a site'
		sys.exit(1)
	site = context.sites[0]
	return site

def call_command(cmd, context):
	return click.Context(cmd, obj=context).forward(cmd)

@click.command('new-site')
@click.argument('site')
@click.option('--db-name', help='Database name')
@click.option('--mariadb-root-username', default='root', help='Root username for MariaDB')
@click.option('--mariadb-root-password', help='Root password for MariaDB')
@click.option('--admin-password', help='Administrator password for new site', default=None)
@click.option('--verbose', is_flag=True, default=False, help='Verbose')
@click.option('--force', help='Force restore if site/database already exists', is_flag=True, default=False)
@click.option('--source_sql', help='Initiate database with a SQL file')
@click.option('--install-app', multiple=True, help='Install app after installation')
def new_site(site, mariadb_root_username=None, mariadb_root_password=None, admin_password=None, verbose=False, install_apps=None, source_sql=None, force=None, install_app=None, db_name=None):
	"Install a new site"
	if not db_name:
		db_name = hashlib.sha1(site).hexdigest()[:10]

	frappe.init(site=site)
	_new_site(db_name, site, mariadb_root_username=mariadb_root_username, mariadb_root_password=mariadb_root_password, admin_password=admin_password, verbose=verbose, install_apps=install_app, source_sql=source_sql, force=force)
	if len(frappe.utils.get_sites()) == 1:
		use(site)

def _new_site(db_name, site, mariadb_root_username=None, mariadb_root_password=None, admin_password=None, verbose=False, install_apps=None, source_sql=None,force=False, reinstall=False):
	"Install a new Frappe site"
	from frappe.installer import install_db, make_site_dirs
	from frappe.installer import install_app as _install_app
	import frappe.utils.scheduler

	frappe.init(site=site)

	try:
		# enable scheduler post install?
		enable_scheduler = _is_scheduler_enabled()
	except:
		enable_scheduler = False

	install_db(root_login=mariadb_root_username, root_password=mariadb_root_password, db_name=db_name, admin_password=admin_password, verbose=verbose, source_sql=source_sql,force=force, reinstall=reinstall)
	make_site_dirs()
	_install_app("frappe", verbose=verbose, set_as_patched=not source_sql)

	if frappe.conf.get("install_apps"):
		for app in frappe.conf.install_apps:
			_install_app(app, verbose=verbose, set_as_patched=not source_sql)

	if install_apps:
		for app in install_apps:
			_install_app(app, verbose=verbose, set_as_patched=not source_sql)

	frappe.utils.scheduler.toggle_scheduler(enable_scheduler)
	scheduler_status = "disabled" if frappe.utils.scheduler.is_scheduler_disabled() else "enabled"
	print "*** Scheduler is", scheduler_status, "***"
	frappe.destroy()

def _is_scheduler_enabled():
	enable_scheduler = False
	try:
		frappe.connect()
		enable_scheduler = cint(frappe.db.get_single_value("System Settings", "enable_scheduler")) and True or False
	except:
		pass
	finally:
		frappe.db.close()

	return enable_scheduler

@click.command('restore')
@click.argument('sql-file-path')
@click.option('--mariadb-root-username', default='root', help='Root username for MariaDB')
@click.option('--mariadb-root-password', help='Root password for MariaDB')
@click.option('--db-name', help='Database name for site in case it is a new one')
@click.option('--admin-password', help='Administrator password for new site')
@click.option('--install-app', multiple=True, help='Install app after installation')
@pass_context
def restore(context, sql_file_path, mariadb_root_username=None, mariadb_root_password=None, db_name=None, verbose=None, install_app=None, admin_password=None, force=None):
	"Restore site database from an sql file"

	site = get_single_site(context)
	frappe.init(site=site)
	db_name = db_name or frappe.conf.db_name or hashlib.sha1(site).hexdigest()[:10]
	_new_site(db_name, site, mariadb_root_username=mariadb_root_username, mariadb_root_password=mariadb_root_password, admin_password=admin_password, verbose=context.verbose, install_apps=install_app, source_sql=sql_file_path, force=context.force)

@click.command('reinstall')
@pass_context
def reinstall(context):
	"Reinstall site ie. wipe all data and start over"
	site = get_single_site(context)
	try:
		frappe.init(site=site)
		frappe.connect()
		frappe.clear_cache()
		installed = frappe.get_installed_apps()
		frappe.clear_cache()
	except Exception:
		installed = []
	finally:
		if frappe.db:
			frappe.db.close()
		frappe.destroy()

	frappe.init(site=site)
	_new_site(frappe.conf.db_name, site, verbose=context.verbose, force=True, reinstall=True, install_apps=installed)

@click.command('install-app')
@click.argument('app')
@pass_context
def install_app(context, app):
	"Install a new app to site"
	from frappe.installer import install_app as _install_app
	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()
		try:
			_install_app(app, verbose=context.verbose)
		finally:
			frappe.destroy()

@click.command('list-apps')
@pass_context
def list_apps(context):
	"Reinstall site ie. wipe all data and start over"
	site = get_single_site(context)
	frappe.init(site=site)
	frappe.connect()
	print "\n".join(frappe.get_installed_apps())
	frappe.destroy()

@click.command('add-system-manager')
@click.argument('email')
@click.option('--first-name')
@click.option('--last-name')
@pass_context
def add_system_manager(context, email, first_name, last_name):
	"Add a new system manager to a site"
	import frappe.utils.user
	for site in context.sites:
		frappe.connect(site=site)
		try:
			frappe.utils.user.add_system_manager(email, first_name, last_name)
			frappe.db.commit()
		finally:
			frappe.destroy()

@click.command('migrate')
@click.option('--rebuild-website', help="Rebuild webpages after migration")
@pass_context
def migrate(context, rebuild_website=False):
	"Run patches, sync schema and rebuild files/translations"
	import frappe.modules.patch_handler
	import frappe.model.sync
	from frappe.utils.fixtures import sync_fixtures
	import frappe.translate
	from frappe.desk.notifications import clear_notifications

	for site in context.sites:
		print 'Migrating', site
		frappe.init(site=site)
		frappe.connect()

		try:
			prepare_for_update()

			# run patches
			frappe.modules.patch_handler.run_all()
			# sync
			frappe.model.sync.sync_all(verbose=context.verbose)
			frappe.translate.clear_cache()
			sync_fixtures()

			clear_notifications()
		finally:
			frappe.destroy()

	if rebuild_website:
		call_command(build_website, context)
	else:
		call_command(sync_www, context)

def prepare_for_update():
	from frappe.sessions import clear_global_cache
	clear_global_cache()

@click.command('run-patch')
@click.argument('module')
@pass_context
def run_patch(context, module):
	"Run a particular patch"
	import frappe.modules.patch_handler
	for site in context.sites:
		frappe.init(site=site)
		try:
			frappe.connect()
			frappe.modules.patch_handler.run_single(module, force=context.force)
		finally:
			frappe.destroy()

@click.command('reload-doc')
@click.argument('module')
@click.argument('doctype')
@click.argument('docname')
@pass_context
def reload_doc(context, module, doctype, docname):
	"Reload schema for a DocType"
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.reload_doc(module, doctype, docname, force=context.force)
			frappe.db.commit()
		finally:
			frappe.destroy()

@click.command('build')
@click.option('--make-copy', is_flag=True, default=False, help='Copy the files instead of symlinking')
@click.option('--verbose', is_flag=True, default=False, help='Verbose')
def build(make_copy=False, verbose=False):
	"Minify + concatenate JS and CSS files, build translations"
	import frappe.build
	import frappe
	frappe.init('')
	frappe.build.bundle(False, make_copy=make_copy, verbose=verbose)

@click.command('watch')
def watch():
	"Watch and concatenate JS and CSS files as and when they change"
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
@pass_context
def destroy_all_sessions(context):
	"Clear sessions of all users (logs them out)"
	import frappe.sessions
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.sessions.clear_all_sessions()
			frappe.db.commit()
		finally:
			frappe.destroy()

@click.command('sync-www')
@click.option('--force', help='Rebuild all pages', is_flag=True, default=False)
@pass_context
def sync_www(context, force=False):
	"Sync files from static pages from www directory to Web Pages"
	from frappe.website import statics
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			statics.sync_statics(rebuild=force)
			frappe.db.commit()
		finally:
			frappe.destroy()

@click.command('build-website')
@pass_context
def build_website(context):
	"Sync statics and clear cache"
	from frappe.website import render, statics
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			render.clear_cache()
			statics.sync(verbose=context.verbose).start(True)
			frappe.db.commit()
		finally:
			frappe.destroy()

@click.command('make-docs')
@pass_context
@click.argument('app')
@click.argument('docs_version')
def make_docs(context, app, docs_version):
	"Setup docs in target folder of target app"
	from frappe.utils.setup_docs import setup_docs
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			make = setup_docs(app)
			make.build(docs_version)
		finally:
			frappe.destroy()

@click.command('sync-docs')
@pass_context
@click.argument('app')
def sync_docs(context, app):
	"Sync docs from /docs folder into the database (Web Page)"
	from frappe.utils.setup_docs import setup_docs
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			make = setup_docs(app)
			make.sync_docs()
		finally:
			frappe.destroy()


@click.command('write-docs')
@pass_context
@click.argument('app')
@click.argument('target')
@click.option('--local', default=False, is_flag=True, help='Run app locally')
def write_docs(context, app, target, local=False):
	"Setup docs in target folder of target app"
	from frappe.utils.setup_docs import setup_docs
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			make = setup_docs(app)
			make.make_docs(target, local)
		finally:
			frappe.destroy()

@click.command('build-docs')
@pass_context
@click.argument('app')
@click.argument('docs_version')
@click.argument('target')
@click.option('--local', default=False, is_flag=True, help='Run app locally')
def build_docs(context, app, docs_version, target, local=False):
	"Setup docs in target folder of target app"
	from frappe.utils.setup_docs import setup_docs
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			make = setup_docs(app)
			make.build(docs_version)
			make.sync_docs()
			make.make_docs(target, local)
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
	"execute a function"
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()

			if args:
				args = eval(args)
			else:
				args = ()

			if kwargs:
				kwargs = eval(args)
			else:
				kwargs = {}

			ret = frappe.get_attr(method)(*args, **kwargs)

			if frappe.db:
				frappe.db.commit()
		finally:
			frappe.destroy()
		if ret:
			print json.dumps(ret)

@click.command('celery')
@click.argument('args')
def celery(args):
	"Run a celery command"
	python = sys.executable
	os.execv(python, [python, "-m", "frappe.celery_app"] + args.split())

@click.command('trigger-scheduler-event')
@click.argument('event')
@pass_context
def trigger_scheduler_event(context, event):
	"Trigger a scheduler event"
	import frappe.utils.scheduler
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.utils.scheduler.trigger(site, event, now=context.force)
		finally:
			frappe.destroy()

@click.command('enable-scheduler')
@pass_context
def enable_scheduler(context):
	"Enable scheduler"
	import frappe.utils.scheduler
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.utils.scheduler.enable_scheduler()
			frappe.db.commit()
			print "Enabled for", site
		finally:
			frappe.destroy()

@click.command('disable-scheduler')
@pass_context
def disable_scheduler(context):
	"Disable scheduler"
	import frappe.utils.scheduler
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.utils.scheduler.disable_scheduler()
			frappe.db.commit()
			print "Disabled for", site
		finally:
			frappe.destroy()

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
@click.argument('name')
@click.argument('path')
@pass_context
def export_json(context, doctype, name, path):
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
	"Dump DocType as csv"
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
	"export fixtures"
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
@pass_context
def import_csv(context, path, only_insert=False, submit_after_import=False, ignore_encoding_errors=False):
	"Import CSV using data import tool"
	from frappe.core.page.data_import_tool import importer
	from frappe.utils.csvutils import read_csv_content
	site = get_single_site(context)

	with open(path, 'r') as csvfile:
		content = read_csv_content(csvfile.read())

	frappe.init(site=site)
	frappe.connect()

	try:
		importer.upload(content, submit_after_import=submit_after_import,
			ignore_encoding_errors=ignore_encoding_errors, overwrite=not only_insert,
			via_console=True)
		frappe.db.commit()
	except Exception:
		print frappe.get_traceback()

	frappe.destroy()

@click.command('bulk-rename')
@click.argument('doctype')
@click.argument('path')
@pass_context
def _bulk_rename(context, doctype, path):
	"Rename multiple records via CSV file"
	from frappe.model.rename_doc import bulk_rename
	from frappe.utils.csvutils import read_csv_content

	site = get_single_site(context)

	with open(path, 'r') as csvfile:
		rows = read_csv_content(csvfile.read())

	frappe.init(site=site)
	frappe.connect()

	bulk_rename(doctype, rows, via_console = True)

	frappe.destroy()

# translation
@click.command('build-message-files')
@pass_context
def build_message_files(context):
	"Build message files for translation"
	import frappe.translate
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.translate.rebuild_all_translation_files()
		finally:
			frappe.destroy()

@click.command('get-untranslated')
@click.argument('lang')
@click.argument('untranslated_file')
@click.option('--all', default=False, is_flag=True, help='Get all message strings')
@pass_context
def get_untranslated(context, lang, untranslated_file, all=None):
	"Get untranslated strings for language"
	import frappe.translate
	site = get_single_site(context)
	try:
		frappe.init(site=site)
		frappe.connect()
		frappe.translate.get_untranslated(lang, untranslated_file, get_all=all)
	finally:
		frappe.destroy()

@click.command('update-translations')
@click.argument('lang')
@click.argument('untranslated_file')
@click.argument('translated-file')
@pass_context
def update_translations(context, lang, untranslated_file, translated_file):
	"Update translated strings"
	import frappe.translate
	site = get_single_site(context)
	try:
		frappe.init(site=site)
		frappe.connect()
		frappe.translate.update_translations(lang, untranslated_file, translated_file)
	finally:
		frappe.destroy()

@click.command('set-admin-password')
@click.argument('admin-password')
@pass_context
def set_admin_password(context, admin_password):
	"Set Administrator password for a site"
	import getpass

	for site in context.sites:
		try:
			frappe.init(site=site)

			while not admin_password:
				admin_password = getpass.getpass("Administrator's password for {0}: ".format(site))

			frappe.connect()
			frappe.db.sql("""update __Auth set `password`=password(%s)
				where user='Administrator'""", (admin_password,))
			frappe.db.commit()
			admin_password = None
		finally:
			frappe.destroy()

@click.command('mysql')
@pass_context
def mysql(context):
	"Start Mariadb console for a site"
	site = get_single_site(context)
	frappe.init(site=site)
	msq = find_executable('mysql')
	os.execv(msq, [msq, '-u', frappe.conf.db_name, '-p'+frappe.conf.db_password, frappe.conf.db_name, '-h', frappe.conf.db_host or "localhost", "-A"])

@click.command('console')
@pass_context
def console(context):
	"Start ipython console for a site"
	site = get_single_site(context)
	frappe.init(site=site)
	frappe.connect()
	frappe.local.lang = frappe.db.get_default("lang")
	import IPython
	IPython.embed()

@click.command('run-tests')
@click.option('--app')
@click.option('--doctype')
@click.option('--test', multiple=True)
@click.option('--driver')
@click.option('--module')
@pass_context
def run_tests(context, app=None, module=None, doctype=None, test=(), driver=None):
	"Run tests"
	import frappe.test_runner
	from frappe.utils import sel
	tests = test

	site = get_single_site(context)
	frappe.init(site=site)

	if frappe.conf.run_selenium_tests and False:
		sel.start(context.verbose, driver)

	try:
		ret = frappe.test_runner.main(app, module, doctype, context.verbose, tests=tests, force=context.force)
		if len(ret.failures) == 0 and len(ret.errors) == 0:
			ret = 0
	finally:
		pass
		if frappe.conf.run_selenium_tests:
			sel.close()

	sys.exit(ret)

@click.command('serve')
@click.option('--port', default=8000)
@click.option('--profile', is_flag=True, default=False)
@pass_context
def serve(context, port=None, profile=False, sites_path='.', site=None):
	"Start development web server"
	if not context.sites:
		site = None
	else:
		site = context.sites[0]
	import frappe.app
	frappe.app.serve(port=port, profile=profile, site=site, sites_path='.')

@click.command('request')
@click.argument('args')
@pass_context
def request(context, args):
	"Run a request as an admin"
	import frappe.handler
	import frappe.api
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			if "?" in args:
				frappe.local.form_dict = frappe._dict([a.split("=") for a in args.split("?")[-1].split("&")])
			else:
				frappe.local.form_dict = frappe._dict()

			if args.startswith("/api/method"):
				frappe.local.form_dict.cmd = args.split("?")[0].split("/")[-1]

			frappe.handler.execute_cmd(frappe.form_dict.cmd)

			print frappe.response
		finally:
			frappe.destroy()

@click.command('doctor')
def doctor():
	"Get diagnostic info about background workers"
	from frappe.utils.doctor import doctor as _doctor
	frappe.init('')
	return _doctor()

@click.command('celery-doctor')
@click.option('--site', help='site name')
def celery_doctor(site=None):
	"Get diagnostic info about background workers"
	from frappe.utils.doctor import celery_doctor as _celery_doctor
	frappe.init('')
	return _celery_doctor(site=site)

@click.command('purge-all-tasks')
def purge_all_tasks():
	"Purge any pending periodic tasks of 'all' event. Doesn't purge hourly, daily and weekly"
	frappe.init('')
	from frappe.utils.doctor import purge_pending_tasks
	count = purge_pending_tasks()
	print "Purged {} tasks".format(count)

@click.command('dump-queue-status')
def dump_queue_status():
	"Dump detailed diagnostic infomation for task queues in JSON format"
	frappe.init('')
	from frappe.utils.doctor import dump_queue_status as _dump_queue_status
	print json.dumps(_dump_queue_status(), indent=1)

@click.command('make-app')
@click.argument('destination')
@click.argument('app_name')
def make_app(destination, app_name):
	from frappe.utils.boilerplate import make_boilerplate
	make_boilerplate(destination, app_name)

@click.command('use')
@click.argument('site')
def _use(site, sites_path='.'):
	use(site, sites_path=sites_path)

def use(site, sites_path='.'):
	with open(os.path.join(sites_path,  "currentsite.txt"), "w") as sitefile:
		sitefile.write(site)

@click.command('backup')
@click.option('--with-files', default=False, is_flag=True, help="Take backup with files")
@pass_context
def backup(context, with_files=False, backup_path_db=None, backup_path_files=None, quiet=False):
	"Backup"
	from frappe.utils.backups import scheduled_backup
	verbose = context.verbose
	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()
		odb = scheduled_backup(ignore_files=not with_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files, force=True)
		if verbose:
			from frappe.utils import now
			print "database backup taken -", odb.backup_path_db, "- on", now()
			if with_files:
				print "files backup taken -", odb.backup_path_files, "- on", now()
		frappe.destroy()


@click.command('remove-from-installed-apps')
@click.argument('app')
@pass_context
def remove_from_installed_apps(context, app):
	from frappe.installer import remove_from_installed_apps
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			remove_from_installed_apps(app)
		finally:
			frappe.destroy()

@click.command('uninstall-app')
@click.argument('app')
@click.option('--dry-run', help='List all doctypes that will be deleted', is_flag=True, default=False)
@pass_context
def uninstall(context, app, dry_run=False):
	from frappe.installer import remove_app
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			remove_app(app, dry_run)
		finally:
			frappe.destroy()

def move(dest_dir, site):
	import os
	if not os.path.isdir(dest_dir):
		raise Exception, "destination is not a directory or does not exist"

	frappe.init(site)
	old_path = frappe.utils.get_site_path()
	new_path = os.path.join(dest_dir, site)

	# check if site dump of same name already exists
	site_dump_exists = True
	count = 0
	while site_dump_exists:
		final_new_path = new_path + (count and str(count) or "")
		site_dump_exists = os.path.exists(final_new_path)
		count = int(count or 0) + 1

	os.rename(old_path, final_new_path)
	frappe.destroy()
	return final_new_path


@click.command('set-config')
@click.argument('key')
@click.argument('value')
@pass_context
def set_config(context, key, value):
	from frappe.installer import update_site_config
	for site in context.sites:
		frappe.init(site=site)
		update_site_config(key, value)
		frappe.destroy()

@click.command('drop-site')
@click.argument('site')
@click.option('--root-login', default='root')
@click.option('--root-password')
def drop_site(site, root_login='root', root_password=None):
	from frappe.installer import get_current_host, make_connection
	from frappe.model.db_schema import DbManager
	from frappe.utils.backups import scheduled_backup

	frappe.init(site=site)
	frappe.connect()
	scheduled_backup(ignore_files=False, force=True)

	db_name = frappe.local.conf.db_name
	frappe.local.db = make_connection(root_login, root_password)
	dbman = DbManager(frappe.local.db)
	dbman.delete_user(db_name, get_current_host())
	dbman.drop_database(db_name)

	archived_sites_dir = os.path.join(frappe.get_app_path('frappe'), '..', '..', '..', 'archived_sites')
	if not os.path.exists(archived_sites_dir):
		os.mkdir(archived_sites_dir)
	move(archived_sites_dir, site)

@click.command('version')
@pass_context
def get_version(context):
	frappe.init(site=context.sites[0])
	for m in sorted(frappe.local.app_modules.keys()):
		module = frappe.get_module(m)
		if hasattr(module, "__version__"):
			print "{0} {1}".format(m, module.__version__)

# commands = [
# 	new_site,
# 	restore,
# 	install_app,
# 	run_patch,
# 	migrate,
# 	add_system_manager,
# 	celery
# ]
commands = [
	new_site,
	restore,
	reinstall,
	install_app,
	list_apps,
	add_system_manager,
	migrate,
	run_patch,
	reload_doc,
	build,
	watch,
	clear_cache,
	clear_website_cache,
	destroy_all_sessions,
	sync_www,
	build_website,
	make_docs,
	sync_docs,
	write_docs,
	build_docs,
	reset_perms,
	execute,
	celery,
	trigger_scheduler_event,
	enable_scheduler,
	disable_scheduler,
	export_doc,
	export_json,
	export_csv,
	export_fixtures,
	import_doc,
	import_csv,
	_bulk_rename,
	build_message_files,
	get_untranslated,
	update_translations,
	set_admin_password,
	mysql,
	run_tests,
	serve,
	request,
	doctor,
	celery_doctor,
	purge_all_tasks,
	dump_queue_status,
	console,
	make_app,
	_use,
	backup,
	remove_from_installed_apps,
	uninstall,
	drop_site,
	set_config,
	get_version,
]
