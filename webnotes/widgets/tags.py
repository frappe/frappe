# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
Server side functions for tagging.

- Tags can be added to any record (doctype, name) in the system.
- Items are filtered by tags
- Top tags are shown in the sidebar (?)
- Tags are also identified by the tag_fields property of the DocType

Discussion:

Tags are shown in the docbrowser and ideally where-ever items are searched.
There should also be statistics available for tags (like top tags etc)


Design:

- free tags (user_tags) are stored in __user_tags
- doctype tags are set in tag_fields property of the doctype
- top tags merges the tags from both the lists (only refreshes once an hour (max))

"""

import webnotes

def check_user_tags(dt):
	"if the user does not have a tags column, then it creates one"
	try:
		webnotes.conn.sql("select `_user_tags` from `tab%s` limit 1" % dt)
	except Exception, e:
		if e.args[0] == 1054:
			DocTags(dt).setup()
			
@webnotes.whitelist()
def add_tag():
	"adds a new tag to a record, and creates the Tag master"
	
	f = webnotes.local.form_dict
	tag, color = f.get('tag'), f.get('color')
	dt, dn = f.get('dt'), f.get('dn')
	
	DocTags(dt).add(dn, tag)
		
	return tag

@webnotes.whitelist()
def remove_tag():
	"removes tag from the record"
	f = webnotes.local.form_dict
	tag, dt, dn = f.get('tag'), f.get('dt'), f.get('dn')
	
	DocTags(dt).remove(dn, tag)


		
class DocTags:
	"""Tags for a particular doctype"""
	def __init__(self, dt):
		self.dt = dt
		
	def get_tag_fields(self):
		"""returns tag_fields property"""
		return webnotes.conn.get_value('DocType', self.dt, 'tag_fields')
		
	def get_tags(self, dn):
		"""returns tag for a particular item"""
		return webnotes.conn.get_value(self.dt, dn, '_user_tags', ignore=1) or ''

	def add(self, dn, tag):
		"""add a new user tag"""
		tl = self.get_tags(dn).split(',')
		if not tag in tl:
			tl.append(tag)
			self.update(dn, tl)

	def remove(self, dn, tag):
		"""remove a user tag"""
		tl = self.get_tags(dn).split(',')
		self.update(dn, filter(lambda x:x!=tag, tl))

	def remove_all(self, dn):
		"""remove all user tags (call before delete)"""
		self.update(dn, [])

	def update(self, dn, tl):
		"""updates the _user_tag column in the table"""

		if not tl:
			tags = ''
		else:
			tl = list(set(filter(lambda x: x, tl)))
			tags = ',' + ','.join(tl)
		try:
			webnotes.conn.sql("update `tab%s` set _user_tags=%s where name=%s" % \
				(self.dt,'%s','%s'), (tags , dn))
		except Exception, e:
			if e.args[0]==1054: 
				if not tags:
					# no tags, nothing to do
					return
					
				self.setup()
				self.update(dn, tl)
			else: raise
		
	def setup(self):
		"""adds the _user_tags column if not exists"""
		from webnotes.model.db_schema import add_column
		add_column(self.dt, "_user_tags", "Data")
