# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

"""
Generate index.cgi html

Loads index.html from the template with:

1. bootinfo
2. static html of home / if _escaped_fragment_ is given
3. top menus and bottom menus

"""

import webnotes

body_html = """
<header></header>
<div id="startup_div" style="padding: 8px; 
	font-size: 12px; font-family: Arial !important; line-height: 1.6em;">
	Loading...
</div>
<!-- Main Starts -->
<div id="body_div"> 
	<footer></footer>
</div>
<div class="no_script" style="display: none;">
 %s
</div>
<div id="dialog_back"></div>
"""

def get():
	"""get index html"""
	import webnotes
	from jinja2 import Template
	
	with open('lib/conf/index.html', 'r') as f:
		template = Template(f.read())

	# google crawler
	if '_escaped_fragment_' in webnotes.form:
		page = webnotes.form_dict['_escaped_fragment_']
		if not page:
			page = webnotes.user.get_home_page()
			
		return template.render(bootinfo = '', style_tag='', version='0', analytics_code = '',\
			script_tag = '', body_html=html_snapshot(page), ajax_meta_tag = '')
	
	# home page
	else:
		import webnotes.session_cache
		from build.project import get_version
		import json

		bootdict = webnotes.session_cache.get()
		bootinfo = """var wn = {}; wn.boot = %s;""" % json.dumps(bootdict)

		if webnotes.session['user'] == 'Guest':
			script_tag = '<script type="text/javascript" src="js/all-web.js"></script>'
			style_tag = '<link type="text/css" rel="stylesheet" href="css/all-web.css">'
		else:
			script_tag = '<script type="text/javascript" src="js/all-app.js"></script>'
			style_tag = '<link type="text/css" rel="stylesheet" href="css/all-app.css">'

		return template.render(bootinfo = bootinfo, version = get_version(),
			script_tag = script_tag, style_tag = style_tag, body_html=body_html % '',
			ajax_meta_tag = '<meta name="fragment" content="!">', 
			analytics_code = bootdict.get('analytics_code', '') or '')
			
def html_snapshot(page):
	"""get html snapshot for search bot"""
	from webnotes.widgets.page import get_page_html	
	from webnotes.model.doc import Document

	doc = Document('Website Settings', 'Website Settings')
	doc.content = get_page_html(page)
	doc.header_menu = doc.footer_menu = ''
	doc.page_name = page
	
	for m in webnotes.conn.sql("""select parentfield, label, url, custom_page
		from `tabTop Bar Item` where parent='Top Bar Settings' order by idx""", as_dict=1):
	
		m['std_page'] = m.get('url') or m('custom_page')

		if m['parentfield']=='top_bar_items':				
			doc.header_menu += '<li><a href="index.cgi#!%(std_page)s">%(label)s</a></li>' % m
		else:
			doc.footer_menu += '<li><a href="index.cgi#!%(std_page)s">%(label)s</a></li>' % m
	
	return """
	<header>
		<h3>%(brand_html)s</h3>
		<ul>
			%(header_menu)s
		</ul>
	</header>
	%(content)s
	<footer>
		<ul>
			%(footer_menu)s
		</ul>
		<div>Address: %(address)s</div>
		<div>&copy; %(copyright)s</div>
		<div>Powered by <a href="https://erpnext.com">erpnext.com</a></div>
		<div style="background-color: #ffc; padding: 7px">
			This page is for search engines, for standard browsers click 
			<a href="index.cgi#!%(page_name)s">here</a>
		</div>
	</footer>
	""" % doc.fields
	
	
