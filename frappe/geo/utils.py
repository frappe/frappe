# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""build query for mapview and return results"""

import json

import frappe
from frappe import _
from frappe.desk.reportview import validate_filters
from frappe.model.base_document import get_controller
from frappe.model.db_query import DatabaseQuery
from frappe.model.utils import is_virtual_doctype


@frappe.whitelist()
@frappe.read_only()
def get_coords(doctype, filters, type):
	args = frappe._dict({"doctype": doctype})

	if filters:
		if isinstance(filters, str):
			args.filters = json.loads(filters)
		else:
			args.filters = filters
		validate_filters(args, args.filters)

	title_field = frappe.get_meta(doctype).title_field
	args.fields = get_fields_from_type(type, title_field)
	# If virtual doctype, get data from controller get_list method
	if is_virtual_doctype(args.doctype):
		controller = get_controller(args.doctype)
		data = controller.get_list(args)
	else:
		data = execute(**args)
	return convert_to_geojson(type, data, title_field)


def convert_to_geojson(type, coords, title_field="name"):
	"""Converts GPS coordinates to geoJSON string."""
	geojson = {"type": "FeatureCollection", "features": None}

	if type == "location_field":
		geojson["features"] = merge_location_features_in_one(coords, title_field)
	elif type == "coordinates":
		geojson["features"] = create_gps_markers(coords, title_field)

	return geojson


def merge_location_features_in_one(coords, title_field="name"):
	"""Merging all features from location field."""
	geojson_dict = []
	for element in coords:
		geojson_loc = frappe.parse_json(element["location"])
		if not geojson_loc:
			continue
		for coord in geojson_loc["features"]:
			coord["properties"]["name"] = element[title_field]
			geojson_dict.append(coord)

	return geojson_dict


def create_gps_markers(coords, title_field="name"):
	"""Build Marker based on latitude and longitude."""
	geojson_dict = []
	for element in coords:
		node = {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": None}}
		node["properties"]["name"] = element[title_field]
		node["geometry"]["coordinates"] = [
			element["longitude"],
			element["latitude"],
		]  # geojson needs it reverse!
		geojson_dict.append(node)

	return geojson_dict


def execute(doctype, *args, **kwargs):
	return DatabaseQuery(doctype).execute(*args, **kwargs)


def get_fields_from_type(type, title_field="name"):
	if type == "location_field":
		return [title_field, "location"]
	elif type == "coordinates":
		return [title_field, "latitude", "longitude"]
	else:
		frappe.throw(_("Invalid type") + f": {type}", frappe.DataError)
