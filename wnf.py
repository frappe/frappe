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
	sys.path.append('lib')
	sys.path.append('lib/py')
	import webnotes
	import webnotes.defs
	sys.path.append(webnotes.defs.modules_path)

	if len(sys.argv)<2:
		print_help()
		return

	cmd = sys.argv[1]

	if cmd=='watch':
		from py import build
		import time
		
		while True:
			build.run()

			vc = version.VersionControl()
			print 'version %s' % vc.repo.get_value('last_version_number')
			time.sleep(5)
			

	elif cmd=='build':
		from py.build.project import Project
		Project().build()
		
	# replace code
	elif cmd=='replace':
		replace_code('.', sys.argv[2], sys.argv[3], sys.argv[4])
		
	elif cmd=='patch':
		from optparse import OptionParser
		parser = OptionParser()
		parser.add_option("-q", "--quiet",
						  action="store_false", dest="verbose", default=True,
						  help="Do not print status messages to stdout")
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
		(options, args) = parser.parse_args()
		
		if options.patch_list:
			for patch in options.patch_list:
				patch_split = patch.split(".")
				idx = options.patch_list.index(patch)
				patch_module = ".".join(patch_split[:-1])
				options.patch_list[idx] = {
					'patch_module': patch_module or "patches",
					'patch_file': patch_split[-1]
				}
		kwargs = options.__dict__
		from webnotes.modules.patch_handler import PatchHandler
		PatchHandler(db_name=kwargs.get('db_name') or getattr(webnotes.defs, 'default_db_name'), verbose=kwargs.get('verbose')).run(**kwargs)		


if __name__=='__main__':
	run()
