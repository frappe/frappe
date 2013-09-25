# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 

from __future__ import unicode_literals
import urllib
import webnotes
import webnotes.webutils
from webnotes.utils import nowdate

def generate(domain):
	"""generate the sitemap XML"""

	frame_xml = """<?xml version="1.0" encoding="UTF-8"?>
	<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s
	</urlset>"""

	link_xml = """\n<url><loc>%s</loc><lastmod>%s</lastmod></url>"""
	
	site_map = ""
	if domain:
		today = nowdate()
		
		for page_name, page_options in webnotes.webutils.get_website_sitemap().items():
			url = urllib.basejoin(domain, urllib.quote(page_name.encode("utf-8")))
			site_map += link_xml % (url, today)
	
	return frame_xml % site_map
