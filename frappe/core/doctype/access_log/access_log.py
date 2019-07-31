# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document


class AccessLog(Document):
    pass


@frappe.whitelist()
def make_access_log(
        doctype=None, document=None,
        method=None, file_type=None,
        report_name=None, _filters=None,
        page=None, backup=False
    ):

    user = frappe.get_user().load_user()
    user_name = user.username if user.username else user.first_name

    if backup:
        report_name = 'Backup'

    doc = frappe.get_doc({
        'doctype': 'Access Log',
        'name': "AL-{}-{}".format(user_name, frappe.generate_hash(length=5)),
        'user': user.email if user.email else user.first_name,
        'export_from': doctype,
        'reference_document': document,
        'file_type': file_type,
        'report_name': report_name,
        'page': page,
        'method': method,
        '_filters': _filters
    })
    doc.insert()

    # `frappe.db.commit` added because insert doesnt `commit` when called in GET requests
    frappe.db.commit()
