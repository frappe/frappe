# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import socket
from frappe.model.document import Document

class ClusterConfiguration(Document):
	def before_save(self):
		if not self.site_ip:
			try:
				self.site_ip = socket.gethostbyname(self.site_name)
			except socket.gaierror:
				frappe.throw('Cannot fetch IP Address for site {self.site_name}, Kindly manually enter the same'.format(self=self))
