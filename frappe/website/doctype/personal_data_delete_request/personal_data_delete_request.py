# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.desk.form.linked_with import get_linked_doctypes
from frappe.website.doctype.personal_data_download_request.personal_data_download_request import get_unlinked_user_data, get_linked_user_data

class PersonalDataDeleteRequest(Document):
	pass