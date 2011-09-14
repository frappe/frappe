#!/usr/bin/env python

import os, sys

from py.build import version
version.verbose = True


def run():
	sys.path.append('lib')
	sys.path.append('lib/py')
	vc = version.VersionControl(os.path.abspath(os.curdir))

	if len(sys.argv)<2:
		print "wnframework version control utility"
		print
		print "Usage: wnf build|add|commit|diff|merge|setup"

	cmd = sys.argv[1]

	if cmd=='build':
		from py import build
		build.run(os.path.abspath(os.curdir))
		
	if cmd=='add':
		if not len(sys.argv)>1:
			print 'usage: wnf add path/to/file'
			return
			
		vc.repo.add(sys.argv[2])
	
	if cmd=='commit':
		if len(sys.argv>2) and sys.argv[2]=='-a':
			vc.add_all()
		
		vc.repo.commit()
	
	if cmd=='diff':
		vc.repo.uncommitted()
	
	if cmd=='merge':
		vc.setup_master()
		if sys.argv[2]=='local':
			vc.merge(vc.repo, vc.master)
		elif sys.argv[2]=='master':
			vc.merge(vc.master, vc.repo)
		else:
			print "usage: wnf merge local|master"
			print "help: parameter (local or master) is the source"

	if cmd=='setup':
		vc.repo.setup()

	vc.close()

if __name__=='__main__':
	run()