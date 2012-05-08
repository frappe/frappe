"""
make index, wn.js, wn.css pages
- rebuild all pages on change of website settings (toolbar)
"""
def make(version):
	import os
	import webnotes
	from webnotes.model.code import get_obj
	from jinja2 import Template
	import webnotes.cms
	
	webnotes.connect()
	
	# get web home
	home_page = webnotes.cms.get_home_page('Guest')

	page = get_obj('Page', home_page)	
	page.write_cms_page(home_page=True)
	
	# script - wn.js
	import startup.event_handlers
	if hasattr(startup.event_handlers, 'get_web_script'):
		with open('public/js/wn-web.js', 'w') as f:

			script = 'window._version_number = "%s";\n' % version
			script += 'window.home_page = "%s";\n' % home_page

			script += startup.event_handlers.get_web_script()

			f.write(script)

	# style - wn.css
	if hasattr(startup.event_handlers, 'get_web_style'):
		with open('public/css/wn-web.css', 'w') as f:
			f.write(startup.event_handlers.get_web_style())

	# make app.html
	with open(os.path.join(os.path.dirname(webnotes.cms.__file__), 'app.html'), 'r') \
		as app_template:
		with open('public/app.html', 'w') as app:
			app.write(Template(app_template.read()).render(version=version))


