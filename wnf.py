#!/usr/bin/env python

# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

from __future__ import unicode_literals
import sys

if __name__=="__main__":
	sys.path = [".", "lib", "app"] + sys.path

import webnotes

def main():
	parsed_args = webnotes._dict(vars(setup_parser()))
	fn = get_function(parsed_args)
	if parsed_args.get("site")=="all":
		for site in get_sites():
			args = parsed_args.copy()
			args["site"] = site
			run(fn, args)
	else:
		run(fn, parsed_args)
		
def run(fn, args):
	out = globals().get(fn)(args.get(fn), args)
	webnotes.destroy()
	return out
		
def get_function(args):
	for fn, opts in args.items():
		if (opts or isinstance(opts, list)) and globals().get(fn):
			return fn
	
def get_sites():
	pass
	
def setup_parser():
	import argparse
	parser = argparse.ArgumentParser(description="Run webnotes utility functions")
	
	setup_install(parser)
	setup_utilities(parser)
	setup_translation(parser)
	setup_git(parser)
	
	# common
	parser.add_argument("-f", "--force", default=False, action="store_true",
		help="Force execution where applicable (look for [-f] in help)")
	parser.add_argument("--site", nargs="?", metavar="SITE-NAME or all",
		help="Run for a particular site")
		
	return parser.parse_args()
	
def setup_install(parser):
	parser.add_argument("--install", metavar="DB-NAME", nargs=1,
		help="Install a new app")
	parser.add_argument("--reinstall", default=False, action="store_true", 
		help="Install a fresh app in db_name specified in conf.py")
	parser.add_argument("--restore", metavar=("DB-NAME", "SQL-FILE"), nargs=2,
		help="Restore from an sql file")
	parser.add_argument("--install_fixtures", default=False, action="store_true", 
		help="(Re)Install install-fixtures from app/startup/install_fixtures")
	parser.add_argument("--make_demo", default=False, action="store_true",
		help="Install demo in demo_db_name specified in conf.py")
	parser.add_argument("--make_demo_fresh", default=False, action="store_true",
		help="(Re)Install demo in demo_db_name specified in conf.py")
		
def setup_utilities(parser):
	# update
	parser.add_argument("-u", "--update", nargs="*", metavar=("REMOTE", "BRANCH"),
		help="Perform git pull, run patches, sync schema and rebuild files/translations")
	parser.add_argument("--patch", nargs=1, metavar="PATCH-MODULE",
		help="Run a particular patch [-f]")
	parser.add_argument("-l", "--latest", default=False, action="store_true",
		help="Run patches, sync schema and rebuild files/translations")
	parser.add_argument("--sync_all", default=False, action="store_true",
		help="Reload all doctypes, pages, etc. using txt files [-f]")
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
	parser.add_argument("--with_files", default=False, action="store_true",
		help="Also take backup of files")
	parser.add_argument("--docs", default=False, action="store_true",
		help="Build docs")
	parser.add_argument("--domain", nargs="*",
		help="Get or set domain in Website Settings")
	parser.add_argument("--make_conf", nargs="*", metavar=("DB-NAME", "DB-PASSWORD"),
		help="Create new conf.py file")
	
	# clear
	parser.add_argument("--clear_web", default=False, action="store_true",
		help="Clear website cache")
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
		
def setup_git(parser):
	parser.add_argument("--pull", nargs="*", metavar=("REMOTE", "BRANCH"),
		help="Run git pull for both repositories")
	parser.add_argument("-p", "--push", nargs="*", metavar=("REMOTE", "BRANCH"),
		help="Run git push for both repositories")
	parser.add_argument("--status", default=False, action="store_true",
		help="Run git status for both repositories")
	parser.add_argument("--checkout", nargs=1, metavar="BRANCH",
		help="Run git checkout BRANCH for both repositories")
	parser.add_argument("--git", nargs="*", metavar="OPTIONS",
		help="Run git command for both repositories")
	
		
def setup_translation(parser):
	parser.add_argument("--build_message_files", default=False, action="store_true",
		help="Build message files for translation")
	parser.add_argument("--export_messages", nargs=2, metavar=("LANG-CODE", "FILENAME"),
		help="""Export all messages for a language to translation in a csv file. 
			Example, lib/wnf.py --export_messages hi hindi.csv""")
	parser.add_argument("--import_messages", nargs=2, metavar=("LANG-CODE", "FILENAME"),
		help="""Import messages for a language and make language files. 
			Example, lib/wnf.py --import_messages hi hindi.csv""")
	parser.add_argument("--google_translate", nargs=3, 
		metavar=("LANG-CODE", "INFILE", "OUTFILE"),
		help="Auto translate using Google Translate API")
	parser.add_argument("--translate", nargs=1, metavar="LANG-CODE",
		help="""Rebuild translation for the given langauge and 
			use Google Translate to tranlate untranslated messages. use "all" """)

# methods

# install
def _install(opts, args):
	from webnotes.install_lib.install import Installer
	inst = Installer('root', db_name=opts[0], site=args.site)
	inst.install(*opts, verbose=1, force=args.force)
	
def install(opts, args):
	_install(opts, args)

# install
def reinstall(opts, args):
	webnotes.init(site=args.site)
	_install([webnotes.conf.db_name], args)

def restore(opts, args):
	_install(opts, args)
	
def install_fixtures(opts, args):
	webnotes.init(site=args.site)
	from webnotes.install_lib.install import install_fixtures
	install_fixtures()
	
def make_demo(opts, args):
	import utilities.demo.make_demo
	webnotes.init(site=args.site)
	utilities.demo.make_demo.make()
	
def make_demo_fresh(opts, args):
	import utilities.demo.make_demo
	webnotes.init(site=args.site)
	utilities.demo.make_demo.make(reset=True)
	
# utilities
def update(opts, args):
	pull(opts, args)
	reload(webnotes)
	latest(opts, args)
	
def latest(opts, args):
	import webnotes.modules.patch_handler
	import webnotes.model.sync
	
	webnotes.connect(site=args.site)
	
	# run patches
	webnotes.modules.patch_handler.log_list = []
	webnotes.modules.patch_handler.run_all()
	print "\n".join(webnotes.modules.patch_handler.log_list)
	
	# sync
	webnotes.model.sync.sync_all()
	
	# build
	build(opts, args)
	
def sync_all(opts, args):
	import webnotes.model.sync
	webnotes.connect(site=args.site)
	webnotes.model.sync.sync_all(force=args.force)
	
def patch(opts, args):
	import webnotes.modules.patch_handler
	webnotes.connect(site=args.site)
	webnotes.modules.patch_handler.log_list = []
	webnotes.modules.patch_handler.run_single(opts[0], force=args.force)
	print "\n".join(webnotes.modules.patch_handler.log_list)

def reload_doc(opts, args):
	webnotes.connect(site=args.site)
	webnotes.reload_doc(opts[0], opts[1], opts[2], force=args.force)
	
def build(opts, args):
	import webnotes.build
	webnotes.build.bundle(False)
	
def watch(opts, args):
	import webnotes.build
	webnotes.build.watch(True)
	
def backup(opts, args):
	from webnotes.utils.backups import scheduled_backup
	webnotes.connect(site=args.site)
	scheduled_backup(ignore_files=not args.with_files)
	
def docs(opts, args):
	from core.doctype.documentation_tool.documentation_tool import write_static
	write_static()
	
def domain(opts, args):
	webnotes.connect(site=args.site)
	if opts:
		webnotes.conn.set_value("Website Settings", None, "subdomain", opts[0])
		webnotes.conn.commit()
	else:
		print webnotes.conn.get_value("Website Settings", None, "subdomain")
		
def make_conf(opts, args):
	from webnotes.install_lib.install import make_conf
	make_conf(*opts, site=args.site)

# clear
def clear_cache(opts, args):
	import webnotes.sessions
	webnotes.connect(site=args.site)
	webnotes.sessions.clear_cache()
	
def clear_web(opts, args):
	import webnotes.webutils
	webnotes.connect(site=args.site)
	webnotes.webutils.clear_cache()
	
def reset_perms(opts, args):
	webnotes.connect(site=args.site)
	for d in webnotes.conn.sql_list("""select name from `tabDocType`
		where ifnull(istable, 0)=0 and ifnull(custom, 0)=0"""):
			webnotes.clear_cache(doctype=d)
			webnotes.reset_perms(d)

# scheduler
def run_scheduler(opts, args):
	import webnotes.utils.scheduler
	webnotes.connect(site=args.site)
	print webnotes.utils.scheduler.execute()
	
def run_scheduler_event(opts, args):
	import webnotes.utils.scheduler
	webnotes.connect(site=args.site)
	print webnotes.utils.scheduler.trigger("execute_" + opts[0])
	
# replace
def replace(opts, args):
	print opts
	replace_code('.', *opts, force=args.force)
	
# import/export	
def export_doc(opts, args):
	import webnotes.modules
	webnotes.connect(site=args.site)
	webnotes.modules.export_doc(*opts)
	
def export_doclist(opts, args):
	from core.page.data_import_tool import data_import_tool
	webnotes.connect(site=args.site)
	data_import_tool.export_json(*opts)
	
def export_csv(opts, args):
	from core.page.data_import_tool import data_import_tool
	webnotes.connect(site=args.site)
	data_import_tool.export_csv(*opts)
	
def import_doclist(opts, args):
	from core.page.data_import_tool import data_import_tool
	webnotes.connect(site=args.site)
	data_import_tool.import_doclist(*opts)
	
# translation
def build_message_files(opts, args):
	import webnotes.translate
	webnotes.connect(site=args.site)
	webnotes.translate.build_message_files()
	
def export_messages(opts, args):
	import webnotes.translate
	webnotes.connect(site=args.site)
	webnotes.translate.export_messages(*opts)

def import_messages(opts, args):
	import webnotes.translate
	webnotes.connect(site=args.site)
	webnotes.translate.import_messages(*opts)
	
def google_translate(opts, args):
	import webnotes.translate
	webnotes.connect(site=args.site)
	webnotes.translate.google_translate(*opts)

def translate(opts, args):
	import webnotes.translate
	webnotes.connect(site=args.site)
	webnotes.translate.translate(*opts)

# git
def git(opts, args=None):
	cmd = opts
	if isinstance(opts, (list, tuple)):
		cmd = " ".join(opts)
	import os
	os.system("cd lib && git %s" % cmd)
	os.system("cd app && git %s" % cmd)
	
def pull(opts, args=None):
	if not opts:
		webnotes.init(site=args.site)
		opts = ("origin", webnotes.conf.branch or "master")
	git(("pull", opts[0], opts[1]))

def push(opts, args=None):
	if not opts:
		webnotes.init(site=args.site)
		opts = ("origin", webnotes.conf.branch or "master")
	git(("push", opts[0], opts[1]))
	
def status(opts, args=None):
	git("status")
	
def checkout(opts, args=None):
	git(("checkout", opts[0]))

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
	
if __name__=="__main__":
	main()