# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import webnotes
from webnotes import _
import json

@webnotes.whitelist()
def update_event(args, field_map):
	args = webnotes._dict(json.loads(args))
	field_map = webnotes._dict(json.loads(field_map))
	w = webnotes.bean(args.doctype, args.name)
	w.doc.fields[field_map.start] = args[field_map.start]
	w.doc.fields[field_map.end] = args[field_map.end]
	w.save()

