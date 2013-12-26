# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes

no_sitemap = True

def get_context():
	return {
		"javascript": webnotes.conn.get_value('Website Script', None, 'javascript'),
		"google_analytics_id": webnotes.conn.get_value("Website Settings", "Website Settings", "google_analytics_id")
	}