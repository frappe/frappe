verbose = True
force_rebuild = False
no_minify = False

def run():
	"""
		Run the builder
	"""
	global verbose
	import sys, os

	sys.path.append('py')
	sys.path.append('lib/py')

	from build.project import Project

	verbose = True
	Project().build()
	
if __name__=='__main__':
	run()