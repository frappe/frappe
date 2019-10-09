# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe

from frappe.model.document import Document
from frappe import _


class MetabaseSettings(Document):
	def validate(self):
		# remove trailing slash
		self.metabase_url = self.metabase_url.rstrip('/')

		# check expiration time not less than 0
		if self.metabase_exp_time < 0:
			frappe.throw(
				_('Dashboard Expiration cannot less than 0')
			)
