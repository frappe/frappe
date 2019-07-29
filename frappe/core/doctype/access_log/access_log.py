# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document


class AccessLog(Document):
    pass


@frappe.whitelist()
def make_access_log(doctype=None, method=None, file_type=None, document=None, filters=None, report_name=None, page=None, backup=False):
    user = frappe.get_user().load_user()
    user_name = user.username if user.username else user.first_name

    if backup:
        report_name = 'Backup'

    frappe.get_doc({
        'doctype': 'Access Log',
        'name': "AL-{}-{}".format(user_name, frappe.generate_hash(length=5)),
        'user': user.first_name,
        'export_from': frappe.get_doc('DocType', doctype),
        'reference_document': document,
        'file_type': file_type,
        'report_name': report_name,
        'page': page,
        'method': method,
        'filters': filters
    }).insert()
    frappe.db.commit()
