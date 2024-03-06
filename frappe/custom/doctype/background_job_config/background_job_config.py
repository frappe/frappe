# -*- coding: utf-8 -*-
# Copyright (c) 2021, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class BackgroundJobConfig(Document):
	@staticmethod
	def get_invalidate_key():
		return f'invalidate_background_job_config'

	# def invalidate(self):
	# 	from latte.utils.caching import invalidate
	# 	invalidate(self.get_invalidate_key())

	# on_update = invalidate
	# on_trash = invalidate