verbose = True
force_rebuild = False
no_minify = False

def run(path):
	"""
		Run the builder
	"""
	global verbose
	import sys, os

	from build.project import Project

	verbose = True
	Project().build(path)
	
if __name__=='__main__':
	run()