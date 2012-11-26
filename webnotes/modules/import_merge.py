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
	Merges (syncs) incoming doclist into the database 
	Called when: 
		importing .txt files
		importing bulk records from .csv files
		
	For regular types, deletes the record and recreates it
	for special types: `DocType`, `Module Def`, `DocType Mapper` there are subclasses
	
	To use::
		set_doc(doclist, ovr=1, ingore=1, noupdate=1)
"""

import webnotes
from webnotes.model.doc import Document

# this variable is a flag that transfer process is on, to the on_update
# method so that if there are other processes on import, it can do so
in_transfer = 0

def set_doc(doclist, ovr=0, ignore=1, onupdate=1):
	"""
		Wrapper function to sync a record
	"""
	if doclist[0].doctype == "DocType":
		from webnotes.model.sync import merge_doctype
		return merge_doctype(doclist, force=ovr)	
	
	global in_transfer
	dt = doclist[0]['doctype']
	
	if webnotes.conn.exists(doclist[0]['doctype'], doclist[0]['name']):	
		# exists, merge if possible
		
		if dt == 'DocType Mapper':
			ud = UpdateDocTypeMapper(doclist)
		else:
			ud = UpdateDocument(doclist)
	else:
		ud = UpdateDocument(doclist)
	
	in_transfer = 1
	ud.sync()
	in_transfer = 0
	return '\n'.join(ud.log)

#
# Class to sync incoming document
#
class UpdateDocument:
	def __init__(self, in_doclist=[]):
		self.in_doclist = in_doclist
		self.doc = Document(fielddata = in_doclist[0])
		self.modified = self.doc.modified # make a copy
		self.doclist = []
		
		self.log = []
		self.exists = 0

	# sync
	def sync(self):
		is_mod = self.is_modified()
		
		if (not self.exists) or (is_mod):
			webnotes.conn.begin()
			if self.exists:
				self.delete_existing()
			self.save()
			self.update_modified()
			self.run_on_update()
			webnotes.conn.commit()
	
	# check modified	
	def is_modified(self):
		try:
			timestamp = webnotes.conn.sql("select modified from `tab%s` where name=%s" % (self.doc.doctype, '%s'), self.doc.name)
		except Exception ,e:
			if(e.args[0]==1146):
				return
			else:
				raise e

		if timestamp:
			self.exists = 1
			if str(timestamp[0][0]) == self.doc.modified: 
				self.log.append('%s %s, No change' % (self.doc.doctype, self.doc.name))
			else: return 1
	
	# delete existing
	def delete_existing(self):
		from webnotes.model import delete_doc
		delete_doc(self.doc.doctype, self.doc.name, force=1)

	# update modified timestamp
	def update_modified(self):
		webnotes.conn.set(self.doc, 'modified', self.modified)
		
	def save(self):
		# parent
		self.doc.save(new = 1, check_links=0)
		self.doclist = [self.doc]
		self.save_children()
			
	def save_children(self):
		for df in self.in_doclist[1:]:
			self.save_one_doc(df)
			
	def save_one_doc(self, df, as_new=1):
		d = Document(fielddata = df)
		d.save(new = as_new, check_links=0)
		self.doclist.append(d)

	def run_on_update(self):
		from webnotes.model.code import get_obj
		so = get_obj(doc=self.doc, doclist=self.doclist)
		if hasattr(so, 'on_update'):
			so.on_update()


class UpdateDocumentMerge(UpdateDocument):
	def __init__(self, in_doclist):
		self.to_update_doctype = []
		UpdateDocument.__init__(self, in_doclist)

	def delete_existing(self):
		pass
		
	def get_id(self, d):
		pass
		
	def to_update(self, d):
		return 1
	
	def child_exists(self, d):
		return self.get_id(d)
		
	def on_save(self):
		pass
	
	def save(self):
		if self.exists:
			# save main doc
			self.keep_values(self.doc)
			self.doc.save(check_links=0)
			self.doclist.append(self.doc)
			self.save_children()
			self.on_save()
			self.log.append('Updated %s' % self.doc.name)
		else:
			UpdateDocument.save(self)
		
	def save_children(self):
		for df in self.in_doclist[1:]: 
			d = Document(fielddata = df)
			
			# update doctype?
			if d.doctype in self.to_update_doctype:
				
				# update this record?
				if self.to_update(d):
				
					# is it new?
					if self.child_exists(d):
						self.keep_values(d)
						d.save(check_links=0)
						self.log.append('updated %s, %s' % (d.doctype, d.name))
					else:
						d.save(1, check_links=0)
						self.log.append('new %s' % d.doctype)
			self.doclist.append(d)

	def keep_values(self, d):
		if hasattr(self, 'get_orignal_values'):
			ov = self.get_orignal_values(d)
			if ov:
				d.fields.update(ov)


class UpdateDocTypeMapper(UpdateDocumentMerge):
	"""
		Merge `DocType Mapper`
	"""
	def __init__(self, in_doclist):
		UpdateDocumentMerge.__init__(self, in_doclist)
		self.to_update_doctype = ['Field Mapper Detail', 'Table Mapper Detail']
			
	def get_id(self, d):
		if d.doctype=='Field Mapper Detail':
			return webnotes.conn.sql("select name from `tabField Mapper Detail` where from_field=%s and to_field=%s and match_id=%s and parent=%s", (d.from_field, d.to_field, d.match_id, d.parent))
		elif d.doctype=='Table Mapper Detail':
			return webnotes.conn.sql("select name from `tabTable Mapper Detail` where from_table=%s and to_table = %s and match_id=%s and validation_logic=%s and parent=%s", (d.from_table, d.to_table, d.match_id, d.validation_logic, d.parent))
		
	def get_orignal_values(self, d):
		if d.doctype in ['Field Mapper Detail', 'Table Mapper Detail']: 
			return {'name': self.get_id(d)[0][0]}


