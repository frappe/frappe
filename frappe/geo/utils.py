# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe

from pymysql import InternalError




@frappe.whitelist()
def get_coords(doctype, filters, type):
    '''Get list of coordinates in form
    returns {name, location} with location being a geojson string'''
    filters_sql = get_coords_conditions(doctype, filters)[4:]
    out = None
    if type == 'coordinates':
        out = return_coordinates(doctype, filters_sql)
    if type == 'location_field':
        out = return_location(doctype, filters_sql)
    return out

def return_location(doctype, filters_sql):
    if filters_sql:
        try:
            coords = frappe.db.sql("""SELECT * FROM `tab{}`  WHERE {}""".format(doctype, filters_sql), as_dict=True)
        except InternalError:
            frappe.msgprint(frappe._('This Doctype did not contain location field'))
            return
    else:
        coords = frappe.get_all(doctype, fields = ['name', 'location'])
    return coords

def return_coordinates(doctype, filters_sql):
    if filters_sql:
        try:
            coords = frappe.db.sql("""SELECT * FROM `tab{}`  WHERE {}""".format(doctype, filters_sql), as_dict=True)
        except InternalError:
            frappe.msgprint(frappe._('This Doctype did not contains latitude and longitude fields'))
            return
    else:
        coords = frappe.get_all(doctype, fields=['name', 'latitude', 'longitude'])
    out = frappe._dict()
    for i in coords:
        out[i.name] = out.get(i.docname, [])
        out[i.name].append(i.latitude)
        out[i.name].append(i.longitude)
    return out


def get_coords_conditions(doctype, filters=None):
    """Returns SQL conditions with user permissions and filters for event queries"""
    from frappe.desk.reportview import get_filters_cond
    if not frappe.has_permission(doctype):
        frappe.throw(frappe._("Not Permitted"), frappe.PermissionError)

    return get_filters_cond(doctype, filters, [], with_match_conditions=True)
