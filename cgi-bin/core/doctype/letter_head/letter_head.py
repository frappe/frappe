# Please edit this list and import only required elements
import webnotes
from webnotes import msgprint

sql = webnotes.conn.sql

class DocType:
	def __init__(self, doc, doclist=[]):
		self.doc = doc
		self.doclist = doclist
	
	#
	# on update
	#
	def on_update(self):
		# clear the cache so that the new letter head is uploaded
		sql("delete from __SessionCache")

		self.set_as_default()	
		
	#
	# this is default, un-set everyone else
	#
	def set_as_default(self):
		from webnotes.utils import set_default
		if self.doc.is_default:
			sql("update `tabLetter Head` set is_default=0 where name != %s", self.doc.name)
			set_default('letter_head', self.doc.name)

			# update control panel - so it loads new letter directly
			webnotes.conn.set_value('Control Panel', None, 'letter_head', self.doc.content)