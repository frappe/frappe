#!/usr/bin/env python

# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

from __future__ import unicode_literals
import os, sys

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
	
def pull(remote, branch, build=False):
	os.system('cd lib && git pull %s %s' % (remote, branch))
	os.system('cd app && git pull %s %s' % (remote, branch))
	if build: rebuild()
	
def rebuild():
	# build js / css
	from webnotes import build
	build.bundle(False)		
	
def apply_latest_patches():
	import webnotes.modules.patch_handler
	webnotes.modules.patch_handler.run_all()
	print '\n'.join(webnotes.modules.patch_handler.log_list)
	
def sync_all(force=0):
	import webnotes.model.sync
	webnotes.model.sync.sync_all(force)

def update_erpnext(remote='origin', branch='master'):
	pull(remote, branch)
	from webnotes.utils import execute_in_shell
	execute_in_shell("lib/wnf.py --patch_sync_build", verbose=1)
	
def patch_sync_build():
	patch_sync()
	rebuild()
	
def patch_sync():
	apply_latest_patches()
	
	import webnotes.modules.patch_handler
	for l in webnotes.modules.patch_handler.log_list:
		if "failed: STOPPED" in l:
			return
	
	sync_all()
	
	clear_cache()
	
def clear_cache():
	import webnotes.sessions
	webnotes.sessions.clear_cache()
	
def append_future_import():
	"""appends from __future__ import unicode_literals to py files if necessary"""
	import os
	import conf
	conf_path = os.path.abspath(conf.__file__)
	if conf_path.endswith("pyc"):
		conf_path = conf_path[:-1]
	
	base_path = os.path.dirname(conf_path)
	
	for path, folders, files in os.walk(base_path):
		for f in files:
			if f.endswith('.py'):
				file_path = os.path.join(path, f)
				with open(file_path, 'r') as pyfile:
					content = pyfile.read()
				future_import = 'from __future__ import unicode_literals'

				if future_import in content: continue

				content = content.split('\n')
				idx = -1
				for c in content:
					idx += 1
					if c and not c.startswith('#'):
						break
				content.insert(idx, future_import)
				content = "\n".join(content)
				with open(file_path, 'w') as pyfile:
					pyfile.write(content)

def setup_options():
	from optparse import OptionParser
	parser = OptionParser()

	# install
	parser.add_option('--install', nargs=2, metavar = "NEW_DB_NAME SOURCE_PATH",
						help="install db")

	parser.add_option('--install_fresh', nargs=1, metavar = "NEW_DB_NAME",
						help="install fresh db")

	parser.add_option('--make_demo', default=False, action="store_true",
						help="install in database 'demo'")

	# update
	parser.add_option("-u", "--update", 
		help="Pull, run latest patches and sync all",
		default=False, action="store_true", metavar="ORIGIN BRANCH")

	parser.add_option("--backup", help="Takes backup of database in backup folder",
		default=False, action="store_true")

	# build
	parser.add_option("-b", "--build", default=False, action="store_true",
						help="minify + concat js files")
	parser.add_option("-w", "--watch", default=False, action="store_true",
						help="watch and minify + concat js files, if necessary")
	parser.add_option("--no_cms", default=False, action="store_true",
						help="do not build wn-web.js and wn-css.js")

	parser.add_option("--docs", default=False, action="store_true",
						help="Build docs")


	parser.add_option("-d", "--db",
						dest="db_name",
						help="Apply the patches on given db")
	parser.add_option("--password",
						help="Password for given db", nargs=1)
						
	parser.add_option("--clear_web", default=False, action="store_true",
						help="clear web cache")
	parser.add_option("--clear_cache", default=False, action="store_true",
						help="clear cache")
	parser.add_option("--clear_defaults", default=False, action="store_true",
						help="clear cache of defaults")

	parser.add_option("--domain", metavar="DOMAIN",
						help="store domain in Website Settings", nargs=1)

	# git
	parser.add_option("--status", default=False, action="store_true",
						help="git status")
	parser.add_option("--git", nargs=1, default=False, 
						metavar = "git options",
						help="run git with options in both repos")
	parser.add_option("--pull", nargs=2, default=False,
						metavar = "remote branch",
						help="git pull (both repos)")

	parser.add_option("-c", "--commit", nargs=1, default=False, 
						metavar = "commit both repos",
						help="git commit -a -m [comment]")
	parser.add_option("-p", "--push", default=False, 
						action="store_true",
						metavar = "remote branch",
						help="git push (both repos) [remote] [branch]")
	parser.add_option("--checkout", nargs=1, default=False, 
						metavar = "branch",
						help="git checkout [branch]")						
						
	parser.add_option("-l", "--latest",
						action="store_true", dest="run_latest", default=False,
						help="Apply the latest patches")

	# patch
	parser.add_option("--patch", nargs=1, dest="patch_list",
		metavar='patch_module',
		action="append",
		help="Apply patch")
	parser.add_option("-f", "--force",
						action="store_true", dest="force", default=False,
						help="Force Apply all patches specified using option -p or --patch")
	parser.add_option('--reload_doc', nargs=3, metavar = "module doctype docname",
						help="reload doc")
	parser.add_option('--export_doc', nargs=2, metavar = "doctype docname",
						help="export doc")

	
	# diff
	parser.add_option('--diff_ref_file', nargs=0, \
						help="Get missing database records and mismatch properties, with file as reference")
	parser.add_option('--diff_ref_db', nargs=0, \
						help="Get missing .txt files and mismatch properties, with database as reference")

	# scheduler
	parser.add_option('--run_scheduler', default=False, action="store_true",
						help="Trigger scheduler")
	parser.add_option('--run_scheduler_event', nargs=1, metavar="[all|daily|weekly|monthly]",
						help="Run scheduler event")

	# misc
	parser.add_option("--replace", nargs=3, default=False, 
						metavar = "search replace_by extension",
						help="file search-replace")
	
	parser.add_option("--sync_all", help="Synchronize all DocTypes using txt files",
			nargs=0)
	
	parser.add_option("--sync", help="Synchronize given DocType using txt file",
			nargs=2, metavar="module doctype (use their folder names)")
			
	parser.add_option("--patch_sync_build", action="store_true", default=False,
		help="run latest patches, sync all and rebuild js css")

	parser.add_option("--patch_sync", action="store_true", default=False,
		help="run latest patches, sync all")
			
	parser.add_option("--cleanup_data", help="Cleanup test data", default=False, 	
			action="store_true")

	parser.add_option("--append_future_import", default=False, action="store_true", 
			help="append from __future__ import unicode literals to py files")
			
	parser.add_option("--build_message_files", default=False, action="store_true",
		help="Build message files for translation")
		
	parser.add_option('--export_messages', nargs=2, metavar="LANG FILENAME", 
		help="""Export all messages for a language to translation in a csv file. 
		Example, lib/wnf.py --export_messages hi hindi.csv""")

	parser.add_option('--import_messages', nargs=2, metavar="LANG FILENAME", 
		help="""Import messages for a language and make language files. 
		Example, lib/wnf.py --import_messages hi hindi.csv""")

	parser.add_option('--google_translate', nargs=3, metavar="LANG INFILE OUTFILE", 
		help="""Auto translate using Google Translate API""")

	parser.add_option('--translate', nargs=1, metavar="LANG", 
		help="""Rebuild translation for the given langauge and 
		use Google Translate to tranlate untranslated messages. use "all" """)
		
	parser.add_option("--reset_perms", default=False, action="store_true",
		help="Reset permissions for all doctypes.")

	return parser.parse_args()
	
def run():
	sys.path.append('.')
	sys.path.append('lib')
	sys.path.append('app')

	(options, args) = setup_options()
	
	# build
	if options.build:
		from webnotes import build
		if options.no_cms:
			cms_make = False
		else:
			cms_make = True
		build.bundle(False, cms_make)
		return
		
	elif options.watch:
		from webnotes import build
		build.watch(True)
		return

	# code replace
	elif options.replace:
		print options.replace
		replace_code('.', options.replace[0], options.replace[1], options.replace[2], force=options.force)
		return
	
	# git
	elif options.status:
		os.chdir('lib')
		os.system('git status')
		os.chdir('../app')
		os.system('git status')
		return

	elif options.git:
		os.chdir('lib')
		os.system('git %s' % options.git)
		os.chdir('../app')
		os.system('git %s' % options.git)
		return
		
	import webnotes
	import conf
	from webnotes.db import Database
	import webnotes.modules.patch_handler
	webnotes.print_messages = True
	
	# connect
	if options.db_name is not None:
		if options.password:
			webnotes.connect(options.db_name, options.password)
		else:
			webnotes.connect(options.db_name)
	elif not any([options.install, options.pull, options.install_fresh]):
		webnotes.connect(conf.db_name)

	if options.pull:
		pull(options.pull[0], options.pull[1], build=True)

	elif options.commit:
		os.chdir('lib')
		os.system('git commit -a -m "%s"' % (options.commit))
		os.chdir('../app')
		os.system('git commit -a -m "%s"' % (options.commit))

	elif options.push:
		if not args:
			args = ["origin", conf.branch]
		
		os.chdir('lib')
		os.system('git push %s %s' % (args[0], args[1]))
		os.chdir('../app')
		os.system('git push %s %s' % (args[0], args[1]))
				
	elif options.checkout:
		os.chdir('lib')
		os.system('git checkout %s' % options.checkout)
		os.chdir('../app')
		os.system('git checkout %s' % options.checkout)
			
	# patch
	elif options.patch_list:
		# clear log
		webnotes.modules.patch_handler.log_list = []
		
		# run individual patches
		for patch in options.patch_list:
			webnotes.modules.patch_handler.run_single(\
				patchmodule = patch, force = options.force)
		
		print '\n'.join(webnotes.modules.patch_handler.log_list)
	
		# reload
	elif options.reload_doc:
		webnotes.modules.patch_handler.reload_doc(\
			{"module":options.reload_doc[0], "dt":options.reload_doc[1], "dn":options.reload_doc[2]})		
		print '\n'.join(webnotes.modules.patch_handler.log_list)

	elif options.export_doc:
		from webnotes.modules import export_doc
		export_doc(options.export_doc[0], options.export_doc[1])

	# run all pending
	elif options.run_latest:
		apply_latest_patches()
	
	elif options.install:
		from webnotes.install_lib.install import Installer
		inst = Installer('root')
		inst.import_from_db(options.install[0], source_path=options.install[1],
			verbose = 1)

	elif options.install_fresh:
		from webnotes.install_lib.install import Installer
		inst = Installer('root')
		inst.import_from_db(options.install_fresh, verbose = 1)

	elif options.make_demo:
		import utilities.make_demo
		utilities.make_demo.make()

	elif options.diff_ref_file is not None:
		import webnotes.modules.diff
		webnotes.modules.diff.diff_ref_file()

	elif options.diff_ref_db is not None:
		import webnotes.modules.diff
		webnotes.modules.diff.diff_ref_db()
	
	elif options.run_scheduler:
		import webnotes.utils.scheduler
		print webnotes.utils.scheduler.execute()
	
	elif options.run_scheduler_event is not None:
		import webnotes.utils.scheduler
		print webnotes.utils.scheduler.trigger('execute_' + options.run_scheduler_event)
		
	elif options.sync_all is not None:
		sync_all(options.force or 0)

	elif options.sync is not None:
		webnotes.reload_doc(options.sync[0], "doctype", options.sync[1])
	
	elif options.update:
		if not args:
			args = ["origin", conf.branch]
			
		update_erpnext(args[0], args[1])
		
	elif options.patch_sync_build:
		patch_sync_build()
	
	elif options.patch_sync:
		patch_sync()

	elif options.cleanup_data:
		from utilities import cleanup_data
		cleanup_data.run()
		
	elif options.domain:
		webnotes.conn.set_value('Website Settings', None, 'subdomain', options.domain)
		webnotes.conn.commit()
		print "Domain set to", options.domain
		
	elif options.clear_web:
		# build wn-web.js and wn-web.css
		from website.helpers.make_web_include_files import make
		make()
	
		import webnotes.webutils
		webnotes.webutils.clear_cache()
		
	elif options.clear_cache:
		clear_cache()
		
	elif options.clear_defaults:
		import webnotes.defaults
		webnotes.defaults.clear_cache()
		webnotes.clear_cache()
		
	elif options.append_future_import:
		append_future_import()

	elif options.backup:
		from webnotes.utils.backups import scheduled_backup
		scheduled_backup(ignore_files = True)
		
	# print messages
	if webnotes.message_log:
		print '\n'.join(webnotes.message_log)
		
	elif options.build_message_files:
		import webnotes.translate
		webnotes.translate.build_message_files()
		
	elif options.export_messages:
		import webnotes.translate
		webnotes.translate.export_messages(*options.export_messages)

	elif options.import_messages:
		import webnotes.translate
		webnotes.translate.import_messages(*options.import_messages)
	
	elif options.google_translate:
		from webnotes.translate import google_translate
		google_translate(*options.google_translate)
	
	elif options.translate:
		from webnotes.translate import translate
		translate(options.translate)
		
	elif options.docs:
		from core.doctype.documentation_tool.documentation_tool import write_static
		write_static()

	elif options.reset_perms:
		for d in webnotes.conn.sql_list("""select name from `tabDocType`
			where ifnull(istable, 0)=0 and ifnull(custom, 0)=0"""):
				try:
					webnotes.clear_cache(doctype=d)
					webnotes.reset_perms(d)
				except:
					pass
		

if __name__=='__main__':
	run()
