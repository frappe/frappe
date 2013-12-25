# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

no_cache = True

def get_context():
	from webnotes.core.doctype.print_format.print_format import get_args
	return get_args()