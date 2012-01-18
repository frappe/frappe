# Please edit this list and import only required elements
import webnotes

from webnotes.utils import cint, flt
from webnotes.model.doc import Document
from webnotes.model.code import get_obj
from webnotes import session, form, is_testing, msgprint, errprint

get_value = webnotes.conn.get_value
	
# -----------------------------------------------------------------------------------------


class DocType:
	def __init__(self, doc, doclist):
		self.doc = doc
		self.doclist = doclist

	def on_update(self):
		# clear cache on save
		webnotes.conn.sql("delete from __SessionCache")

	def upload_many(self,form):
		pass

	def upload_callback(self,form):
		pass
		
	def execute_test(self, arg=''):
		if webnotes.user.name=='Guest':
			raise Exception, 'Guest cannot call execute test!'
		out = ''
		exec(arg and arg or self.doc.test_code)
		webnotes.msgprint('that worked!')
		return out
