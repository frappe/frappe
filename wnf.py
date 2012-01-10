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
		from webnotes.modules.patch_handler import run
		if len(sys.argv)>2 and sys.argv[2]=='-f':
			# force patch
			run(patch_list = sys.argv[3:], overwrite=1, log_exception=0)
		else:
			# run patch once
			run(patch_list = sys.argv[2:], log_exception=0)

if __name__=='__main__':
	run()
