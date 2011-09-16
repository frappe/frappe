#!/usr/bin/env python

import os, sys

from py.build import version
version.verbose = True

def print_help():
	print "wnframework version control utility"
	print
	print "Usage:"
	print "python lib/wnf.py build : scan all folders and commit versions with latest changes"
	print "python lib/wnf.py setup : setup the local system (from master or fresh)"
	print "python lib/wnf.py merge : merge from local into master"
	print "python lib/wnf.py log : list last 10 commits"
	print "python lib/wnf.py pull : pull from git"

def setup():
	import os, sys
	
	if not os.path.exists('versions-local.db'):
		if os.path.exists('versions-master.db'):
			import shutil
			shutil.copyfile('versions-master.db', 'versions-local.db')
			print "created versions-local.db from versions-master.db"
		else:
			vc = version.VersionControl()
			vc.repo.setup()
			vc.close()
			print "created fresh versions-local.db"
	else:
		if len(sys.argv)==3 and sys.argv[2]=='master':
			import shutil
			shutil.copyfile('versions-local.db', 'versions-master.db')
			print "created versions-master.db from versions-local.db"
		else:
			print "versions-local.db already exists. Nothing to do."
def run():
	sys.path.append('lib')
	sys.path.append('lib/py')

	if len(sys.argv)<2:
		print_help()
		return

	cmd = sys.argv[1]

	if cmd=='build':
		from py import build
		build.run()

		vc = version.VersionControl()
		print 'version %s' % vc.repo.get_value('last_version_number')
				
	elif cmd=='merge':
		vc = version.VersionControl()
		vc.setup_master()
		vc.merge(vc.repo, vc.master)
		vc.close()

	elif cmd=='merge-local':
		vc = version.VersionControl()
		vc.setup_master()
		vc.merge(vc.master, vc.repo)
		vc.close()

	elif cmd=='setup':
		setup()
		
	elif cmd=='clear_startup':
		# experimental
		from webnotes import startup
		startup.clear_info('all')

		vc = version.VersionControl()
		print 'version %s' % vc.repo.get_value('last_version_number')
		
	elif cmd=='log':
		vc = version.VersionControl()
		for l in vc.repo.sql("select * from log order by rowid desc limit 10 ", as_dict =1):
			print 'file:'+ l['fname'] + ' | version: ' + l['version']
		print 'version %s' % vc.repo.get_value('last_version_number')
		vc.close()
		
	elif cmd=='files':
		vc = version.VersionControl()
		for f in vc.repo.sql("select fname from files where fname like ?", ((sys.argv[2] + '%'),)):
			print f[0]
		vc.close()
	
	# pull from remote and merge with local
	elif cmd=='gitpull':
		branch = 'master'
		if len(sys.argv)>2:
			branch = sys.argv[2]

		print "pulling erpnext"
		os.system('git pull origin %s' % branch)
		vc = version.VersionControl()
		vc.setup_master()
		vc.merge(vc.master, vc.repo)
		vc.close()

		print "pulling framework"
		os.chdir('lib')
		os.system('git pull origin %s' % branch)
		
	
if __name__=='__main__':
	run()