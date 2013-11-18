# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 

from __future__ import unicode_literals

import urllib
import webnotes
import webnotes.webutils
from webnotes.utils import get_request_site_address

def get_context():
	"""generate the sitemap XML"""
	host = get_request_site_address()
	links = []
	for l in webnotes.conn.sql("""select * from `tabWebsite Sitemap` where ifnull(no_sitemap, 0)=0""", 
		as_dict=True):
		links.append({"loc": urllib.basejoin(host, urllib.quote(l.page_name.encode("utf-8")))})
	
	return links
	