# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

def get_context(context):
	# get settings from site config
	if webnotes.conf.get("fb_app_id"):
		return { "fb_app_id": webnotes.conf.fb_app_id }
