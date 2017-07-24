# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
import json
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

import frappe

def check_user_tags(dt):
	"if the user does not have a tags column, then it creates one"
	try:
		frappe.db.sql("select `_user_tags` from `tab%s` limit 1" % dt)
	except Exception as e:
		if e.args[0] == 1054:
			DocTags(dt).setup()

@frappe.whitelist()
def add_tag(tag, dt, dn, color=None):
	"adds a new tag to a record, and creates the Tag master"
	DocTags(dt).add(dn, tag)

	return tag

@frappe.whitelist()
def remove_tag(tag, dt, dn):
	"removes tag from the record"
	DocTags(dt).remove(dn, tag)

@frappe.whitelist()
def get_tagged_docs(doctype, tag):
	frappe.has_permission(doctype, throw=True)

	return frappe.db.sql("""SELECT name
		FROM `tab{0}`
		WHERE _user_tags LIKE '%{1}%'""".format(doctype, tag))

@frappe.whitelist()
def get_tags(doctype, txt, cat_tags):
	tags = json.loads(cat_tags)
	try:
		for _user_tags in frappe.db.sql_list("""select DISTINCT `_user_tags`
			from `tab{0}`
			where _user_tags like '%{1}%'
			limit 50""".format(frappe.db.escape(doctype), frappe.db.escape(txt))):
			tags.extend(_user_tags[1:].split(","))
	except Exception as e:
		if e.args[0]!=1054: raise
	return sorted(filter(lambda t: t and txt.lower() in t.lower(), list(set(tags))))

class DocTags:
	"""Tags for a particular doctype"""
	def __init__(self, dt):
		self.dt = dt

	def get_tag_fields(self):
		"""returns tag_fields property"""
		return frappe.db.get_value('DocType', self.dt, 'tag_fields')

	def get_tags(self, dn):
		"""returns tag for a particular item"""
		return (frappe.db.get_value(self.dt, dn, '_user_tags', ignore=1) or '').strip()

	def add(self, dn, tag):
		"""add a new user tag"""
		tl = self.get_tags(dn).split(',')
		if not tag in tl:
			tl.append(tag)
			self.update(dn, tl)

	def remove(self, dn, tag):
		"""remove a user tag"""
		tl = self.get_tags(dn).split(',')
		self.update(dn, filter(lambda x:x.lower()!=tag.lower(), tl))

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
			frappe.db.sql("update `tab%s` set _user_tags=%s where name=%s" % \
				(self.dt,'%s','%s'), (tags , dn))
		except Exception as e:
			if e.args[0]==1054:
				if not tags:
					# no tags, nothing to do
					return

				self.setup()
				self.update(dn, tl)
			else: raise

	def setup(self):
		"""adds the _user_tags column if not exists"""
		from frappe.model.db_schema import add_column
		add_column(self.dt, "_user_tags", "Data")
