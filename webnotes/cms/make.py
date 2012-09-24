from __future__ import unicode_literals
"""
make index, wn.js, wn.css pages
- rebuild all pages on change of website settings (toolbar)
"""
def make():
	import os
	import webnotes
	# TODO: why is jinja2 imported?
	from jinja2 import Template
	import webnotes.cms
	
	if not webnotes.conn:
		webnotes.connect()
	
	make_web_core()

def make_web_core():
	"""make index.html, wn-web.js, wn-web.css, sitemap.xml and rss.xml"""
	# index.html
	#from webnotes.model.code import get_obj
	import webnotes
	
	home_page = webnotes.cms.get_home_page('Guest')

	# js/wn-web.js and css/wn-web.css
	write_web_js_css(home_page)

def write_web_js_css(home_page):
	"""write web js and css"""

	# script - wn.js
	import os
	import startup.event_handlers

	fname = 'js/wn-web.js'
	if os.path.basename(os.path.abspath('.'))!='public':
		fname = os.path.join('public', fname)
			
	if hasattr(startup.event_handlers, 'get_web_script'):
		with open(fname, 'w') as f:

			script = 'window.home_page = "%s";\n' % home_page
			script += startup.event_handlers.get_web_script()

			f.write(script)

	fname = 'css/wn-web.css'
	if os.path.basename(os.path.abspath('.'))!='public':
		fname = os.path.join('public', fname)

	# style - wn.css
	if hasattr(startup.event_handlers, 'get_web_style'):
		with open(fname, 'w') as f:
			f.write(startup.event_handlers.get_web_style())