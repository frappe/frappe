#!/usr/bin/python

# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

import os, sys

def replace_code(start, txt1, txt2, extn, search=None):
	"""replace all txt1 by txt2 in files with extension (extn)"""
	import webnotes.utils
	import os, re
	esc = webnotes.utils.make_esc('[]')
	if not search: search = esc(txt1)
	for wt in os.walk(start, followlinks=1):
		for fn in wt[2]:
			if fn.split('.')[-1]==extn:
				fpath = os.path.join(wt[0], fn)
				if fpath != '/var/www/erpnext/erpnext/patches/jan_mar_2012/rename_dt.py': # temporary
					with open(fpath, 'r') as f:
						content = f.read()
				
					if re.search(search, content):
						res = search_replace_with_prompt(fpath, txt1, txt2)
						if res == 'skip':
							return 'skip'



def search_replace_with_prompt(fpath, txt1, txt2):
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
	
def pull(remote, branch):
	os.system('git pull %s %s' % (remote, branch))
	os.system('cd lib && git pull %s %s' % (remote, branch))
	
def apply_latest_patches():
	import webnotes.modules.patch_handler
	webnotes.modules.patch_handler.run_all()
	print '\n'.join(webnotes.modules.patch_handler.log_list)
	
def sync_all(force=0):
	import webnotes.model.sync
	webnotes.model.sync.sync_all(force)

def update_erpnext(remote='origin', branch='master'):
	# do a pull
	pull(remote, branch)
	
	# apply latest patches
	apply_latest_patches()
	
	import webnotes.modules.patch_handler
	for l in webnotes.modules.patch_handler.log_list:
		if "failed: STOPPED" in l:
			return
	
	# sync all
	sync_all()

def setup_options():
	from optparse import OptionParser
	parser = OptionParser()

	parser.add_option("-d", "--db",
						dest="db_name",
						help="Apply the patches on given db")
	parser.add_option("--password",
						help="Password for given db", nargs=1)

	# build
	parser.add_option("-b", "--build", default=False, action="store_true",
						help="minify + concat js files")
						
	parser.add_option("--build_web_cache", default=False, action="store_true",
						help="build web cache")

	parser.add_option("--domain", metavar="DOMAIN",
						help="store domain in Website Settings", nargs=1)

	# git
	parser.add_option("--status", default=False, action="store_true",
						help="git status")
	parser.add_option("--pull", nargs=2, default=False,
						metavar = "remote branch",
						help="git pull (both repos)")
	parser.add_option("--push", nargs=3, default=False, 
						metavar = "remote branch comment",
						help="git commit + push (both repos) [remote] [branch] [comment]")
	parser.add_option("--checkout", nargs=1, default=False, 
						metavar = "branch",
						help="git checkout [branch]")						
						
	parser.add_option("-l", "--latest",
						action="store_true", dest="run_latest", default=False,
						help="Apply the latest patches")

	# patch
	parser.add_option("-p", "--patch", nargs=1, dest="patch_list", metavar='patch_module',
						action="append",
						help="Apply patch")
	parser.add_option("-f", "--force",
						action="store_true", dest="force", default=False,
						help="Force Apply all patches specified using option -p or --patch")
	parser.add_option('--reload_doc', nargs=3, metavar = "module doctype docname",
						help="reload doc")
	parser.add_option('--export_doc', nargs=2, metavar = "doctype docname",
						help="export doc")

	# install
	parser.add_option('--install', nargs=2, metavar = "dbname source",
						help="install fresh db")
	
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
			
	parser.add_option("--update", help="Pull, run latest patches and sync all",
			nargs=2, metavar="ORIGIN BRANCH")
			
	parser.add_option("--cleanup_data", help="Cleanup test data", default=False, 	
			action="store_true")

	return parser.parse_args()
	
def run():
	sys.path.append('.')
	sys.path.append('lib/py')
	import webnotes
	import conf
	sys.path.append(conf.modules_path)

	(options, args) = setup_options()


	from webnotes.db import Database
	import webnotes.modules.patch_handler

	# connect
	if options.db_name is not None:
		if options.password:
			webnotes.connect(options.db_name, options.password)
		else:
			webnotes.connect(options.db_name)
	elif not any([options.install, options.pull]):
		webnotes.connect(conf.db_name)

	# build
	if options.build:
		import build.project
		build.project.build()	

	# code replace
	elif options.replace:
		print options.replace
		replace_code('.', options.replace[0], options.replace[1], options.replace[2])
	
	# git
	elif options.status:
		os.system('git status')
		os.chdir('lib')
		os.system('git status')
	
	elif options.pull:
		pull(options.pull[0], options.pull[1])

	elif options.push:
		os.system('git commit -a -m "%s"' % options.push[2])
		os.system('git push %s %s' % (options.push[0], options.push[1]))
		os.chdir('lib')
		os.system('git commit -a -m "%s"' % options.push[2])
		os.system('git push %s %s' % (options.push[0], options.push[1]))
		
	elif options.checkout:
		os.system('git checkout %s' % options.checkout)
		os.chdir('lib')
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
		inst.import_from_db(options.install[0], source_path=options.install[1], \
			password='admin', verbose = 1)
	
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
		import webnotes.model.sync
		webnotes.model.sync.sync(options.sync[0], options.sync[1], options.force or 0)
	
	elif options.update:
		update_erpnext(options.update[0], options.update[1])

	elif options.cleanup_data:
		from utilities import cleanup_data
		cleanup_data.run()
		
	elif options.domain:
		webnotes.conn.set_value('Website Settings', None, 'subdomain', options.domain)
		webnotes.conn.commit()
		print "Domain set to", options.domain
		
	elif options.build_web_cache:
		import website.web_cache
		website.web_cache.refresh_cache(True)

	# print messages
	if webnotes.message_log:
		print '\n'.join(webnotes.message_log)

if __name__=='__main__':
	run()
