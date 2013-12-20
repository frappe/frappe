# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import webnotes
import os, json
import types

from webnotes import _
from webnotes.modules import scrub, get_module_path
from webnotes.utils import flt, cint
import webnotes.widgets.reportview

@webnotes.whitelist()
def get_script(report_name):
	report = webnotes.doc("Report", report_name)
	
	module = webnotes.conn.get_value("DocType", report.ref_doctype, "module")
	module_path = get_module_path(module)
	report_folder = os.path.join(module_path, "report", scrub(report.name))
	script_path = os.path.join(report_folder, scrub(report.name) + ".js")
	
	script = None
	if os.path.exists(script_path):
		with open(script_path, "r") as script:
			script = script.read()
	
	if not script and report.javascript:
		script = report.javascript
	
	if not script:
		script = "wn.query_reports['%s']={}" % report_name
		
	# load translations
	if webnotes.lang != "en":
		webnotes.response["__messages"] = webnotes.get_lang_dict("report", report_name)
		
	return script

@webnotes.whitelist()
def run(report_name, filters=None):
	
	report = webnotes.doc("Report", report_name)
	
	if filters and isinstance(filters, basestring):
		filters = json.loads(filters)

	if not webnotes.has_permission(report.ref_doctype, "report"):
		webnotes.msgprint(_("Must have report permission to access this report."), 
			raise_exception=True)
	
	if report.report_type=="Query Report":
		if not report.query:
			webnotes.msgprint(_("Must specify a Query to run"), raise_exception=True)
	
	
		if not report.query.lower().startswith("select"):
			webnotes.msgprint(_("Query must be a SELECT"), raise_exception=True)
		
		result = [list(t) for t in webnotes.conn.sql(report.query, filters)]
		columns = [c[0] for c in webnotes.conn.get_description()]
	else:
		module = webnotes.conn.get_value("DocType", report.ref_doctype, "module")
		if report.is_standard=="Yes":
			method_name = webnotes.local.module_app[scrub(module)] + "." + scrub(module) \
				+ ".report." + scrub(report.name) + "." + scrub(report.name) + ".execute"
			columns, result = webnotes.get_attr(method_name)(filters or {})
	
	result = get_filtered_data(report.ref_doctype, columns, result)
	
	if cint(report.add_total_row) and result:
		result = add_total_row(result, columns)
	
	return {
		"result": result,
		"columns": columns
	}
	
def add_total_row(result, columns):
	total_row = [""]*len(columns)
	has_percent = []
	for row in result:
		for i, col in enumerate(columns):
			col = col.split(":")
			if len(col) > 1:
				if col[1] in ["Currency", "Int", "Float", "Percent"] and flt(row[i]):
					total_row[i] = flt(total_row[i]) + flt(row[i])
				if col[1] == "Percent" and i not in has_percent:
					has_percent.append(i)
	
	for i in has_percent:
		total_row[i] = total_row[i] / len(result)
	
	first_col = columns[0].split(":")
	if len(first_col) > 1 and first_col[1] not in ["Currency", "Int", "Float", "Percent"]:
		total_row[0] = "Total"
		
	result.append(total_row)
	return result

def get_filtered_data(ref_doctype, columns, data):
	result = []

	linked_doctypes = get_linked_doctypes(columns)
	match_filters = get_user_match_filters(linked_doctypes, ref_doctype)
	
	if match_filters:
		matched_columns = get_matched_columns(linked_doctypes, match_filters)
		for row in data:
			match = True
			for col, idx in matched_columns.items():
				if row[idx] not in match_filters[col]:
					match = False

			if match:
				result.append(row)
	else:
		for row in data:
			result.append(row)

	return result

def get_linked_doctypes(columns):
	linked_doctypes = {}

	for idx, col in enumerate(columns):
		col = col.split(":")
		if len(col) > 1 and col[1].startswith("Link"):
			link_dt = col[1].split("/")[1]
			linked_doctypes[link_dt] = idx

	return linked_doctypes

def get_user_match_filters(doctypes, ref_doctype):
	match_filters = {}
	doctypes_meta = {}
	tables = []

	for dt in doctypes:
		tables.append("`tab" + dt + "`")
		doctypes_meta[dt] = webnotes.model.doctype.get(dt)

	webnotes.local.reportview_tables = tables
	webnotes.local.reportview_doctypes = doctypes_meta

	for dt in doctypes:
		match_filters.update(webnotes.widgets.reportview.build_match_conditions(dt, 
			None, False))

	return match_filters

def get_matched_columns(linked_doctypes, match_filters):
	if "owner" in match_filters:
		match_filters["profile"] = match_filters["owner"]

	col_idx_map = {}
	for dt, idx in linked_doctypes.items():
		link_field = dt.lower().replace(" ", "_")
		if link_field in match_filters:
			col_idx_map[link_field] = idx

	return col_idx_map