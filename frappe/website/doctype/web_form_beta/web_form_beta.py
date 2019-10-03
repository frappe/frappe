# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.website_generator import WebsiteGenerator

class WebFormBeta(WebsiteGenerator):
	website = frappe._dict(
		no_cache = 1
	)


def get_fields():
	pass
