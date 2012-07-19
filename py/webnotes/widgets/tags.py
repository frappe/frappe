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
from webnotes.utils import cint, cstr, load_json


def check_user_tags(dt):
	"if the user does not have a tags column, then it creates one"
	try:
		webnotes.conn.sql("select `_user_tags` from `tab%s` limit 1" % dt)
	except Exception, e:
		if e.args[0] == 1054:
			DocTags(dt).setup()
			

#
# Add a new tag
#
@webnotes.whitelist()
def add_tag():
	"adds a new tag to a record, and creates the Tag master"
	
	f = webnotes.form_dict
	tag, color = f.get('tag'), f.get('color')
	dt, dn = f.get('dt'), f.get('dn')
	
	DocTags(dt).add(dn, tag)
		
	return tag

#
# remove tag
#
@webnotes.whitelist()
def remove_tag():
	"removes tag from the record"
	f = webnotes.form_dict
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

	def create(self, tag):
		try:
			webnotes.conn.sql("insert into tabTag(name) values (%s) on duplicate key ignore", tag)
		except Exception, e:
			if e.args[0]==1147:
				self.setup_tag_master()
				self.create(tag)

	def add(self, dn, tag):
		"""add a new user tag"""
		self.create(tag)
		tl = self.get_tags(dn).split(',')
		if not tag in tl:
			tl.append(tag)
			self.update(dn, tl)
			TagCounter(self.dt).update(tag, 1)

	def remove(self, dn, tag):
		"""remove a user tag"""
		tl = self.get_tags(dn).split(',')
		self.update(dn, filter(lambda x:x!=tag, tl))
		TagCounter(self.dt).update(tag, -1)

	def remove_all(self, dn):
		"""remove all user tags (call before delete)"""
		tl = self.get_tags(dn).split(',')
		tl = filter(lambda x:x, tl)
		tc = TagCounter(self.dt)
		for t in tl:
			tc.update(t, -1)
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
			else: raise e

	def setup_tags(self):
		"""creates the tabTag table if not exists"""
		webnotes.conn.commit()
		from webnotes.modules import reload_doc
		reload_doc('core','doctype','tag')
		webnotes.conn.begin()
		
	def setup(self):
		"""adds the _user_tags column if not exists"""
		webnotes.conn.commit()
		webnotes.conn.sql("alter table `tab%s` add column `_user_tags` varchar(180)" % self.dt)
		webnotes.conn.begin()








class TagCounter:
	"""
		Tag Counter stores tag count per doctype in table _tag_cnt
	"""
	def __init__(self, doctype):
		self.doctype = doctype

	# setup / update tag cnt
	# keeps tags in _tag_cnt (doctype, tag, cnt)
	# if doctype cnt does not exist
	# creates it for the first time
	def update(self, tag, diff):
		if not tag:
			return
		"updates tag cnt for a doctype and tag"
		cnt = webnotes.conn.sql("select cnt from `_tag_cnt` where doctype=%s and tag=%s", (self.doctype, tag))

		if not cnt:
			# first time? build a cnt and add
			self.new_tag(tag, 1)
		else:
			webnotes.conn.sql("update `_tag_cnt` set cnt = ifnull(cnt,0) + (%s) where doctype=%s and tag=%s",\
				(diff, self.doctype, tag))

 	
	def new_tag(self, tag, cnt=0, dt=None):
		"Creates a new row for the tag and doctype"
		webnotes.conn.sql("insert into `_tag_cnt`(doctype, tag, cnt) values (%s, %s, %s)", \
			(dt or self.doctype, tag, cnt))

	def build(self, dt):
		"Builds / rebuilds the counting"		
		webnotes.conn.sql("delete from _tag_cnt where doctype=%s", dt)
		
		# count
		tags = {}
		for ut in webnotes.conn.sql("select _user_tags from `tab%s`" % dt):
			if ut[0]:
				tag_list = ut[0].split(',')
				for t in tag_list:
					if t:
						tags[t] = tags.get(t, 0) + 1

		# insert
		for t in tags:
			self.new_tag(t, tags[t], dt)
						
	def load_top(self):
		try:
			return webnotes.conn.sql("select tag, cnt from `_tag_cnt` where doctype=%s and cnt>0 order by cnt desc limit 10", self.doctype, as_list = 1)
		except Exception, e:
			if e.args[0]==1146:
				self.setup()
				return self.load_top()
			else: raise e

	def setup(self):
		"creates the tag cnt table from the DocType"
		webnotes.conn.commit()
		webnotes.conn.sql("""
		create table `_tag_cnt` (
			doctype varchar(180), tag varchar(22), cnt int(10),
			primary key (doctype, tag), index cnt(cnt)) ENGINE=InnoDB
		""")
		webnotes.conn.begin()
		
		# build all
		for dt in webnotes.conn.sql("select name from tabDocType where ifnull(issingle,0)=0 and docstatus<2"):
			try:
				self.build(dt[0])
			except Exception, e:
				if e.args[0]==1054: pass
				else: raise e



def get_top_field_tags(dt):
	from webnotes.model.doctype import get_property
	tf = get_property(dt, 'tag_fields')

	if not tf: return []
	
	# restrict to only 2 fields
	tf = tuple(set(tf.split(',')))[:2]
	tl = []
	
	for t in tf:
		t = t.strip()
		# disastrous query but lets try it!
		tl += webnotes.conn.sql("""select `%s`, count(*), '%s' from `tab%s` 
			where docstatus!=2 
			and ifnull(`%s`, '')!=''
			group by `%s` 
			order by count(*) desc 
			limit 10""" % (t, t, dt, t, t), as_list=1)

	if tl:
		tl.sort(lambda x, y: y[1]-x[1])

	return tl[:10]

# returns the top ranked 10 tags for the
# doctype. 
# merges the top tags from fields and user tags
@webnotes.whitelist()
def get_top_tags(args=''):
	"returns the top 10 tags for the doctype from fields (7) and users (3)"
	tl = None
	dt = webnotes.form_dict['doctype']
	
	from webnotes.utils.cache import CacheItem
	
	# if not reload, try and load from cache
	if not cint(webnotes.form_dict.get('refresh')):
		tl = CacheItem('tags-' + dt).get()
	
	if tl:
		return eval(tl)
	else:
		tl = TagCounter(dt).load_top() + get_top_field_tags(dt)
		if tl:
			tl.sort(lambda x, y: y[1]-x[1])
			tl = tl[:20]
			
		# set in cache and don't reload for an hour
		CacheItem('tags-' + dt).set(tl, 3600)
	
		return tl

def clear_tags(dt, dn):
	DocTags(dt).remove_all(dn)
