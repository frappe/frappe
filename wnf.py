#!/usr/bin/env python

import os, sys

def print_help():
	print "wnframework version control utility"
	print
	print "Usage:"
	print "python lib/wnf.py build : scan all folders and commit versions with latest changes"
	print "python lib/wnf.py pull : pull from git"
	print "python lib/wnf.py replace txt1 txt2 extn"
	print "python lib/wnf.py patch patch1 .. : run patches from patches module if not executed"
	print "python lib/wnf.py patch -f patch1 .. : run patches from patches module, force rerun"

"""simple replacement script"""

def replace_code(start, txt1, txt2, extn):
	"""replace all txt1 by txt2 in files with extension (extn)"""
	import os, re
	for wt in os.walk(start, followlinks=1):
		for fn in wt[2]:
			if fn.split('.')[-1]==extn:
				fpath = os.path.join(wt[0], fn)
				with open(fpath, 'r') as f:
					content = f.read()
				
				if re.search(txt1, content):				
					with open(fpath, 'w') as f:
						f.write(re.sub(txt1, txt2, content))
				
					print 'updated in %s' % fpath

def run():
	sys.path.append('.')
	sys.path.append('lib/py')
	import webnotes
	import webnotes.defs

	if len(sys.argv)<2:
		print_help()
		return

	cmd = sys.argv[1]			

	if cmd=='build':
		from build.project import Project
		Project().build()
		
	# replace code
	elif cmd=='replace':
		replace_code('.', sys.argv[2], sys.argv[3], sys.argv[4])
		
	elif cmd=='patch':
		from optparse import OptionParser
		parser = OptionParser()
		parser.add_option("-l", "--latest",
						  action="store_true", dest="run_latest", default=False,
						  help="Apply the latest patches")
		parser.add_option("-p", "--patch", dest="patch_list", metavar='PATCH_MODULE.PATCH_FILE',
						  action="append",
						  help="Apply patch PATCH_MODULE.PATCH_FILE")
		parser.add_option("-f", "--force",
						  action="store_true", dest="force", default=False,
						  help="Force Apply all patches specified using option -p or --patch")
		parser.add_option("-d", "--db",
						  dest="db_name",
						  help="Apply the patches on given db")
		parser.add_option('-r', '--reload_doc',help="reload doc, requires module, dt, dn", nargs=3)
		(options, args) = parser.parse_args()

		from webnotes.db import Database
		import webnotes.modules.patch_handler

		# connect to db
		if options.db_name is not None:
			webnotes.connect(options.db_name)
		else:
			webnotes.connect()
		
		# run individual patches
		if options.patch_list:
			for patch in options.patch_list:
				webnotes.modules.patch_handler.run_single(\
					patchmodule = patch, force = options.force)
		
		# reload
		elif options.reload_doc:
			webnotes.modules.patch_handler.reload_doc(\
				{"module":args[0], "dt":args[1], "dn":args[2]})		

		# run all pending
		elif options.run_latest:
			webnotes.modules.patch_handler.run_all()
			
		print '\n'.join(webnotes.modules.patch_handler.log_list)

if __name__=='__main__':
	run()
