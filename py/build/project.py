verbose = False
import os				

def build():
	"""concat / minify js files"""
	from py.build.bundle import Bundle
	bundle = Bundle()
	bundle.make('build.json')
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