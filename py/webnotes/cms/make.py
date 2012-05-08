"""
make index, wn.js, wn.css pages
- rebuild all pages on change of website settings (toolbar)
"""
def make(version):
	import os
	import webnotes
	from webnotes.model.code import get_obj
	from jinja2 import Template
	from webnotes.cms import page_name, get_home_page
	
	webnotes.connect()
	
	# get web home
	home_page = get_home_page('Guest')

	page = get_obj('Page', home_page)

	os.chdir('public')

	page.write_cms_page(home_page=True)
	
	# script - wn.js
	import startup.event_handlers
	if hasattr(startup.event_handlers, 'get_web_script'):
		with open('js/wn-web.js', 'w') as f:

			script = 'window._version_number = "%s";\n' % version
			script += 'window.home_page = "%s";\n' % home_page

			script += startup.event_handlers.get_web_script()

			f.write(script)

	# style - wn.css
	if hasattr(startup.event_handlers, 'get_web_style'):
		with open('css/wn-web.css', 'w') as f:
			f.write(startup.event_handlers.get_web_style())

	# make app.html
	with open('../lib/conf/app.html', 'r') as app_template:
		with open('app.html', 'w') as app:
			app.write(Template(app_template.read()).render(version=version))


