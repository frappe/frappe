# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

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

	script_path = os.path.join(get_module_path(webnotes.conn.get_value("DocType", report.ref_doctype, "module")),
		"report", scrub(report.name), scrub(report.name) + ".js") 
	
	if os.path.exists(script_path):
		with open(script_path, "r") as script:
			return script.read()
	else:
		return "wn.query_reports['%s']={}" % report_name

@webnotes.whitelist()
def run(report_name, filters=None):
	report = webnotes.doc("Report", report_name)

	if not webnotes.has_permission(report.ref_doctype, "report"):
		webnotes.msgprint(_("Must have report permission to access this report."), 
			raise_exception=True)
	
	if report.report_type=="Query Report":
		if not report.query:
			webnotes.msgprint(_("Must specify a Query to run"), raise_exception=True)
	
	
		if not report.query.lower().startswith("select"):
			webnotes.msgprint(_("Query must be a SELECT"), raise_exception=True)
		
		result = [list(t) for t in webnotes.conn.sql(report.query)]
		columns = [c[0] for c in webnotes.conn.get_description()]
	else:
		if filters:
			filters = json.loads(filters)
		
		method_name = scrub(webnotes.conn.get_value("DocType", report.ref_doctype, "module")) \
			+ ".report." + scrub(report.name) + "." + scrub(report.name) + ".execute"
		columns, result = webnotes.get_method(method_name)(filters or {})

	result = get_filtered_data(report.ref_doctype, columns, result)
	
	if cint(report.add_total_row) and result:
		result = add_total_row(result, columns)
	
	return {
		"result": result,
		"columns": columns
	}
	
def add_total_row(result, columns):
	total_row = [""]*len(columns)
	for row in result:
		for i, col in enumerate(columns):
			col = col.split(":")
			if len(col) > 1 and col[1] in ["Currency", "Int", "Float"] and flt(row[i]):
				total_row[i] = flt(total_row[i]) + flt(row[i])
	first_col = columns[0].split(":")
	if len(first_col) > 1 and first_col[1] not in ["Currency", "Int", "Float"]:
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
		if "Link" in col:
			link_dt = col.split(":")[1].split("/")[1]
			linked_doctypes[link_dt] = idx

	return linked_doctypes

def get_user_match_filters(doctypes, ref_doctype):
	match_filters = {}
	doctypes_meta = {}
	tables = []
	doctypes[ref_doctype] = None

	for dt in doctypes:
		tables.append("`tab" + dt + "`")
		doctypes_meta[dt] = webnotes.model.doctype.get(dt)

	webnotes.widgets.reportview.tables = tables
	webnotes.widgets.reportview.doctypes = doctypes_meta

	for dt in doctypes:
		match_filters = webnotes.widgets.reportview.build_match_conditions(dt, 
			None, False, match_filters)

	return match_filters

def get_matched_columns(linked_doctypes, match_filters):
	col_idx_map = {}
	for dt, idx in linked_doctypes.items():
		link_field = dt.lower().replace(" ", "_")
		if link_field in match_filters:
			col_idx_map[link_field] = idx

	return col_idx_map