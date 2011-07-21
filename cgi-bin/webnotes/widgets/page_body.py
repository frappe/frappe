#:    HTML Template of index.cgi
index_template = '''<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head id="head">
<!-- Web Notes Framework : www.webnotesframework.org -->

  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
  <meta name="robots" content="index, follow" />
  <meta name="keywords" content="%(keywords)s" />
  <meta name="description" content="%(site_description)s" />
  <meta name="generator" content="Web Notes Framework Version v170 - Open Source Web Application Framework" />  
  
  <title>%(title)s</title>
  <link type="text/css" rel="stylesheet" href="css/jquery-ui.css">
  <link type="text/css" rel="stylesheet" href="css/default.css">
  <link rel="Shortcut Icon" href="/favicon.ico">
  
  <script language="JavaScript" src="js/jquery/jquery.min.js"></script>
  <script language="JavaScript" src="js/jquery/jquery-ui.min.js"></script>
  <script type="text/javascript" src="js/tiny_mce_33/jquery.tinymce.js"></script>
  <script language="JavaScript" src="js/wnf.compressed.js"></script>
  %(import_form)s
  <script language="JavaScript">var _startup_data = %(startup_data)s;</script>
  <!--[if IE]><script language="javascript" type="text/javascript" src="js/jquery/excanvas.min.js"></script><![endif]-->
  %(add_in_head)s
  
  <script type="text/javascript">
    window.dhtmlHistory.create({ debugMode: false });
  </script>
</head>
<body>

<div id="dialog_back"></div>

<div id="startup_div" style="padding: 8px; font-size: 14px;"></div>

<!-- Main Starts -->
<div id="body_div"> 

	<!--static (no script) content-->
	<div class="no_script">
		%(content)s
	</div>

</div>

%(add_in_body)s
</body>
</html>
'''

redirect_template = '''<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
<title>%s</title>
<meta http-equiv="REFRESH" content="0; url=%s"></HEAD>
<BODY style="font-family: Arial; padding: 8px; font-size: 14px; margin: 0px;">
Redirecting...
</BODY>
</HTML>'''

page_properties = {
	'add_in_head':'',
	'add_in_body':'',
	'keywords':'',
	'site_description':'',
	'title':'',
	'content':'',
	'startup_data':'{}',
	'import_form':'<script language="JavaScript" src="js/form.compressed.js"></script>'
}


import webnotes

# remove 'id' attributes so they don't conflict
# ---------------------------------------------
def replace_id(match):
	#webnotes.msgprint(match.group('name'))
	return ''
	
def scrub_ids(content):
	import re
	
	p = re.compile('id=\"(?P<name> [^\"]*)\"', re.VERBOSE)
	content = p.sub(replace_id, content)

	p = re.compile('id=\'(?P<name> [^\']*)\'', re.VERBOSE)
	content = p.sub(replace_id, content)
	
	return content

def get_page_content(page):
	"""
		Gets the HTML content from `static_content` or `content` property of a `Page`
		and loads it in global `page_properties`
	"""
	from webnotes.model.code import get_code
	from webnotes.model.doc import Document
	global page_properties
	
	if not page: return
	if '/' in page: page = page.split('/')[0]
	if page=='Form': return
	
	try:
		doc = Document('Page', page)
	
		load_page_metatags(doc)
	
		template = '%(content)s'
		# content
		if doc.template:
			template = get_code(webnotes.conn.get_value('Page Template', doc.template, 'module'), 'Page Template', doc.template, 'html', fieldname='template')
	
		page_properties['content'] = get_code(doc.module, 'page', doc.name, 'html', fieldname='content')
				
		# dynamic (scripted) content
		if page_properties['content'] and page_properties['content'].startswith('#!python'):
			page_properties.update(webnotes.model.code.execute(page_properties['content']))
	
		page_properties['content'] = scrub_ids(template % {'content':page_properties['content']})
	except:
		pass

def load_page_metatags(doc):
	global page_properties

	try:
		import startup
	except:
		startup = ''

	# page meta-tags
	page_properties['title'] = doc.page_title or doc.name
	page_properties['keywords'] = doc.keywords or webnotes.conn.get_value('Control Panel',None,'keywords') or ''
	page_properties['site_description'] = doc.site_description or webnotes.conn.get_value('Control Panel',None,'site_description') or ''
	page_properties['add_in_head'] = getattr(startup, 'add_in_head', '')
	page_properties['add_in_body'] = getattr(startup, 'add_in_body', '')


# find the page to load as static
# -------------------------------

def load_properties():
	import webnotes.widgets.page
	import urllib

	page_url = webnotes.form_dict.get('_escaped_fragment_', webnotes.form_dict.get('page', ''))

	if pag_url and page_url.lower().startswith('page/'): 
		page_url = page_url[5:]
	
	if page_url:
		get_page_content(urllib.unquote(page_url))
	else:
		get_page_content(webnotes.user.get_home_page())

# generate the page
# -----------------
def load_default_properties():
	if not page_properites['keywords']:
		page_properites['keywords'] = webnotes.conn.get_value('Control Panel',None,'keywords') or ''
	if not page_properites['site_description']:
		page_properites['site_description'] = webnotes.conn.get_value('Control Panel',None,'site_description') or ''

# generate the page
# -----------------
def get():
	"""
	   returns the full rendered index.cgi
	   Gets `keywords` and `site_description` from the `Control Panel`
	"""
	import webnotes
	no_startup = webnotes.form.getvalue('no_startup') or None

	global index_template, redirect_template
	import webnotes.session_cache
	try:
		import json
	except: # python 2.4
		import simplejson as json
	
	page = webnotes.form_dict.get('page', '')
	# sid in public display
	# ---------------------
	if webnotes.form_dict.get('sid'): 
		return redirect_template % ('Redirecting...', ('index.cgi' + (page and ('?page='+page) or '')))
	
	if '%(content)s' in index_template:
		load_properties()
		
		# load the session data
		# ---------------------
		try:
			sd = webnotes.session_cache.get()
		except:
			import webnotes.utils
			sd = {'exc':webnotes.utils.getTraceback()}
		
		# add debug messages

		sd['server_messages'] = '\n--------------\n'.join(webnotes.message_log)
		
		page_properties['startup_data'] = no_startup and '{}' or json.dumps(sd)
		
		# no form api required for guests
		if webnotes.session['user']=='Guest':
			page_properties['import_form'] = ''
		
		index_template = index_template % page_properties
		
	return index_template
