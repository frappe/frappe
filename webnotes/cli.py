#!/usr/bin/env python2.7

# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import sys

import webnotes

def main():
	parsed_args = webnotes._dict(vars(setup_parser()))
	fn = get_function(parsed_args)
	if not parsed_args.get("sites_path"):
		parsed_args["sites_path"] = "."
	if not parsed_args.get("site"):
		print "Site argument required"
		return
	if parsed_args.get("site")=="all":
		for site in get_sites():
			args = parsed_args.copy()
			args["site"] = site
			webnotes.init(site)
			run(fn, args)
	else:
		webnotes.init(parsed_args.get("site"))
		run(fn, parsed_args)

def cmd(fn):
	def new_fn(*args, **kwargs):
		import inspect
		fnargs, varargs, varkw, defaults = inspect.getargspec(fn)
		new_kwargs = {}
		for a in fnargs:
			if a in kwargs:
				new_kwargs[a] = kwargs.get(a)
		
		return fn(*args, **new_kwargs)
	
	return new_fn
	

def run(fn, args):
	if isinstance(args.get(fn), (list, tuple)):
		out = globals().get(fn)(*args.get(fn), **args)
	else:
		out = globals().get(fn)(**args)
	
	return out
		
def get_function(args):
	for fn, val in args.items():
		if (val or isinstance(val, list)) and globals().get(fn):
			return fn
	
def get_sites():
	import os
	import conf
	return [site for site in os.listdir(conf.sites_dir)
			if not os.path.islink(os.path.join(conf.sites_dir, site)) 
				and os.path.isdir(os.path.join(conf.sites_dir, site))]
	
def setup_parser():
	import argparse
	parser = argparse.ArgumentParser(description="Run webnotes utility functions")
	
	setup_install(parser)
	setup_utilities(parser)
	setup_translation(parser)
	setup_test(parser)
	
	parser.add_argument("site")
	
	# common
	parser.add_argument("-f", "--force", default=False, action="store_true",
		help="Force execution where applicable (look for [-f] in help)")
	parser.add_argument("-v", "--verbose", default=False, action="store_true", dest="verbose",
		help="Show verbose output where applicable")
		
	return parser.parse_args()
	
def setup_install(parser):
	parser.add_argument("--install", metavar="DB-NAME", nargs=1,
		help="Install a new db")
	parser.add_argument("--install_app", metavar="APP-NAME", nargs=1,
		help="Install a new app")
	parser.add_argument("--root-password", nargs=1,
		help="Root password for new app")
	parser.add_argument("--reinstall", default=False, action="store_true", 
		help="Install a fresh app in db_name specified in conf.py")
	parser.add_argument("--restore", metavar=("DB-NAME", "SQL-FILE"), nargs=2,
		help="Restore from an sql file")
	parser.add_argument("--make_demo", default=False, action="store_true",
		help="Install demo in demo_db_name specified in conf.py")
	parser.add_argument("--make_demo_fresh", default=False, action="store_true",
		help="(Re)Install demo in demo_db_name specified in conf.py")
	parser.add_argument("--add_system_manager", nargs="+", 
		metavar=("EMAIL", "[FIRST-NAME] [LAST-NAME]"), help="Add a user with all roles")

def setup_test(parser):
	parser.add_argument("--run_tests", default=False, action="store_true",
		help="Run tests options [-d doctype], [-m module]")
	parser.add_argument("--app", metavar="APP-NAME", nargs=1,
		help="Run command for specified app")
	parser.add_argument("--doctype", metavar="DOCTYPE", nargs=1,
		help="Run command for specified doctype")
	parser.add_argument("--module", metavar="MODULE", nargs=1,
		help="Run command for specified module")

def setup_utilities(parser):
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
		help="Create new conf.py file")
	parser.add_argument("--set_admin_password", metavar='ADMIN-PASSWORD', nargs=1,
		help="Set administrator password")
	parser.add_argument("--mysql", action="store_true", help="get mysql shell for a site")
	parser.add_argument("--serve", action="store_true", help="Run development server")
	parser.add_argument("--profile", action="store_true", help="enable profiling in development server")
	parser.add_argument("--smtp", action="store_true", help="Run smtp debug server",
		dest="smtp_debug_server")
	parser.add_argument("--python", action="store_true", help="get python shell for a site")
	parser.add_argument("--ipython", action="store_true", help="get ipython shell for a site")
	parser.add_argument("--get_site_status", action="store_true", help="Get site details")
	parser.add_argument("--update_site_config", nargs=1, 
		metavar="site-CONFIG-JSON", 
		help="Update site_config.json for a given site")
	parser.add_argument("--port", default=8000, type=int, help="port for development server")
	
	# clear
	parser.add_argument("--clear_web", default=False, action="store_true",
		help="Clear website cache")
	parser.add_argument("--build_sitemap", default=False, action="store_true",
		help="Build Website Sitemap")
	parser.add_argument("--clear_cache", default=False, action="store_true",
		help="Clear cache, doctype cache and defaults")
	parser.add_argument("--reset_perms", default=False, action="store_true",
		help="Reset permissions for all doctypes")
	
	# scheduler
	parser.add_argument("--run_scheduler", default=False, action="store_true",
		help="Trigger scheduler")
	parser.add_argument("--run_scheduler_event", nargs=1, 
		metavar="all | daily | weekly | monthly",
		help="Run a scheduler event")
		
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
	parser.add_argument("--import_doclist", nargs=1, metavar="PATH", 
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

# install
@cmd
def install(db_name, root_login="root", root_password=None, source_sql=None,
	 admin_password = 'admin', verbose=True, force=False, site_config=None, reinstall=False):
	from webnotes.installer import install_db, install_app
	install_db(root_login=root_login, root_password=root_password, db_name=db_name, source_sql=source_sql,
		admin_password = admin_password, verbose=verbose, force=force, site_config=site_config, reinstall=reinstall)
	install_app("webnotes", verbose=verbose)
	webnotes.destroy()

@cmd
def install_app(app_name, verbose=False):
	from webnotes.installer import install_app
	webnotes.connect()
	install_app(app_name, verbose=verbose)
	webnotes.destroy()

@cmd
def reinstall(verbose=True):
	install(db_name=webnotes.conf.db_name, verbose=verbose, force=True, reinstall=True)

@cmd
def restore(db_name, source_sql, verbose=True, force=False):
	install(db_name, source_sql, verbose=verbose, force=force)

@cmd
def install_fixtures():
	from webnotes.install_lib.install import install_fixtures
	install_fixtures()
	webnotes.destroy()

@cmd
def add_system_manager(email, first_name=None, last_name=None):
	webnotes.connect()
	webnotes.profile.add_system_manager(email, first_name, last_name)
	webnotes.conn.commit()
	webnotes.destroy()

@cmd
def make_demo():
	import utilities.demo.make_demo
	utilities.demo.make_demo.make()
	webnotes.destroy()

@cmd
def make_demo_fresh():
	import utilities.demo.make_demo
	utilities.demo.make_demo.make(reset=True)
	webnotes.destroy()
	
# utilities

@cmd
def update(remote=None, branch=None, reload_gunicorn=False):
	pull(remote=remote, branch=branch)

	# maybe there are new framework changes, any consequences?
	reload(webnotes)
	build()
	latest()
	if reload_gunicorn:
		import subprocess
		subprocess.check_output("killall -HUP gunicorn".split())

@cmd
def latest(verbose=True):
	import webnotes.modules.patch_handler
	import webnotes.model.sync
	from webnotes.website import rebuild_config
	
	webnotes.connect()
	
	try:
		# run patches
		webnotes.local.patch_log_list = []
		webnotes.modules.patch_handler.run_all()
		if verbose:
			print "\n".join(webnotes.local.patch_log_list)
	
		# sync
		webnotes.model.sync.sync_all()
				
		# build website config if any changes in templates etc.
		rebuild_config()
		
	except webnotes.modules.patch_handler.PatchError, e:
		print "\n".join(webnotes.local.patch_log_list)
		raise
	finally:
		webnotes.destroy()

@cmd
def sync_all(force=False):
	import webnotes.model.sync
	webnotes.connect()
	webnotes.model.sync.sync_all(force=force)
	webnotes.destroy()

@cmd
def patch(patch_module, force=False):
	import webnotes.modules.patch_handler
	webnotes.connect()
	webnotes.local.patch_log_list = []
	webnotes.modules.patch_handler.run_single(patch_module, force=force)
	print "\n".join(webnotes.local.patch_log_list)
	webnotes.destroy()
	
@cmd
def update_all_sites(remote=None, branch=None, verbose=True):
	pull(remote, branch)
	
	# maybe there are new framework changes, any consequences?
	reload(webnotes)
	
	build()
	for site in get_sites():
		webnotes.init(site)
		latest(verbose=verbose)

@cmd
def reload_doc(module, doctype, docname, force=False):
	webnotes.connect()
	webnotes.reload_doc(module, doctype, docname, force=force)
	webnotes.conn.commit()
	webnotes.destroy()

@cmd
def build():
	import webnotes.build
	import webnotes
	webnotes.build.bundle(False)

@cmd
def watch():
	import webnotes.build
	webnotes.build.watch(True)

@cmd
def backup(with_files=False, verbose=True, backup_path_db=None, backup_path_files=None):
	from webnotes.utils.backups import scheduled_backup
	webnotes.connect()
	odb = scheduled_backup(ignore_files=not with_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files)
	if verbose:
		from webnotes.utils import now
		print "database backup taken -", odb.backup_path_db, "- on", now()
		if with_files:
			print "files backup taken -", odb.backup_path_files, "- on", now()
	webnotes.destroy()
	return odb

@cmd
def move(dest_dir=None):
	import os
	if not dest_dir:
		raise Exception, "--dest_dir is required for --move"
	if not os.path.isdir(dest_dir):
		raise Exception, "destination is not a directory or does not exist"

	old_path = webnotes.utils.get_site()
	new_path = os.path.join(dest_dir, site)

	# check if site dump of same name already exists
	site_dump_exists = True
	count = 0
	while site_dump_exists:
		final_new_path = new_path + (count and str(count) or "")
		site_dump_exists = os.path.exists(final_new_path)
		count = int(count or 0) + 1

	os.rename(old_path, final_new_path)
	webnotes.destroy()
	return os.path.basename(final_new_path)

@cmd
def domain(host_url=None):
	webnotes.connect()
	if host_url:
		webnotes.conn.set_value("Website Settings", None, "subdomain", host_url)
		webnotes.conn.commit()
	else:
		print webnotes.conn.get_value("Website Settings", None, "subdomain")
	webnotes.destroy()

@cmd
def make_conf(db_name=None, db_password=None, site_config=None):
	from webnotes.install_lib.install import make_conf
	make_conf(db_name=db_name, db_password=db_password, site_config=site_config)
	
@cmd
def make_custom_server_script(doctype):
	from webnotes.core.doctype.custom_script.custom_script import make_custom_server_script_file
	webnotes.connect()
	make_custom_server_script_file(doctype)
	webnotes.destroy()

# clear
@cmd
def clear_cache():
	import webnotes.sessions
	webnotes.connect()
	webnotes.clear_cache()
	webnotes.destroy()

@cmd
def clear_web():
	import webnotes.webutils
	webnotes.connect()
	webnotes.webutils.clear_cache()
	webnotes.destroy()

@cmd
def build_sitemap():
	from webnotes.website import rebuild_config
	webnotes.connect()
	rebuild_config()
	webnotes.destroy()
	
@cmd
def reset_perms():
	webnotes.connect()
	for d in webnotes.conn.sql_list("""select name from `tabDocType`
		where ifnull(istable, 0)=0 and ifnull(custom, 0)=0"""):
			webnotes.clear_cache(doctype=d)
			webnotes.reset_perms(d)
	webnotes.destroy()

# scheduler
@cmd
def run_scheduler():
	from webnotes.utils.file_lock import create_lock, delete_lock
	import webnotes.utils.scheduler
	if create_lock('scheduler'):
		webnotes.connect()
		print webnotes.utils.scheduler.execute()
		delete_lock('scheduler')
	webnotes.destroy()

@cmd
def run_scheduler_event(event):
	import webnotes.utils.scheduler
	webnotes.connect()
	print webnotes.utils.scheduler.trigger("execute_" + event)
	webnotes.destroy()
	
# replace
@cmd
def replace(search_regex, replacement, extn, force=False):
	print search_regex, replacement, extn
	replace_code('.', search_regex, replacement, extn, force=force)
	
# import/export	
@cmd
def export_doc(doctype, docname):
	import webnotes.modules
	webnotes.connect()
	webnotes.modules.export_doc(doctype, docname)
	webnotes.destroy()

@cmd
def export_doclist(doctype, name, path):
	from webnotes.core.page.data_import_tool import data_import_tool
	webnotes.connect()
	data_import_tool.export_json(doctype, name, path)
	webnotes.destroy()
	
@cmd
def export_csv(doctype, path):
	from webnotes.core.page.data_import_tool import data_import_tool
	webnotes.connect()
	data_import_tool.export_csv(doctype, path)
	webnotes.destroy()

@cmd
def import_doclist(path, force=False):
	from webnotes.core.page.data_import_tool import data_import_tool
	webnotes.connect()
	data_import_tool.import_doclist(path, overwrite=force)
	webnotes.destroy()
	
# translation
@cmd
def build_message_files():
	import webnotes.translate
	webnotes.connect()
	webnotes.translate.rebuild_all_translation_files()
	webnotes.destroy()

@cmd
def get_untranslated(lang, untranslated_file):
	import webnotes.translate
	webnotes.connect()
	webnotes.translate.get_untranslated(lang, untranslated_file)
	webnotes.destroy()

@cmd
def update_translations(lang, untranslated_file, translated_file):
	import webnotes.translate
	webnotes.connect()
	webnotes.translate.update_translations(lang, untranslated_file, translated_file)
	webnotes.destroy()

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
		if not webnotes.conf.branch:
			raise Exception("Please specify remote and branch")
			
		remote = remote or "origin"
		branch = branch or webnotes.conf.branch
		webnotes.destroy()
		
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
def set_admin_password(admin_password):
	import webnotes
	webnotes.connect()
	webnotes.conn.sql("""update __Auth set `password`=password(%s)
		where user='Administrator'""", (admin_password,))
	webnotes.conn.commit()
	webnotes.destroy()

@cmd
def mysql():
	import webnotes 
	import commands, os
	msq = commands.getoutput('which mysql')
	os.execv(msq, [msq, '-u', webnotes.conf.db_name, '-p'+webnotes.conf.db_password, webnotes.conf.db_name, '-h', webnotes.conf.db_host or "localhost", "-A"])
	webnotes.destroy()

@cmd
def python(site):
	import webnotes 
	import commands, os
	python = commands.getoutput('which python')
	if site:
		os.environ["site"] = site
	os.environ["PYTHONSTARTUP"] = os.path.join(os.path.dirname(webnotes.__file__), "pythonrc.py")
	os.execv(python, [python])
	webnotes.destroy()

@cmd
def ipython():
	import webnotes
	webnotes.connect()
	import IPython
	IPython.embed()

@cmd
def smtp_debug_server():
	import commands, os
	python = commands.getoutput('which python')
	os.execv(python, [python, '-m', "smtpd", "-n", "-c", "DebuggingServer", "localhost:25"])

@cmd
def run_tests(app=None, module=None, doctype=None, verbose=False):
	import webnotes.test_runner
	webnotes.test_runner.main(app and app[0], module and module[0], doctype and doctype[0], verbose)

@cmd
def serve(port=8000, profile=False):
	import webnotes.app
	webnotes.app.serve(port=port, profile=profile)

def replace_code(start, txt1, txt2, extn, search=None, force=False):
	"""replace all txt1 by txt2 in files with extension (extn)"""
	import webnotes.utils
	import os, re
	esc = webnotes.utils.make_esc('[]')
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
	import webnotes
	import webnotes.utils
	from webnotes.profile import get_system_managers
	from webnotes.core.doctype.profile.profile import get_total_users, get_active_users, \
		get_website_users, get_active_website_users
	
	import json
	webnotes.connect()
	ret = {
		'last_backup_on': webnotes.local.conf.last_backup_on,
		'active_users': get_active_users(),
		'total_users': get_total_users(),
		'active_website_users': get_active_website_users(),
		'website_users': get_website_users(),
		'system_managers': "\n".join(get_system_managers()),
		'default_company': webnotes.conn.get_default("company"),
		'disk_usage': webnotes.utils.get_disk_usage(),
		'working_directory': webnotes.utils.get_base_path()
	}
	
	# country, timezone, industry
	control_panel_details = webnotes.conn.get_value("Control Panel", "Control Panel", 
		["country", "time_zone", "industry"], as_dict=True)
	if control_panel_details:
		ret.update(control_panel_details)
	
	# basic usage/progress analytics
	for doctype in ("Company", "Customer", "Item", "Quotation", "Sales Invoice",
		"Journal Voucher", "Stock Ledger Entry"):
			key = doctype.lower().replace(" ", "_") + "_exists"
			ret[key] = 1 if webnotes.conn.count(doctype) else 0
			
	webnotes.destroy()
	
	if verbose:
		print json.dumps(ret, indent=1, sort_keys=True)
	
	return ret

@cmd
def update_site_config(site_config, verbose=False):
	import json
	
	if isinstance(site_config, basestring):
		site_config = json.loads(site_config)
	
	webnotes.conf.site_config.update(site_config)
	site_config_path = webnotes.get_conf_path(webnotes.conf.sites_dir)
	
	with open(site_config_path, "w") as f:
		json.dump(webnotes.conf.site_config, f, indent=1, sort_keys=True)
		
	webnotes.destroy()

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
	main()
