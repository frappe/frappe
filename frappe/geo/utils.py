# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils.data import flt


@frappe.whitelist()
def get_coords(doctype, filters, type):
	"""Get a geojson dict representing a doctype."""
	filters_sql = get_coords_conditions(doctype, filters)[4:]
	meta = frappe.get_meta(doctype)
	title_field = meta.title_field if meta.show_title_field_in_link else None

	coords = None
	if type == "location_field":
		coords = return_location(doctype, filters_sql, title_field)
	elif type == "coordinates":
		coords = return_coordinates(doctype, filters_sql, title_field)

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


def return_location(doctype, filters_sql, title_field=None):
	"""Get name and location fields for Doctype."""
	fields = ["name", "location"]
	if title_field:
		fields.append(f"{title_field} as title")

	if filters_sql:
		try:
			coords = frappe.db.sql(
				f"""SELECT {", ".join(fields)} FROM `tab{doctype}`  WHERE {filters_sql}""", as_dict=True
			)
		except frappe.db.InternalError:
			frappe.msgprint(frappe._("This Doctype does not contain location fields"), raise_exception=True)
			return
	else:
		coords = frappe.get_all(doctype, fields=fields)
	return coords


def return_coordinates(doctype, filters_sql, title_field=None):
	"""Get name, latitude and longitude fields for Doctype."""
	fields = ["name", "latitude", "longitude"]
	if title_field:
		fields.append(f"{title_field} as title")

	if filters_sql:
		try:
			coords = frappe.db.sql(
				f"""SELECT {", ".join(fields)} FROM `tab{doctype}`  WHERE {filters_sql}""",
				as_dict=True,
			)
		except frappe.db.InternalError:
			frappe.msgprint(
				frappe._("This Doctype does not contain latitude and longitude fields"), raise_exception=True
			)
			return
	else:
		coords = frappe.get_all(doctype, fields=fields)
	return coords


def get_coords_conditions(doctype, filters=None):
	"""Returns SQL conditions with user permissions and filters for event queries."""
	from frappe.desk.reportview import get_filters_cond

	if not frappe.has_permission(doctype):
		frappe.throw(frappe._("Not Permitted"), frappe.PermissionError)

	return get_filters_cond(doctype, filters, [], with_match_conditions=True)
