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
		from build.bundle import Bundle
		from nav import Nav
		
		self.bundle = Bundle()
		self.nav = Nav()

	def boot(self):
		"""
			returns bootstrap js
		"""
		import json

		corejs = open('lib/js/core.min.js', 'r')
		v = int(self.vc.repo.get_value('last_version_number') or 0) + 1
		
		boot = ('window._version_number="%s"' % str(v)) + \
			'\n' + corejs.read()

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
				

	def build(self, root_path):
		"""
			Build all js files, index.html and template.html
		"""
		from build.version import VersionControl
		
		self.vc = VersionControl(root_path)
		self.vc.add_all()
		
		# index, template if framework is dirty
		if self.vc.repo.uncommitted():
			self.bundle.bundle(self.vc)			
			self.render_templates()

			# again add all bundles
			self.vc.add_all()
			self.vc.repo.commit()
		
		self.vc.close()
