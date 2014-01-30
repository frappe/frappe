# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def on_update(self):
		remove_empty_permissions()
		
def remove_empty_permissions():
	permissions_cache_to_be_cleared = webnotes.conn.sql_list("""select distinct profile 
		from `tabWebsite Sitemap Permission`
		where ifnull(`read`, 0)=0 and ifnull(`write`, 0)=0 and ifnull(`admin`, 0)=0""")
	
	webnotes.conn.sql("""delete from `tabWebsite Sitemap Permission`
		where ifnull(`read`, 0)=0 and ifnull(`write`, 0)=0 and ifnull(`admin`, 0)=0""")
		
	# TODO clear permissions cache for permissions_cache_to_be_cleared
	