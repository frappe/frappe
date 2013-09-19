# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

import os
import webnotes

def make():
	from webnotes.webutils import get_home_page
	from webnotes.utils import get_path

	if not webnotes.conn:
		webnotes.connect()
	
	home_page = get_home_page()

	if not os.path.exists(get_path("public", "js")):
		os.makedirs(get_path("public", "js"))
	fname = os.path.join(get_path("public", "js", "wn-web.js"))
	with open(fname, 'w') as f:
		f.write(get_web_script())

	if not os.path.exists(get_path("public", "css")):
		os.makedirs(get_path("public", "css"))
	fname = os.path.join(get_path("public", "css", "wn-web.css"))
	with open(fname, 'w') as f:
		f.write(get_web_style())

def get_web_script():
	"""returns web startup script"""
	user_script = ""
	
	ws = webnotes.doc("Website Settings", "Website Settings")

	if ws.google_analytics_id:
		user_script += google_analytics_template % ws.google_analytics_id
	
	user_script += (webnotes.conn.get_value('Website Script', None, 'javascript') or '')

	return user_script
	
def get_web_style():
	"""returns web css"""
	return webnotes.conn.get_value('Style Settings', None, 'custom_css') or ''

google_analytics_template = """

// Google Analytics template

window._gaq = window._gaq || [];
window._gaq.push(['_setAccount', '%s']);
window._gaq.push(['_trackPageview']);

(function() {
    var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
    ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
    var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
})();
"""