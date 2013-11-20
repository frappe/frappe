# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
def on_doctype_update():
	if not webnotes.conn.sql("""show index from `tabDefaultValue` 
		where Key_name="defaultvalue_parent_defkey_index" """):
		webnotes.conn.commit()
		webnotes.conn.sql("""alter table `tabDefaultValue` 
			add index defaultvalue_parent_defkey_index(parent, defkey)""")		