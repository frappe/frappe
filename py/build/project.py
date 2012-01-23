verbose = False
import os

class Project:
	"""
		Build a project
		Make files::
			
			index.html
			assets/template.html
			assets/js/core.min.js
			assets/timestamps.json
	"""	
	def __init__(self):
		"""
			load libraries
		"""
		from py.build.bundle import Bundle
		self.bundle = Bundle()

	def getversion(self):
		"""get from version.num file and increment it"""
		
		if os.path.exists('version.num'):
			with open('version.num', 'r') as vfile:
				self.version = int(vfile.read()) + 1
		else:
			self.version = 1

		with open('version.num', 'w') as vfile:
			vfile.write(str(self.version))
			
		return self.version
		
	def boot(self):
		"""
			returns bootstrap js
		"""
		import json

		corejs = open('lib/js/core.min.js', 'r')		
		boot = ('window._version_number="%s";' % str(self.getversion())) + \
			'\n' + corejs.read()

		corejs.close()
		
		return boot

	def render_templates(self):
		"""
			Generate static files from templates
		"""
		# render templates
		boot = self.boot()
		for wt in os.walk('templates'):
			for fname in wt[2]:
				if fname.split('.')[-1]=='html' and not fname.startswith('template'):
					fpath = os.path.relpath(os.path.join(wt[0], fname), 'templates')
					
					with open(os.path.join(wt[0], fname), 'r') as tempfile:
						temp = tempfile.read()
					
					temp = temp % boot
					
					with open(fpath, 'w') as outfile:
						outfile.write(temp)

					print "Rendered %s | %.2fkb" % (fpath, os.path.getsize(fpath) / 1024.0)
				

	def build(self):
		"""
			build js files, index.html
		"""
		for wt in os.walk('lib'):
			for fname in wt[2]:
				if fname=='build.json':
					self.bundle.make(os.path.join(wt[0], fname))
						
		self.render_templates()