# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

def get_context():
	return webnotes.doc("Blog Settings", "Blog Settings").fields