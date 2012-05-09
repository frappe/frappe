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
		# list of all Guest pages (static content)
		for r in webnotes.conn.sql("""SELECT distinct t1.name, t1.modified 
				FROM tabPage t1, `tabPage Role` t2
				WHERE t1.name = t2.parent
				and t2.role = 'Guest'
				and t1.web_page = 'Yes'
				ORDER BY modified DESC"""):

			page_url = os.path.join(domain, urllib.quote(r[0]) + '.html')
			site_map += link_xml % (page_url, r[1].strftime('%Y-%m-%d'))
		

	return frame_xml % site_map
