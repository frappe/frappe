verbose = False
import os				

def build():
	"""concat / minify js files"""
	from py.build.bundle import Bundle
	bundle = Bundle()
	for wt in os.walk('lib'):
		for fname in wt[2]:
			if fname=='build.json':
				bundle.make(os.path.join(wt[0], fname))
	
	increment_version()

def get_version():
	"""get from version.num file and increment it"""
	if os.path.exists('version.num'):
		with open('version.num', 'r') as vfile:
			version = int(vfile.read()) + 1
	else:
		version = 1

	return version

def increment_version():
	"""incremenet version by 1"""
	version = get_version()
	with open('version.num', 'w') as vfile:
		vfile.write(str(version))
		
	return version
	
def get_corejs():
	"""return corejs with version number"""
	import json

	corejs = open('lib/js/core.min.js', 'r')		
	boot = ('window._version_number="%s";' % str(get_version())) + \
		'\n' + corejs.read()

	corejs.close()
	
	return boot