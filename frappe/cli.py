#!/usr/bin/env python2.7

# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import os
import subprocess
import frappe
from frappe.utils import cint

site_arg_optional = ['serve', 'build', 'watch', 'celery', 'resize_images']

def get_site(parsed_args):
	if not parsed_args.get("site") and os.path.exists(os.path.join(parsed_args["sites_path"], "currentsite.txt")):
		with open(os.path.join(parsed_args["sites_path"], "currentsite.txt"), "r") as sitefile:
			parsed_args["site"] = sitefile.read().strip()
			return  parsed_args["site"]
	return parsed_args.get("site")

def main():
	parsed_args = frappe._dict(vars(setup_parser()))
	fn = get_function(parsed_args)
	if parsed_args.get("sites_path"):
		parsed_args["sites_path"] = parsed_args["sites_path"][0]
	else:
		parsed_args["sites_path"] = os.environ.get("SITES_PATH", ".")
	sites_path = parsed_args.get("sites_path")

	if not parsed_args.get("make_app"):

		if parsed_args.get("site")=="all":
			for site in get_sites(parsed_args["sites_path"]):
				print "\nRunning", fn, "for", site
				print "-"*50
				args = parsed_args.copy()
				args["site"] = site
				frappe.init(site, sites_path=sites_path)
				ret = run(fn, args)
				if ret:
					# if there's a return value, it's an error, so quit
					return ret
		else:
			site = get_site(parsed_args)
			if fn not in site_arg_optional and not site:
				print 'site argument required'
				return 1
			elif site:
				frappe.init(site, sites_path=sites_path)
			else:
				# site argument optional
				frappe.init("", sites_path=sites_path)
			return run(fn, parsed_args)
	else:
		return run(fn, parsed_args)

def cmd(fn):
	def new_fn(*args, **kwargs):
		import inspect
		fnargs, varargs, varkw, defaults = inspect.getargspec(fn)
		new_kwargs = {}
		for i, a in enumerate(fnargs):
			# should not pass an argument more than once
			if i >= len(args) and a in kwargs:
				new_kwargs[a] = kwargs.get(a)

		return fn(*args, **new_kwargs)

	return new_fn


def run(fn, args):
	import cProfile, pstats, StringIO

	use_profiler = args.get("profile") and fn!="serve"
	if use_profiler:
		pr = cProfile.Profile()
		pr.enable()

	if isinstance(args.get(fn), (list, tuple)):
		out = globals().get(fn)(*args.get(fn), **args)
	else:
		out = globals().get(fn)(**args)

	if use_profiler:
		pr.disable()
		s = StringIO.StringIO()
		ps = pstats.Stats(pr, stream=s).sort_stats('tottime', 'ncalls')
		ps.print_stats()
		print s.getvalue()

	return out

def get_function(args):
	for fn, val in args.items():
		if (val or isinstance(val, list)) and globals().get(fn):
			return fn

def get_sites(sites_path=None):
	import os
	if not sites_path:
		sites_path = '.'
	return [site for site in os.listdir(sites_path)
			if os.path.isdir(os.path.join(sites_path, site))
				and not site in ('assets',)]

def setup_parser():
	import argparse
	parser = argparse.ArgumentParser(description="Run frappe utility functions")

	setup_install(parser)
	setup_utilities(parser)
	setup_translation(parser)
	setup_test(parser)

	parser.add_argument("site", nargs="?")

	# common
	parser.add_argument("-f", "--force", default=False, action="store_true",
		help="Force execution where applicable (look for [-f] in help)")
	parser.add_argument("--all", default=False, action="store_true",
		help="Get all (where applicable)")
	parser.add_argument("--verbose", default=False, action="store_true",
		help="Show verbose output (where applicable)")
	parser.add_argument("--quiet", default=False, action="store_true",
		help="Do not show verbose output (where applicable)")

	return parser.parse_args()

def setup_install(parser):
	parser.add_argument("--make_app", metavar="DEST", nargs=1,
		help="Make a new application with boilerplate")
	parser.add_argument("--install", metavar="DB-NAME", nargs=1,
		help="Install a new db")
	parser.add_argument("--root_password", metavar="ROOT-PASSWD",
		help="MariaDB root password")
	parser.add_argument("--sites_path", metavar="SITES_PATH", nargs=1,
		help="path to directory with sites")
	parser.add_argument("--install_app", metavar="APP-NAME", nargs=1,
		help="Install a new app")
	parser.add_argument("--add_to_installed_apps", metavar="APP-NAME", nargs="*",
		help="Add these app(s) to Installed Apps")
	parser.add_argument("--reinstall", default=False, action="store_true",
		help="Install a fresh app in db_name specified in conf.py")
	parser.add_argument("--restore", metavar=("DB-NAME", "SQL-FILE"), nargs=2,
		help="Restore from an sql file")
	parser.add_argument("--with_scheduler_enabled", default=False, action="store_true",
		help="Enable scheduler on restore")
	parser.add_argument("--add_system_manager", nargs="+",
		metavar=("EMAIL", "[FIRST-NAME] [LAST-NAME]"), help="Add a user with all roles")

def setup_test(parser):
	parser.add_argument("--run_tests", default=False, action="store_true",
		help="Run tests options [-d doctype], [-m module]")
	parser.add_argument("--app", metavar="APP-NAME", nargs=1,
		help="Run command for specified app")
	parser.add_argument("-d", "--doctype", metavar="DOCTYPE", nargs=1,
		help="Run command for specified doctype")
	parser.add_argument("-m", "--module", metavar="MODULE", nargs=1,
		help="Run command for specified module")
	parser.add_argument("--tests", metavar="TEST FUNCTION", nargs="*",
		help="Run one or more specific test functions")
	parser.add_argument("--serve_test", action="store_true", help="Run development server for testing")
	parser.add_argument("--driver", nargs="?", help="Run selenium using given driver")


def setup_utilities(parser):
	# serving
	parser.add_argument("--port", type=int, help="port for development server")
	parser.add_argument("--use", action="store_true", help="Set current site for development.")

	# update
	parser.add_argument("-u", "--update", nargs="*", metavar=("REMOTE", "BRANCH"),
		help="Perform git pull, run patches, sync schema and rebuild files/translations")
	parser.add_argument("--reload_gunicorn", default=False, action="store_true", help="reload gunicorn on update")
	parser.add_argument("--patch", nargs=1, metavar="PATCH-MODULE",
		help="Run a particular patch [-f]")
	parser.add_argument("-l", "--latest", default=False, action="store_true",
		help="Run patches, sync schema and rebuild files/translations")
	parser.add_argument("--sync_all", default=False, action="store_true",
		help="Reload all doctypes, pages, etc. using txt files [-f]")
	parser.add_argument("--update_all_sites", nargs="*", metavar=("REMOTE", "BRANCH"),
		help="Perform git pull, run patches, sync schema and rebuild files/translations")

	parser.add_argument("--reload_doc", nargs=3,
		metavar=('"MODULE"', '"DOCTYPE"', '"DOCNAME"'))

	# build
	parser.add_argument("-b", "--build", default=False, action="store_true",
		help="Minify + concatenate JS and CSS files, build translations")
	parser.add_argument("--make_copy", default=False, action="store_true",
		help="Make copy of assets instead of symlinks")
	parser.add_argument("-w", "--watch", default=False, action="store_true",
		help="Watch and concatenate JS and CSS files as and when they change")

	# misc
	parser.add_argument("--backup", default=False, action="store_true",
		help="Take backup of database in backup folder [--with_files]")
	parser.add_argument("--move", default=False, action="store_true",
		help="Move site to different directory defined by --dest_dir")
	parser.add_argument("--dest_dir", nargs=1, metavar="DEST-DIR",
		help="Move site to different directory")
	parser.add_argument("--with_files", default=False, action="store_true",
		help="Also take backup of files")
	parser.add_argument("--domain", nargs="*",
		help="Get or set domain in Website Settings")
	parser.add_argument("--make_conf", nargs="*", metavar=("DB-NAME", "DB-PASSWORD"),
		help="Create new conf.py file")
	parser.add_argument("--make_custom_server_script", nargs=1, metavar="DOCTYPE",
		help="Create new custome server script")
	parser.add_argument("--init_list", nargs=1, metavar="DOCTYPE",
		help="Create new list.js and list.html files")
	parser.add_argument("--set_admin_password", metavar='ADMIN-PASSWORD', nargs="*",
		help="Set administrator password")
	parser.add_argument("--request", metavar='URL-ARGS', nargs=1, help="Run request as admin")
	parser.add_argument("--mysql", action="store_true", help="get mysql shell for a site")
	parser.add_argument("--serve", action="store_true", help="Run development server")
	parser.add_argument("--profile", action="store_true", help="enable profiling in development server")
	parser.add_argument("--smtp", action="store_true", help="Run smtp debug server",
		dest="smtp_debug_server")
	parser.add_argument("--python", action="store_true", help="get python shell for a site")
	parser.add_argument("--flush_memcache", action="store_true", help="flush memcached")
	parser.add_argument("--ipython", action="store_true", help="get ipython shell for a site")
	parser.add_argument("--execute", help="execute a function", nargs=1, metavar="FUNCTION")
	parser.add_argument("--get_site_status", action="store_true", help="Get site details")
	parser.add_argument("--update_site_config", nargs=1,
		metavar="site-CONFIG-JSON",
		help="Update site_config.json for a given site")
	parser.add_argument("--resize_images", nargs=1, metavar="PATH", help="resize images to a max width of 500px")


	# clear
	parser.add_argument("--clear_web", default=False, action="store_true",
		help="Clear website cache")
	parser.add_argument("--build_website", default=False, action="store_true",
		help="Sync statics and clear cache")
	parser.add_argument("--sync_statics", default=False, action="store_true",
		help="Sync files from templates/statics to Web Pages")
	parser.add_argument("--clear_cache", default=False, action="store_true",
		help="Clear cache, doctype cache and defaults")
	parser.add_argument("--reset_perms", default=False, action="store_true",
		help="Reset permissions for all doctypes")
	parser.add_argument("--clear_all_sessions", default=False, action="store_true",
		help="Clear sessions of all users (logs them out)")

	# scheduler
	parser.add_argument("--run_scheduler", default=False, action="store_true",
		help="Trigger scheduler")
	parser.add_argument("--celery", nargs="*", help="Run Celery Commands")
	parser.add_argument("--run_scheduler_event", nargs=1,
		metavar="all | daily | weekly | monthly",
		help="Run a scheduler event")
	parser.add_argument("--enable_scheduler", default=False, action="store_true",
		help="Enable scheduler")
	parser.add_argument("--disable_scheduler", default=False, action="store_true",
		help="Disable scheduler")


	# replace
	parser.add_argument("--replace", nargs=3,
		metavar=("SEARCH-REGEX", "REPLACE-BY", "FILE-EXTN"),
		help="Multi-file search-replace [-f]")

	# import/export
	parser.add_argument("--export_doc", nargs=2, metavar=('"DOCTYPE"', '"DOCNAME"'))
	parser.add_argument("--export_doclist", nargs=3, metavar=("DOCTYPE", "NAME", "PATH"),
		help="""Export doclist as json to the given path, use '-' as name for Singles.""")
	parser.add_argument("--export_csv", nargs=2, metavar=("DOCTYPE", "PATH"),
		help="""Dump DocType as csv""")
	parser.add_argument("--export_fixtures", default=False, action="store_true",
		help="""Export fixtures""")
	parser.add_argument("--import_doc", nargs=1, metavar="PATH",
		help="""Import (insert/update) doclist. If the argument is a directory, all files ending with .json are imported""")

def setup_translation(parser):
	parser.add_argument("--build_message_files", default=False, action="store_true",
		help="Build message files for translation.")
	parser.add_argument("--get_untranslated", nargs=2, metavar=("LANG-CODE", "TARGET-FILE-PATH"),
		help="""Get untranslated strings for lang.""")
	parser.add_argument("--update_translations", nargs=3,
		metavar=("LANG-CODE", "UNTRANSLATED-FILE-PATH", "TRANSLATED-FILE-PATH"),
		help="""Update translated strings.""")

# methods
@cmd
def make_app(destination):
	from frappe.utils.boilerplate import make_boilerplate
	make_boilerplate(destination)

@cmd
def use(sites_path):
	with open(os.path.join(sites_path,  "currentsite.txt"), "w") as sitefile:
		sitefile.write(frappe.local.site)

# install
def _install(db_name, root_login="root", root_password=None, source_sql=None,
		admin_password = 'admin', force=False, site_config=None, reinstall=False, quiet=False, install_apps=None):

	from frappe.installer import install_db, install_app, make_site_dirs
	import frappe.utils.scheduler

	verbose = not quiet

	# enable scheduler post install?
	enable_scheduler = _is_scheduler_enabled()

	install_db(root_login=root_login, root_password=root_password, db_name=db_name, source_sql=source_sql,
		admin_password = admin_password, verbose=verbose, force=force, site_config=site_config, reinstall=reinstall)
	make_site_dirs()
	install_app("frappe", verbose=verbose, set_as_patched=not source_sql)

	if frappe.conf.get("install_apps"):
		for app in frappe.conf.install_apps:
			install_app(app, verbose=verbose, set_as_patched=not source_sql)

	if install_apps:
		for app in install_apps:
			install_app(app, verbose=verbose, set_as_patched=not source_sql)

	frappe.utils.scheduler.toggle_scheduler(enable_scheduler)
	scheduler_status = "disabled" if frappe.utils.scheduler.is_scheduler_disabled() else "enabled"
	print "*** Scheduler is", scheduler_status, "***"

@cmd
def install(db_name, root_login="root", root_password=None, source_sql=None,
		admin_password = 'admin', force=False, site_config=None, reinstall=False, quiet=False, install_apps=None):
	_install(db_name, root_login, root_password, source_sql, admin_password, force, site_config, reinstall, quiet, install_apps)
	frappe.destroy()

def _is_scheduler_enabled():
	enable_scheduler = False
	try:
		frappe.connect()
		enable_scheduler = cint(frappe.db.get_default("enable_scheduler"))
	except:
		pass
	finally:
		frappe.db.close()

	return enable_scheduler

@cmd
def install_app(app_name, quiet=False):
	verbose = not quiet
	from frappe.installer import install_app
	frappe.connect()
	install_app(app_name, verbose=verbose)
	frappe.destroy()

@cmd
def add_to_installed_apps(*apps):
	from frappe.installer import add_to_installed_apps
	frappe.connect()
	all_apps = frappe.get_all_apps(with_frappe=True)
	for each in apps:
		if each in all_apps:
			add_to_installed_apps(each, rebuild_website=False)
	frappe.destroy()

@cmd
def reinstall(quiet=False):
	verbose = not quiet
	try:
		frappe.connect()
		installed = frappe.get_installed_apps()
		frappe.clear_cache()
	except:
		installed = []
	finally:
		frappe.db.close()

	install(db_name=frappe.conf.db_name, verbose=verbose, force=True, reinstall=True, install_apps=installed)

@cmd
def restore(db_name, source_sql, force=False, quiet=False, with_scheduler_enabled=False):
	import frappe.utils.scheduler
	_install(db_name, source_sql=source_sql, quiet=quiet, force=force)

	try:
		frappe.connect()
		frappe.utils.scheduler.toggle_scheduler(with_scheduler_enabled)
		scheduler_status = "disabled" if frappe.utils.scheduler.is_scheduler_disabled() else "enabled"
		print "*** Scheduler is", scheduler_status, "***"
	finally:
		frappe.destroy()

@cmd
def add_system_manager(email, first_name=None, last_name=None):
	import frappe.utils.user
	frappe.connect()
	frappe.utils.user.add_system_manager(email, first_name, last_name)
	frappe.db.commit()
	frappe.destroy()

# utilities

@cmd
def update(remote=None, branch=None, reload_gunicorn=False):
	pull(remote=remote, branch=branch)

	# maybe there are new framework changes, any consequences?
	reload(frappe)
	build()
	latest()
	if reload_gunicorn:
		subprocess.check_output("killall -HUP gunicorn".split())

@cmd
def latest(rebuild_website=True, quiet=False):
	import frappe.modules.patch_handler
	import frappe.model.sync
	from frappe.utils.fixtures import sync_fixtures
	import frappe.translate
	from frappe.core.doctype.notification_count.notification_count import clear_notifications

	verbose = not quiet

	frappe.connect()

	try:
		# run patches
		frappe.modules.patch_handler.run_all()
		# sync
		frappe.model.sync.sync_all(verbose=verbose)
		frappe.translate.clear_cache()
		sync_fixtures()

		clear_notifications()

		if rebuild_website:
			build_website()
	finally:
		frappe.destroy()

@cmd
def sync_all(force=False, quiet=False):
	import frappe.model.sync
	verbose = not quiet
	frappe.connect()
	frappe.model.sync.sync_all(force=force, verbose=verbose)
	frappe.destroy()

@cmd
def patch(patch_module, force=False):
	import frappe.modules.patch_handler
	frappe.connect()
	frappe.modules.patch_handler.run_single(patch_module, force=force)
	frappe.destroy()

@cmd
def update_all_sites(remote=None, branch=None, quiet=False):
	verbose = not quiet
	pull(remote, branch)

	# maybe there are new framework changes, any consequences?
	reload(frappe)

	build()
	for site in get_sites():
		frappe.init(site)
		latest(verbose=verbose)

@cmd
def reload_doc(module, doctype, docname, force=False):
	frappe.connect()
	frappe.reload_doc(module, doctype, docname, force=force)
	frappe.db.commit()
	frappe.destroy()

@cmd
def build(make_copy=False, verbose=False):
	import frappe.build
	import frappe
	frappe.build.bundle(False, make_copy=make_copy, verbose=verbose)

@cmd
def watch():
	import frappe.build
	frappe.build.watch(True)

@cmd
def backup(with_files=False, backup_path_db=None, backup_path_files=None, quiet=False):
	from frappe.utils.backups import scheduled_backup
	verbose = not quiet
	frappe.connect()
	odb = scheduled_backup(ignore_files=not with_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files)
	if verbose:
		from frappe.utils import now
		print "database backup taken -", odb.backup_path_db, "- on", now()
		if with_files:
			print "files backup taken -", odb.backup_path_files, "- on", now()
	frappe.destroy()

@cmd
def move(dest_dir=None, site=None):
	import os
	if not dest_dir:
		raise Exception, "--dest_dir is required for --move"
	if not os.path.isdir(dest_dir):
		raise Exception, "destination is not a directory or does not exist"

	old_path = frappe.utils.get_site()
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
	return os.path.basename(final_new_path)

@cmd
def domain(host_url=None):
	frappe.connect()
	if host_url:
		frappe.db.set_value("Website Settings", None, "subdomain", host_url)
		frappe.db.commit()
	else:
		print frappe.db.get_value("Website Settings", None, "subdomain")
	frappe.destroy()

@cmd
def make_conf(db_name=None, db_password=None, site_config=None):
	from frappe.install_lib.install import make_conf
	make_conf(db_name=db_name, db_password=db_password, site_config=site_config)

@cmd
def make_custom_server_script(doctype):
	from frappe.core.doctype.custom_script.custom_script import make_custom_server_script_file
	frappe.connect()
	make_custom_server_script_file(doctype)
	frappe.destroy()

@cmd
def init_list(doctype):
	import frappe.core.doctype.doctype.doctype
	frappe.core.doctype.doctype.doctype.init_list(doctype)

# clear
@cmd
def clear_cache():
	import frappe.sessions
	from frappe.core.doctype.notification_count.notification_count import clear_notifications
	frappe.connect()
	frappe.clear_cache()
	clear_notifications()
	frappe.destroy()

@cmd
def clear_web():
	import frappe.website.render
	frappe.connect()
	frappe.website.render.clear_cache()
	frappe.destroy()

@cmd
def clear_all_sessions():
	import frappe.sessions
	frappe.connect()
	frappe.sessions.clear_all_sessions()
	frappe.db.commit()
	frappe.destroy()

@cmd
def build_website(verbose=False):
	from frappe.website import render, statics
	frappe.connect()
	render.clear_cache()
	statics.sync(verbose=verbose).start(True)
	frappe.db.commit()
	frappe.destroy()

@cmd
def sync_statics(force=False):
	from frappe.website import statics
	frappe.connect()
	statics.sync_statics(rebuild = force)
	frappe.db.commit()
	frappe.destroy()

@cmd
def reset_perms():
	frappe.connect()
	for d in frappe.db.sql_list("""select name from `tabDocType`
		where ifnull(istable, 0)=0 and ifnull(custom, 0)=0"""):
			frappe.clear_cache(doctype=d)
			frappe.reset_perms(d)
	frappe.destroy()

@cmd
def execute(method):
	frappe.connect()
	ret = frappe.get_attr(method)()
	frappe.db.commit()
	frappe.destroy()
	if ret:
		print ret

@cmd
def celery(arg):
	import frappe
	import commands, os
	python = commands.getoutput('which python')
	os.execv(python, [python, "-m", "frappe.celery_app"] + arg.split())
	frappe.destroy()

@cmd
def run_scheduler_event(event, force=False):
	import frappe.utils.scheduler
	frappe.connect()
	frappe.utils.scheduler.trigger(frappe.local.site, event, now=force)
	frappe.destroy()

@cmd
def enable_scheduler():
	import frappe.utils.scheduler
	frappe.connect()
	frappe.utils.scheduler.enable_scheduler()
	frappe.db.commit()
	print "Enabled"
	frappe.destroy()

@cmd
def disable_scheduler():
	import frappe.utils.scheduler
	frappe.connect()
	frappe.utils.scheduler.disable_scheduler()
	frappe.db.commit()
	print "Disabled"
	frappe.destroy()

# replace
@cmd
def replace(search_regex, replacement, extn, force=False):
	print search_regex, replacement, extn
	replace_code('.', search_regex, replacement, extn, force=force)

# import/export
@cmd
def export_doc(doctype, docname):
	import frappe.modules
	frappe.connect()
	frappe.modules.export_doc(doctype, docname)
	frappe.destroy()

@cmd
def export_doclist(doctype, name, path):
	from frappe.core.page.data_import_tool import data_import_tool
	frappe.connect()
	data_import_tool.export_json(doctype, name, path)
	frappe.destroy()

@cmd
def export_csv(doctype, path):
	from frappe.core.page.data_import_tool import data_import_tool
	frappe.connect()
	data_import_tool.export_csv(doctype, path)
	frappe.destroy()

@cmd
def export_fixtures():
	from frappe.utils.fixtures import export_fixtures
	frappe.connect()
	export_fixtures()
	frappe.destroy()

@cmd
def import_doc(path, force=False):
	from frappe.core.page.data_import_tool import data_import_tool
	frappe.connect()
	data_import_tool.import_doc(path, overwrite=force)
	frappe.destroy()

# translation
@cmd
def build_message_files():
	import frappe.translate
	frappe.connect()
	frappe.translate.rebuild_all_translation_files()
	frappe.destroy()

@cmd
def get_untranslated(lang, untranslated_file, all=None):
	import frappe.translate
	frappe.connect()
	frappe.translate.get_untranslated(lang, untranslated_file, get_all=all)
	frappe.destroy()

@cmd
def update_translations(lang, untranslated_file, translated_file):
	import frappe.translate
	frappe.connect()
	frappe.translate.update_translations(lang, untranslated_file, translated_file)
	frappe.destroy()

# git
@cmd
def git(param):
	if isinstance(param, (list, tuple)):
		param = " ".join(param)
	import os
	os.system("""cd lib && git %s""" % param)
	os.system("""cd app && git %s""" % param)

def get_remote_and_branch(remote=None, branch=None):
	if not (remote and branch):
		if not frappe.conf.branch:
			raise Exception("Please specify remote and branch")

		remote = remote or "origin"
		branch = branch or frappe.conf.branch
		frappe.destroy()

	return remote, branch

@cmd
def pull(remote=None, branch=None):
	remote, branch = get_remote_and_branch(remote, branch)
	git(("pull", remote, branch))

@cmd
def push(remote=None, branch=None):
	remote, branch = get_remote_and_branch(remote, branch)
	git(("push", remote, branch))

@cmd
def status():
	git("status")

@cmd
def commit(message):
	git("""commit -a -m "%s" """ % message.replace('"', '\"'))

@cmd
def checkout(branch):
	git(("checkout", branch))

@cmd
def set_admin_password(admin_password=None):
	import frappe
	import getpass

	while not admin_password:
		admin_password = getpass.getpass("Administrator's password: ")

	frappe.connect()
	frappe.db.sql("""update __Auth set `password`=password(%s)
		where user='Administrator'""", (admin_password,))
	frappe.db.commit()
	frappe.destroy()

@cmd
def mysql():
	import frappe
	import commands, os
	msq = commands.getoutput('which mysql')
	os.execv(msq, [msq, '-u', frappe.conf.db_name, '-p'+frappe.conf.db_password, frappe.conf.db_name, '-h', frappe.conf.db_host or "localhost", "-A"])
	frappe.destroy()

@cmd
def python(site):
	import frappe
	import commands, os
	python = commands.getoutput('which python')
	if site:
		os.environ["site"] = site
	os.environ["PYTHONSTARTUP"] = os.path.join(os.path.dirname(frappe.__file__), "pythonrc.py")
	os.execv(python, [python])
	frappe.destroy()

@cmd
def ipython(site):
	import frappe
	frappe.connect(site=site)
	import IPython
	IPython.embed()

@cmd
def smtp_debug_server():
	import commands, os
	python = commands.getoutput('which python')
	os.execv(python, [python, '-m', "smtpd", "-n", "-c", "DebuggingServer", "localhost:25"])

@cmd
def run_tests(app=None, module=None, doctype=None, verbose=False, tests=(), driver=None, force=False):
	import frappe.test_runner
	from frappe.utils import sel

	sel.start(verbose, driver)

	ret = 1
	try:
		ret = frappe.test_runner.main(app and app[0], module and module[0], doctype and doctype[0], verbose,
			tests=tests, force=force)
		if len(ret.failures) == 0 and len(ret.errors) == 0:
			ret = 0
	finally:
		sel.close()

	return ret

@cmd
def serve(port=None, profile=False, sites_path='.', site=None):
	if not port: port = 8000

	import frappe.app
	frappe.app.serve(port=port, profile=profile, site=frappe.local.site, sites_path=sites_path)

@cmd
def serve_test(port=None, profile=False, sites_path='.', site=None):
	from frappe.utils import sel
	if not port: port = sel.port
	serve(port)

@cmd
def request(args):
	import frappe.handler
	import frappe.api
	frappe.connect()
	if "?" in args:
		frappe.local.form_dict = frappe._dict([a.split("=") for a in args.split("?")[-1].split("&")])
	else:
		frappe.local.form_dict = frappe._dict()

	if args.startswith("/api/method"):
		frappe.local.form_dict.cmd = args.split("?")[0].split("/")[-1]

	frappe.handler.execute_cmd(frappe.form_dict.cmd)

	print frappe.response
	frappe.destroy()

@cmd
def resize_images(path):
	import frappe.utils.image
	frappe.utils.image.resize_images(path)

@cmd
def flush_memcache():
	frappe.cache().flush_all()


def replace_code(start, txt1, txt2, extn, search=None, force=False):
	"""replace all txt1 by txt2 in files with extension (extn)"""
	import frappe.utils
	import os, re
	esc = frappe.utils.make_esc('[]')
	if not search: search = esc(txt1)
	for wt in os.walk(start, followlinks=1):
		for fn in wt[2]:
			if fn.split('.')[-1]==extn:
				fpath = os.path.join(wt[0], fn)
				with open(fpath, 'r') as f:
					content = f.read()

				if re.search(search, content):
					res = search_replace_with_prompt(fpath, txt1, txt2, force)
					if res == 'skip':
						return 'skip'


def search_replace_with_prompt(fpath, txt1, txt2, force=False):
	""" Search and replace all txt1 by txt2 in the file with confirmation"""
	from termcolor import colored
	with open(fpath, 'r') as f:
		content = f.readlines()

	tmp = []
	for c in content:
		if c.find(txt1) != -1:
			print fpath
			print  colored(txt1, 'red').join(c[:-1].split(txt1))
			a = ''
			if force:
				c = c.replace(txt1, txt2)
			else:
				while a.lower() not in ['y', 'n', 'skip']:
					a = raw_input('Do you want to Change [y/n/skip]?')
				if a.lower() == 'y':
					c = c.replace(txt1, txt2)
				elif a.lower() == 'skip':
					return 'skip'
		tmp.append(c)

	with open(fpath, 'w') as f:
		f.write(''.join(tmp))
	print colored('Updated', 'green')

@cmd
def get_site_status(verbose=False):
	import frappe
	import frappe.utils
	from frappe.utils.user import get_system_managers
	from frappe.core.doctype.user.user import get_total_users, get_active_users, \
		get_website_users, get_active_website_users

	import json
	frappe.connect()
	ret = {
		'last_backup_on': frappe.local.conf.last_backup_on,
		'active_users': get_active_users(),
		'total_users': get_total_users(),
		'active_website_users': get_active_website_users(),
		'website_users': get_website_users(),
		'system_managers': "\n".join(get_system_managers()),
		'default_company': frappe.db.get_default("company"),
		'disk_usage': frappe.utils.get_disk_usage(),
		'working_directory': frappe.local.site_path
	}

	# country, timezone, industry
	for key in ["country", "time_zone", "industry"]:
		ret[key] = frappe.db.get_default(key)

	# basic usage/progress analytics
	for doctype in ("Company", "Customer", "Item", "Quotation", "Sales Invoice",
		"Journal Voucher", "Stock Ledger Entry"):
			key = doctype.lower().replace(" ", "_") + "_exists"
			ret[key] = 1 if frappe.db.count(doctype) else 0

	frappe.destroy()

	if verbose:
		print json.dumps(ret, indent=1, sort_keys=True)

	return ret

@cmd
def update_site_config(site_config, verbose=False):
	import json

	if isinstance(site_config, basestring):
		site_config = json.loads(site_config)

	config = frappe.get_site_config()
	config.update(site_config)
	site_config_path = os.path.join(frappe.local.site_path, "site_config.json")

	with open(site_config_path, "w") as f:
		json.dump(config, f, indent=1, sort_keys=True)

	frappe.destroy()

@cmd
def bump(repo, bump_type):

	import json
	assert repo in ['lib', 'app']
	assert bump_type in ['minor', 'major', 'patch']

	def validate(repo_path):
		import git
		repo = git.Repo(repo_path)
		if repo.active_branch != 'master':
			raise Exception, "Current branch not master in {}".format(repo_path)

	def bump_version(version, version_type):
		import semantic_version
		v = semantic_version.Version(version)
		if version_type == 'minor':
			v.minor += 1
		elif version_type == 'major':
			v.major += 1
		elif version_type == 'patch':
			v.patch += 1
		return unicode(v)

	def add_tag(repo_path, version):
		import git
		repo = git.Repo(repo_path)
		repo.index.add(['config.json'])
		repo.index.commit('bumped to version {}'.format(version))
		repo.create_tag('v' + version, repo.head)

	def update_framework_requirement(version):
		with open('app/config.json') as f:
			config = json.load(f)
		config['requires_framework_version'] = '==' + version
		with open('app/config.json', 'w') as f:
			json.dump(config, f, indent=1, sort_keys=True)

	validate('lib/')
	validate('app/')

	if repo == 'app':
		with open('app/config.json') as f:
			config = json.load(f)
		new_version = bump_version(config['app_version'], bump_type)
		config['app_version'] = new_version
		with open('app/config.json', 'w') as f:
			json.dump(config, f, indent=1, sort_keys=True)
		add_tag('app/', new_version)

	elif repo == 'lib':
		with open('lib/config.json') as f:
			config = json.load(f)
		new_version = bump_version(config['framework_version'], bump_type)
		config['framework_version'] = new_version
		with open('lib/config.json', 'w') as f:
			json.dump(config, f, indent=1, sort_keys=True)
		add_tag('lib/', new_version)

		update_framework_requirement(new_version)

		bump('app', bump_type)


if __name__=="__main__":
	out = main()
	if out and out==1:
		exit(1)
