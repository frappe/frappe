# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model import get_permitted_fields
from frappe.utils.data import flt


@frappe.whitelist()
def get_coords(doctype: str, filters: str | list | dict | None, type: str):
	"""Get a geojson dict representing a doctype."""
	coords = None
	if type == "location_field":
		coords = return_location(doctype, filters)
	elif type == "coordinates":
		coords = return_coordinates(doctype, filters)

	return convert_to_geojson(type, coords)


def convert_to_geojson(type, coords):
	"""Converts GPS coordinates to geoJSON string."""
	geojson = {"type": "FeatureCollection", "features": None}

	if type == "location_field":
		geojson["features"] = merge_location_features_in_one(coords)
	elif type == "coordinates":
		geojson["features"] = create_gps_markers(coords)

	return geojson


def merge_location_features_in_one(coords):
	"""Merging all features from location field."""
	geojson_dict = []
	for element in coords:
		geojson_loc = frappe.parse_json(element["location"])
		if not geojson_loc:
			continue
		for coord in geojson_loc["features"]:
			coord["properties"]["name"] = element["name"]
			coord["properties"]["title"] = element.get("title")
			geojson_dict.append(coord.copy())

	return geojson_dict


def create_gps_markers(coords):
	"""Build Marker based on latitude and longitude."""
	return [
		{
			"type": "Feature",
			"properties": {
				"name": i.name,
				"title": i.get("title"),
			},
			"geometry": {
				"type": "Point",
				"coordinates": [flt(i.longitude), flt(i.latitude)],  # geojson needs it reverse!
			},
		}
		for i in coords
	]


def return_location(doctype, filters):
	"""Get name and location fields for Doctype."""
	meta = frappe.get_meta(doctype)
	if not meta.has_field("location"):
		frappe.throw(frappe._("This Doctype does not contain location fields"))

	if "location" not in get_permitted_fields(doctype):
		frappe.throw(frappe._("You are not permitted to read the location field"), frappe.PermissionError)

	fields = ["name", "location"]
	if title_field := get_title_field(meta):
		fields.append(f"{title_field} as title")

	return frappe.get_list(doctype, filters=filters, fields=fields)


def return_coordinates(doctype, filters):
	"""Get name, latitude and longitude fields for Doctype."""
	meta = frappe.get_meta(doctype)
	if not (meta.has_field("latitude") and meta.has_field("longitude")):
		frappe.throw(frappe._("This Doctype does not contain latitude and longitude fields"))

	if not {"latitude", "longitude"}.issubset(get_permitted_fields(doctype)):
		frappe.throw(
			frappe._("You are not permitted to read the latitude and longitude fields"),
			frappe.PermissionError,
		)

	fields = ["name", "latitude", "longitude"]
	if title_field := get_title_field(meta):
		fields.append(f"{title_field} as title")

	return frappe.get_list(doctype, filters=filters, fields=fields)


def get_title_field(meta):
	return meta.title_field if meta.show_title_field_in_link else None
