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
</div>
<div class="no_script" style="display: none;">
 %s
</div>
<footer></footer>
<script>wn.require('js/app.js');</script>
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
			
		return template.render(bootinfo = '', \
			corejs = '', body_html=html_snapshot(page), ajax_meta_tag = '')
	
	# home page
	else:
		import webnotes.session_cache
		from build.project import get_corejs
		import json

		bootinfo = webnotes.session_cache.get()
		bootinfo = """var wn = {}; wn.boot = %s;""" % json.dumps(bootinfo)

		return template.render(bootinfo = bootinfo, \
			corejs = get_corejs(), body_html=body_html % '', \
			ajax_meta_tag = '<meta name="fragment" content="!">')
			
def html_snapshot(page):
	"""get html snapshot for search bot"""
	from webnotes.widgets.page import get_page_html	
	from webnotes.model.doc import Document

	doc = Document('Top Bar Settings', 'Top Bar Settings')
	doc.content = get_page_html(page)
	doc.header_menu = doc.footer_menu = ''
	doc.page_name = page
	
	for m in webnotes.conn.sql("""select parentfield, label, std_page, custom_page
		from `tabTop Bar Item` where parent='Top Bar Settings' order by idx""", as_dict=1):
	
		if m['custom_page']:
			m['std_page'] = m['custom_page']

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
	
	
