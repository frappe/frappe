import webnotes

from webnotes.utils import cint, flt
from webnotes.model.doc import Document
from webnotes.model.code import get_obj
from webnotes import session, msgprint, errprint

sql = webnotes.conn.sql

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

	def execute_server(self, arg=''):
		if webnotes.user.name=='Guest':
			raise Exception, 'Guest cannot call execute test!'
		exec(self.doc.script)
