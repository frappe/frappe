"""
make index, wn.js, wn.css pages
- rebuild all pages on change of website settings (toolbar)
- if home, write index.html
"""
def make(version):
	import os
	import webnotes
	from webnotes.model.code import get_obj
	from jinja2 import Template
	
	webnotes.connect()
	
	# get web home
	home_page = webnotes.conn.get_default("web_home_page") or 'Login Page'

	page = get_obj('Page', home_page)
	page.get_from_files()

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


def page_name(title):
	"""truncated page name"""	
	import re
	name = title.lower()
	name = re.sub('[~!@#$%^&*()<>,."\']', '', name)
	return '-'.join(name.split()[:4])
