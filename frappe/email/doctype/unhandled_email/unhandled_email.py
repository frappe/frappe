# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class UnhandledEmail(Document):
	pass


def remove_old_unhandled_emails():
	frappe.db.sql(
		"""DELETE FROM `tabUnhandled Email`
	WHERE creation < %s""",
		frappe.utils.add_days(frappe.utils.nowdate(), -30),
	)
