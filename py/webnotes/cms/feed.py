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
Generate RSS feed for blog
"""

rss = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
        <title>%(title)s</title>
        <description>%(description)s</description>
        <link>%(link)s</link>
        <lastBuildDate>%(modified)s</lastBuildDate>
        <pubDate>%(modified)s</pubDate>
        <ttl>1800</ttl>
		%(items)s
</channel>
</rss>"""

rss_item = """
<item>
        <title>%(title)s</title>
        <description>%(content_html)s</description>
        <link>%(link)s</link>
        <guid>%(name)s</guid>
        <pubDate>%(modified)s</pubDate>
</item>"""

def generate():
	"""generate rss feed"""
	import webnotes, os
	from webnotes.model.doc import Document
	
	host = (os.environ.get('HTTPS') and 'https://' or 'http://') + os.environ.get('HTTP_HOST')
	
	items = ''
	modified = None
	for blog in webnotes.conn.sql("""select name, title, content_html, modified from tabBlog 
		where ifnull(published,0)=1 order by modified desc limit 100""", as_dict=1):
		blog['link'] = host + '/#!' + blog['name']
		blog['content_html'] = scrub(blog['content_html'] or '')
		if not modified:
			modified = blog['modified']
		items += rss_item % blog
		
	ws = Document('Website Settings', 'Website Settings')
	return rss % {
		'title': ws.title_prefix,
		'description': ws.description or (ws.title_prefix + ' Blog'),
		'modified': modified,
		'items': items,
		'link': host + '/#!blog'
	}
	
def scrub(txt):
	return txt.replace('<', '&lt;').replace('>', '&gt;')