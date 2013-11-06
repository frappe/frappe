# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 

from __future__ import unicode_literals

import urllib
import webnotes
import webnotes.webutils
from webnotes.utils import get_request_site_address

def get_context():
	"""generate the sitemap XML"""
	links = webnotes.webutils.get_website_sitemap().items()
	host = get_request_site_address()
	
	for l in links:
		l[1]["loc"] = urllib.basejoin(host, urllib.quote(l[1].get("page_name", l[1]["link_name"]).encode("utf-8")))
	
	return {
		"links": [l[1] for l in links if not l[1].get("no_sitemap")]
	}
	