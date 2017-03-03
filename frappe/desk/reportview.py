# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""build query for doclistview and return results"""

import frappe, json
import frappe.permissions
from frappe.model.db_query import DatabaseQuery
from frappe import _
from frappe.model.utils.list_settings import get_list_settings, update_list_settings

@frappe.whitelist()
def get():
	args = get_form_params()

	data = compress(execute(**args), args = args)

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
	if isinstance(data.get("save_list_settings"), basestring):
		data["save_list_settings"] = json.loads(data["save_list_settings"])
	else:
		data["save_list_settings"] = True


	# queries must always be server side
	data.query = None

	return data

def compress(data, args = {}):
	"""separate keys and values"""
	from frappe.desk.query_report import add_total_row

	if not data: return data
	values = []
	keys = data[0].keys()
	for row in data:
		new_row = []
		for key in keys:
			new_row.append(row[key])
		values.append(new_row)

	if args.get("add_total_row"):
		meta = frappe.get_meta(args.doctype)
		values = add_total_row(values, keys, meta)

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
	add_totals_row = None

	del form_params["doctype"]

	if 'add_totals_row' in form_params and form_params['add_totals_row']=='1':
		add_totals_row = 1
		del form_params["add_totals_row"]

	frappe.permissions.can_export(doctype, raise_exception=True)

	db_query = DatabaseQuery(doctype)
	ret = db_query.execute(**form_params)

	if add_totals_row:
		ret = append_totals_row(ret)

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

def append_totals_row(data):
	if not data:
		return data
	data = list(data)
	totals = []
	totals.extend([""]*len(data[0]))

	for row in data:
		for i in xrange(len(row)):
			if isinstance(row[i], (float, int)):
				totals[i] = (totals[i] or 0) + row[i]
	data.append(totals)

	return data

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

	il = json.loads(frappe.form_dict.get('items'))
	doctype = frappe.form_dict.get('doctype')

	for i, d in enumerate(il):
		try:
			frappe.delete_doc(doctype, d)
			if len(il) >= 5:
				frappe.publish_realtime("progress",
					dict(progress=[i+1, len(il)], title=_('Deleting {0}').format(doctype)),
					user=frappe.session.user)
		except Exception:
			pass

@frappe.whitelist()
def get_sidebar_stats(stats, doctype, filters=[]):
	cat_tags = frappe.db.sql("""select tag.parent as category, tag.tag_name as tag
		from `tabTag Doc Category` as docCat
		INNER JOIN  tabTag as tag on tag.parent = docCat.parent
		where docCat.tagdoc=%s
		ORDER BY tag.parent asc,tag.idx""",doctype,as_dict=1)

	return {"defined_cat":cat_tags, "stats":get_stats(stats, doctype, filters)}

@frappe.whitelist()
def get_stats(stats, doctype, filters=[]):
	"""get tag info"""
	tags = json.loads(stats)
	if filters:
		filters = json.loads(filters)
	stats = {}

	columns = frappe.db.get_table_columns(doctype)
	for tag in tags:
		if not tag in columns: continue
		tagcount = frappe.get_list(doctype, fields=[tag, "count(*)"],
			#filters=["ifnull(`%s`,'')!=''" % tag], group_by=tag, as_list=True)
			filters = filters + ["ifnull(`%s`,'')!=''" % tag], group_by = tag, as_list = True)

		if tag=='_user_tags':
			stats[tag] = scrub_user_tags(tagcount)
			stats[tag].append(["No Tags", frappe.get_list(doctype,
				fields=[tag, "count(*)"],
				filters=filters +["({0} = ',' or {0} is null)".format(tag)], as_list=True)[0][1]])
		else:
			stats[tag] = tagcount

	return stats

@frappe.whitelist()
def get_filter_dashboard_data(stats, doctype, filters=[], list_settings={}):
	"""get tags info"""
	tags = json.loads(stats)
	if list_settings:
		list_settings = frappe._dict(json.loads(list_settings))
	if filters:
		filters = json.loads(filters)

	filters = add_age_to_filter(filters, doctype, list_settings.dashboard_age_fieldname, list_settings.dashboard_age_value)
	# process out columns 
	column_list = []
	columns = frappe.db.get_table_columns(doctype)
	for tag in tags:
		if tag["name"] in columns and tag["type"] not in ['Date', 'Datetime']:
			column_list.append({"name":tag["name"], "type":tag["type"]})
	stats = {}

	if filters:
		conditions = []
		DatabaseQuery(doctype).build_filter_conditions(filters, conditions)
		if conditions:
			conditions = ' where ' + ' and '.join(conditions)
		else:
			conditions = ""
	
		frappe.db.sql("""CREATE temporary TABLE tempfiltered ENGINE=myisam as
			(select {0} from `tab{1}` 
	            {2}
				order by modified desc);
		""".format(", ".join([x["name"] for x in column_list]), doctype, conditions))
	
	for column in column_list:
		if filters:
			tagcount = frappe.db.sql("""select {0}, count(*) from tempfiltered
			where ifnull({0},'')!='' group by {0}""".format(column["name"]),as_list=1)
		else:
			tagcount = frappe.get_list(doctype, 
				fields=[column["name"], "count(*)"],
				filters = filters + ["ifnull(`%s`,'')!=''" % column["name"]], 
				group_by = column["name"], 
				as_list = True)

		if column["type"] not in ['Check','Select','Int',
			'Float','Currency','Percent'] and tag['name'] not in ['docstatus']:
			stats[column["name"]] = list(tagcount)
			if stats[column["name"]]:
				if filters:
					data = frappe.db.sql("""select "No Data", count(*) 
						from tempfiltered 
						where ifnull({0},'')='' """.format(column["name"]), as_list=1)[0]
				else:
					data =["No Data", frappe.get_list(doctype, 
						fields=[column["name"], "count(*)"], 
						filters=filters + ["({0} = '' or {0} is null)".format(column["name"])], 
						as_list=True)[0][1]]
				if data and data[1]!=0:
					stats[column["name"]].append(data)
		else:
			stats[column["name"]] = tagcount
	if filters:
		frappe.db.sql("drop table tempfiltered")
	update_dashboard_settings(list_settings.list_settings_key or doctype, list_settings.dashboard_age_fieldname, list_settings.dashboard_age_value)
	return stats

def add_age_to_filter(filters, doctype, field, date):
	from frappe.utils import now_datetime, add_days, add_months, add_years, get_datetime_str

	if date == "All Time":
		return filters
	today = now_datetime()
	selected_dates = {
	'Last 7 Days': [add_days(today,-6)],
	'Last 30 Days': [add_days(today,-29)],
	'This Month': [add_days(today, -today.day)],
	'Last Month': [add_months(add_days(today, -today.day),-1), add_days(today, -today.day-1)],
	'Last 3 Months': [add_months(add_days(today, -today.day),-3)],
	'This Financial Year': [frappe.db.get_default("year_start_date"),frappe.db.get_default("year_end_date")],
	'Last Financial Year': [add_years(frappe.db.get_default("year_start_date"), -1),
		add_years(frappe.db.get_default("year_end_date"), -1)]
	}[date]

	if len(selected_dates)==2:
		return filters + [[ doctype, field,">", get_datetime_str(selected_dates[0]) ],
			[ doctype, field, "<", get_datetime_str(selected_dates[1]) ]]
	else:
		return filters + [[ doctype, field, ">", get_datetime_str(selected_dates[0]) ]]

def update_dashboard_settings(doctype, dashboard_age_fieldname, dashboard_age_value):
	list_settings = json.loads(get_list_settings(doctype) or '{}')
	list_settings['dashboard_age_fieldname'] = dashboard_age_fieldname
	list_settings['dashboard_age_value'] = dashboard_age_value

	update_list_settings(doctype, list_settings)

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

def get_filters_cond(doctype, filters, conditions):
	if filters:
		flt = filters
		if isinstance(filters, dict):
			filters = filters.items()
			flt = []
			for f in filters:
				if isinstance(f[1], basestring) and f[1][0] == '!':
					flt.append([doctype, f[0], '!=', f[1][1:]])
				else:
					value = frappe.db.escape(f[1]) if isinstance(f[1], basestring) else f[1]
					flt.append([doctype, f[0], '=', value])

		query = DatabaseQuery(doctype)
		query.filters = flt
		query.conditions = conditions
		query.build_filter_conditions(flt, conditions)

		cond = ' and ' + ' and '.join(query.conditions)
	else:
		cond = ''
	return cond

