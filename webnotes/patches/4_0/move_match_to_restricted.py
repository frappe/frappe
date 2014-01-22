# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

def execute():
	webnotes.reload_doc("core", "doctype", "docperm")
	webnotes.conn.sql("""update `tabDocPerm` set restricted=1 where `match`='owner'""")