# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
import json
from six import string_types

@frappe.whitelist()
def get_coords(doctype, names):
	'''Get list of coordinates in form
    returns {names: ['latitude', 'longitude']}'''

    if isinstance(names, string_types):
        names = json.loads(names)

    coords = frappe.db.get_list(doctype, filters= {
        'name': ('in', names)
    }, fields=['latitude', 'longitude', 'name as docname'])

    out = frappe._dict()
    for i in coords:
        out[i.docname] = out.get(i.docname, [])
        out[i.docname].append(i.latitude)
        out[i.docname].append(i.longitude)

    return out
