import webnotes

def get():
	"""load print format by `name`"""
	import re

	html = get_html(webnotes.form.getvalue('name'))

	p = re.compile('\$import\( (?P<name> [^)]*) \)', re.VERBOSE)
	out_html = ''
	if html: 
		out_html = p.sub(substitute, html)

	webnotes.response['message'] = out_html
	
def substitute(match):
	"""return matched printformat by html"""
	name = match.group('name')
	return get_html(name)

def get_html(name):
	"""load html from db"""
	html = webnotes.conn.sql('select html from `tabPrint Format` where name="%s"' % name)
	return html and html[0][0] or ''