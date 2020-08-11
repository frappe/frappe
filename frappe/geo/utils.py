# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json

import frappe

from pymysql import InternalError


@frappe.whitelist()
def get_coords(doctype, filters, type):
    '''Get list of coordinates in form
    returns {names: ['latitude', 'longitude']} or location type'''
    filters_sql = get_coords_conditions(doctype, filters)[4:]
    out = None
    if type == 'coordinates':
        out = return_coordinates(doctype, filters_sql)
    if type == 'location_field':
        out = return_location(doctype, filters_sql)
    return out


def convert_to_geo_json(coords_list):
    handled_geo_json_dict = []
    for element in coords_list:
        handled_geo_json = json.loads(element['location'])
        for coord in handled_geo_json['features']:
            coord['properties']['name'] = element['name']
            handled_geo_json_dict.append(coord.copy())
            print(handled_geo_json['features'])
    handled_geo_json = {"type": "FeatureCollection", "features": handled_geo_json_dict}
    return handled_geo_json


def return_location(doctype, filters_sql):
    if filters_sql:
        try:
            coords = frappe.db.sql("""SELECT name,location FROM `tab{}`  WHERE {}""".format(doctype, filters_sql), as_dict=True)
        except InternalError:
            frappe.msgprint(frappe._('This Doctype did not contains latitude and longitude fields'))
            return
    else:
        coords = frappe.get_all(doctype, fields=['location', 'name'])
    handled_geo_json = convert_to_geo_json(coords)
    return handled_geo_json


def return_coordinates(doctype, filters_sql):
    handled_geo_json = {"type": "FeatureCollection", "features": None}
    if filters_sql:
        try:
            coords = frappe.db.sql("""SELECT * FROM `tab{}`  WHERE {}""".format(doctype, filters_sql), as_dict=True)
        except InternalError:
            frappe.msgprint(frappe._('This Doctype did not contains latitude and longitude fields'))
            return
    else:
        coords = frappe.get_all(doctype, fields=['name', 'latitude', 'longitude'])
    out_list = []
    for i in coords:
        node = {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": None}}
        node['properties']['name'] = i.name
        node['geometry']['coordinates'] = [i.latitude, i.longitude]
        out_list.append(node.copy())
    handled_geo_json['features'] = out_list
    print(handled_geo_json)
    return handled_geo_json


def get_coords_conditions(doctype, filters=None):
    """Returns SQL conditions with user permissions and filters for event queries"""
    from frappe.desk.reportview import get_filters_cond
    if not frappe.has_permission(doctype):
        frappe.throw(frappe._("Not Permitted"), frappe.PermissionError)

    return get_filters_cond(doctype, filters, [], with_match_conditions=True)
