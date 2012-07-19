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

# to generate sitemaps

from __future__ import unicode_literals
frame_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s
</urlset>"""

link_xml = """\n<url><loc>%s</loc><lastmod>%s</lastmod></url>"""

# generate the sitemap XML
def generate(domain):
	global frame_xml, link_xml
	import urllib, os
	import webnotes

	# settings
	max_doctypes = 10
	max_items = 1000
	
	site_map = ''
	page_list = []
	
	if domain:
		# list of all pages in web cache
		pages = webnotes.conn.sql("""\
			select name, `modified`
			from `tabWeb Cache`
			order by modified desc""")
		
		for p in pages:
			page_url = os.path.join(domain, urllib.quote(p[0]) + '.html')
			modified = p[1].strftime('%Y-%m-%d')
			site_map += link_xml % (page_url, modified)

	return frame_xml % site_map
