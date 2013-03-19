# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.utils import get_base_path
import os

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
def get_print_style():
	name = webnotes.conn.get_default("print_style") or "Standard"
	css = webnotes.conn.get_value("Print Style", name, "css")
	if css: 
		return css

	# find in local
	path = os.path.join(get_base_path(), "lib", "core", "doctype", "print_style", 
		"standard", name.lower() + ".css")
	if os.path.exists(path):
		with open(path, "r") as psfile:
			return psfile.read()
	else:
		return ""
	
	