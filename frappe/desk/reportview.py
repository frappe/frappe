# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""build query for doclistview and return results"""

import frappe, json
import frappe.permissions
from frappe.model.db_query import DatabaseQuery
from frappe import _

@frappe.whitelist()
def get():
	args = get_form_params()
	args.save_list_settings = True
	data = compress(execute(**args))

	return data

def execute(doctype, *args, **kwargs):
	return DatabaseQuery(doctype).execute(*args, **kwargs)

def get_form_params():
	"""Stringify GET request parameters."""
	data = frappe._dict(frappe.local.form_dict)

	del data["cmd"]

	if isinstance(data.get("filters"), basestring):
		data["filters"] = json.loads(data["filters"])
	if isinstance(data.get("fields"), basestring):
		data["fields"] = json.loads(data["fields"])
	if isinstance(data.get("docstatus"), basestring):
		data["docstatus"] = json.loads(data["docstatus"])

	# queries must always be server side
	data.query = None

	return data

def compress(data):
	"""separate keys and values"""
	if not data: return data
	values = []
	keys = data[0].keys()
	for row in data:
		new_row = []
		for key in keys:
			new_row.append(row[key])
		values.append(new_row)

	return {
		"keys": keys,
		"values": values
	}


@frappe.whitelist()
def save_report():
	"""save report"""

	data = frappe.local.form_dict
	if frappe.db.exists('Report', data['name']):
		d = frappe.get_doc('Report', data['name'])
	else:
		d = frappe.new_doc('Report')
		d.report_name = data['name']
		d.ref_doctype = data['doctype']

	d.report_type = "Report Builder"
	d.json = data['json']
	frappe.get_doc(d).save()
	frappe.msgprint(_("{0} is saved").format(d.name))
	return d.name

@frappe.whitelist()
def export_query():
	"""export from report builder"""
	form_params = get_form_params()
	form_params["limit_page_length"] = None
	form_params["as_list"] = True
	doctype = form_params.doctype
	del form_params["doctype"]

	frappe.permissions.can_export(doctype, raise_exception=True)

	db_query = DatabaseQuery(doctype)
	ret = db_query.execute(**form_params)

	data = [['Sr'] + get_labels(db_query.fields, doctype)]
	for i, row in enumerate(ret):
		data.append([i+1] + list(row))

	# convert to csv
	from cStringIO import StringIO
	import csv

	f = StringIO()
	writer = csv.writer(f)
	for r in data:
		# encode only unicode type strings and not int, floats etc.
		writer.writerow(map(lambda v: isinstance(v, unicode) and v.encode('utf-8') or v, r))

	f.seek(0)
	frappe.response['result'] = unicode(f.read(), 'utf-8')
	frappe.response['type'] = 'csv'
	frappe.response['doctype'] = doctype

def get_labels(fields, doctype):
	"""get column labels based on column names"""
	labels = []
	for key in fields:
		key = key.split(" as ")[0]

		if "." in key:
			parenttype, fieldname = key.split(".")[0][4:-1], key.split(".")[1].strip("`")
		else:
			parenttype = doctype
			fieldname = fieldname.strip("`")

		df = frappe.get_meta(parenttype).get_field(fieldname)
		label = df.label if df else fieldname.title()
		if label in labels:
			label = doctype + ": " + label
		labels.append(label)

	return labels

@frappe.whitelist()
def delete_items():
	"""delete selected items"""
	import json

	il = json.loads(frappe.form_dict.get('items'))
	doctype = frappe.form_dict.get('doctype')

	for d in il:
		frappe.delete_doc(doctype, d)

@frappe.whitelist()
def get_tag_catagories(doctype):
	cat_tags = frappe.db.sql("""select tag.parent as category, tag.tag_name as tag
		from `tabTag Doc Category` as docCat
		INNER JOIN  tabTag as tag on tag.parent = docCat.parent
		where docCat.tagdoc=%s
		ORDER BY tag.parent asc,tag.idx""",doctype,as_dict=1)

	return cat_tags

@frappe.whitelist()
def get_stats(stats, doctype,filters=[]):
	"""get tag info"""
	import json
	tags = json.loads(stats)
	if filters:
		filters = json.loads(filters)
	stats = {}

	columns = frappe.db.get_table_columns(doctype)
	for tag in tags:
		if not tag in columns: continue
		tagcount = execute(doctype, fields=[tag, "count(*)"],
			#filters=["ifnull(`%s`,'')!=''" % tag], group_by=tag, as_list=True)
			filters = filters + ["ifnull(`%s`,'')!=''" % tag], group_by = tag, as_list = True)

		if tag=='_user_tags':
			stats[tag] = scrub_user_tags(tagcount)
			stats[tag].append(["No Tags",execute(doctype, fields=[tag, "count(*)"], filters=filters +["({0} = ',' or {0} is null)".format(tag)],  as_list=True)[0][1]])
		else:
			stats[tag] = tagcount

	return stats

@frappe.whitelist()
def get_dash(stats, doctype,filters=[]):
	"""get tag info"""
	import json
	tags = json.loads(stats)
	if filters:
		filters = json.loads(filters)
	stats = {}

	columns = frappe.db.get_table_columns(doctype)
	for tag in tags:
		if not tag["name"] in columns: continue
		tagcount = []
		if tag["type"] not in ['Date', 'Datetime']:
			tagcount = execute(doctype, fields=[tag["name"], "count(*)"],
				filters = filters + ["ifnull(`%s`,'')!=''" % tag["name"]], group_by = tag["name"], as_list = True)

		if tag["type"] not in ['Check','Select','Date','Datetime']:
			stats[tag["name"]] = list(tagcount)
			if stats[tag["name"]]:
				data =["No Data",execute(doctype, fields=[tag["name"], "count(*)"], filters=filters + ["({0} = '' or {0} is null)".format(tag["name"])],  as_list=True)[0][1]]
				if data and data[1]!=0:

					stats[tag["name"]].append(data)
		else:
			stats[tag["name"]] = tagcount

	return stats

def scrub_user_tags(tagcount):
	"""rebuild tag list for tags"""
	rdict = {}
	tagdict = dict(tagcount)
	for t in tagdict:
		if not t:
			continue
		alltags = t.split(',')
		for tag in alltags:
			if tag:
				if not tag in rdict:
					rdict[tag] = 0

				rdict[tag] += tagdict[t]

	rlist = []
	for tag in rdict:
		rlist.append([tag, rdict[tag]])

	return rlist

# used in building query in queries.py
def get_match_cond(doctype):
	cond = DatabaseQuery(doctype).build_match_conditions()
	return ((' and ' + cond) if cond else "").replace("%", "%%")

def build_match_conditions(doctype, as_condition=True):
	match_conditions =  DatabaseQuery(doctype).build_match_conditions(as_condition=as_condition)
	if as_condition:
		return match_conditions.replace("%", "%%")
	else:
		return match_conditions
