# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 

from __future__ import unicode_literals

import urllib
import webnotes
import webnotes.webutils

def get_context():
	"""generate the sitemap XML"""
	links = webnotes.webutils.get_website_sitemap().items()

	host = ('https://' if webnotes.get_request_header('HTTPS') else 'http://') \
		+ webnotes.get_request_header('HTTP_HOST', "localhost")
	
	for l in links:
		l[1]["loc"] = urllib.basejoin(host, urllib.quote(l[1].get("page_name", l[1]["link_name"])))
	
	return {
		"links": [l[1] for l in links]
	}
	