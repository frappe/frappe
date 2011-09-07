verbose = False

class Project:
	"""
		Build a project
		Make files::
			
			index.html
			assets/template.html
			assets/js/core.min.js
			assets/timestamps.json
	"""	
	def __init__(self,):
		"""
			load libraries
		"""
		from build.timestamps import Timestamps
		from build.bundle import Bundle
		from nav import Nav
		
		self.timestamps = Timestamps()
		self.bundle = Bundle()
		self.nav = Nav()

	def boot(self):
		"""
			returns bootstrap js
		"""
		import json

		corejs = open('lib/js/core.min.js', 'r')
		
		boot = 'var asset_timestamps_=' + self.timestamps.get('json', ('js', 'html', 'css')) \
			+ '\n' + corejs.read()
		
		corejs.close()
		return boot

	def render_templates(self):
		"""
			Generate static files from templates
		"""

		# render templates
		import os
		from jinja2 import Environment, FileSystemLoader
		from build.markdown2_extn import Markdown2Extension

		env = Environment(loader=FileSystemLoader('templates'), extensions=[Markdown2Extension])

		# dynamic boot info
		env.globals['boot'] = self.boot()
		env.globals['nav'] = self.nav.html()
		page_info = self.nav.page_info()
		
		for wt in os.walk('templates'):
			for fname in wt[2]:
				if fname.split('.')[-1]=='html' and not fname.startswith('template'):
					fpath = os.path.relpath(os.path.join(wt[0], fname), 'templates')
					temp = env.get_template(fpath)
					
					env.globals.update(self.nav.page_info_template)
					env.globals.update(page_info.get(fpath, {}))
					
					# out file in parent folder of template
					f = open(fpath, 'w')
					f.write(temp.render())
					f.close()
					print "Rendered %s | %.2fkb" % (fpath, os.path.getsize(fpath) / 1024.0)
				

	def build(self):
		"""
			Build all js files, timestamps.js, index.html and template.html
		"""
		
		# make bundles
		self.bundle.bundle(self.timestamps)
		
		# index, template if framework is dirty
		if self.timestamps.dirty:
			self.render_templates()
			self.timestamps.write()