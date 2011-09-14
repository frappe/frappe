#!/usr/bin/env python

import os, sys

from py.build import version
version.verbose = True


def run():
	sys.path.append('lib')
	sys.path.append('lib/py')

	if len(sys.argv)<2:
		print "wnframework version control utility"
		print
		print "Usage: wnf build|add|commit|diff|merge|setup"

	cmd = sys.argv[1]

	if cmd=='build':
		from py import build
		build.run()

		vc = version.VersionControl()
		print 'version %s' % vc.repo.get_value('last_version_number')
				
	if cmd=='merge':
		vc = version.VersionControl()
		vc.setup_master()
		if sys.argv[2]=='local':
			vc.merge(vc.repo, vc.master)
		elif sys.argv[2]=='master':
			vc.merge(vc.master, vc.repo)
		else:
			print "usage: wnf merge local|master"
			print "help: parameter (local or master) is the source"
		vc.close()

	if cmd=='setup':
		vc = version.VersionControl()
		vc.repo.setup()
		vc.close()
		
	if cmd=='clear_startup':
		from webnotes import startup
		startup.clear_info('all')

		vc = version.VersionControl()
		print 'version %s' % vc.repo.get_value('last_version_number')
		
	if cmd=='log':
		vc = version.VersionControl()
		for l in vc.repo.sql("select * from log order by rowid desc limit 10 ", as_dict =1):
			print 'file:'+ l['fname'] + ' | version: ' + l['version']
		print 'version %s' % vc.repo.get_value('last_version_number')
		vc.close()
		
	if cmd=='files':
		vc = version.VersionControl()
		for f in vc.repo.sql("select fname from files where fname like ?", ((sys.argv[2] + '%'),)):
			print f[0]
		vc.close()

if __name__=='__main__':
	run()