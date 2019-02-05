# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""build query for doclistview and return results"""

import frappe, json
from six.moves import range
import frappe.permissions
from frappe.model.db_query import DatabaseQuery
from frappe import _
from six import text_type, string_types, StringIO

@frappe.whitelist()
@frappe.read_only()
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
	if "csrf_token" in data:
		del data["csrf_token"]

	if isinstance(data.get("filters"), string_types):
		data["filters"] = json.loads(data["filters"])
	if isinstance(data.get("fields"), string_types):
		data["fields"] = json.loads(data["fields"])
	if isinstance(data.get("docstatus"), string_types):
		data["docstatus"] = json.loads(data["docstatus"])
	if isinstance(data.get("save_user_settings"), string_types):
		data["save_user_settings"] = json.loads(data["save_user_settings"])
	else:
		data["save_user_settings"] = True

	fields = data["fields"]

	for field in fields:
		key = field.split(" as ")[0]

		if key.startswith('count('): continue

		if "." in key:
			parenttype, fieldname = key.split(".")[0][4:-1], key.split(".")[1].strip("`")
		else:
			parenttype = data.doctype
			fieldname = field.strip("`")

		df = frappe.get_meta(parenttype).get_field(fieldname)

		report_hide = df.report_hide if df else None

		# remove the field from the query if the report hide flag is set
		if report_hide:
			fields.remove(field)


	# queries must always be server side
	data.query = None

	return data

def compress(data, args = {}):
	"""separate keys and values"""
	from frappe.desk.query_report import add_total_row

	if not data: return data
	values = []
	keys = list(data[0])
	for row in data:
		new_row = []
		for key in keys:
			new_row.append(row.get(key))
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
@frappe.read_only()
def export_query():
	"""export from report builder"""
	form_params = get_form_params()
	form_params["limit_page_length"] = None
	form_params["as_list"] = True
	doctype = form_params.doctype
	add_totals_row = None
	file_format_type = form_params["file_format_type"]

	del form_params["doctype"]
	del form_params["file_format_type"]

	if 'add_totals_row' in form_params and form_params['add_totals_row']=='1':
		add_totals_row = 1
		del form_params["add_totals_row"]

	frappe.permissions.can_export(doctype, raise_exception=True)

	if 'selected_items' in form_params:
		si = json.loads(frappe.form_dict.get('selected_items'))
		form_params["filters"] = {"name": ("in", si)}
		del form_params["selected_items"]

	db_query = DatabaseQuery(doctype)
	ret = db_query.execute(**form_params)

	if add_totals_row:
		ret = append_totals_row(ret)

	data = [['Sr'] + get_labels(db_query.fields, doctype)]
	for i, row in enumerate(ret):
		data.append([i+1] + list(row))

	if file_format_type == "CSV":

		# convert to csv
		import csv
		from frappe.utils.xlsxutils import handle_html

		f = StringIO()
		writer = csv.writer(f)
		for r in data:
			# encode only unicode type strings and not int, floats etc.
			writer.writerow([handle_html(frappe.as_unicode(v)).encode('utf-8') \
				if isinstance(v, string_types) else v for v in r])

		f.seek(0)
		frappe.response['result'] = text_type(f.read(), 'utf-8')
		frappe.response['type'] = 'csv'
		frappe.response['doctype'] = doctype

	elif file_format_type == "Excel":

		from frappe.utils.xlsxutils import make_xlsx
		xlsx_file = make_xlsx(data, doctype)

		frappe.response['filename'] = doctype + '.xlsx'
		frappe.response['filecontent'] = xlsx_file.getvalue()
		frappe.response['type'] = 'binary'


def append_totals_row(data):
	if not data:
		return data
	data = list(data)
	totals = []
	totals.extend([""]*len(data[0]))

	for row in data:
		for i in range(len(row)):
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
	import json

	il = sorted(json.loads(frappe.form_dict.get('items')), reverse=True)
	doctype = frappe.form_dict.get('doctype')

	failed = []

	for i, d in enumerate(il):
		try:
			frappe.delete_doc(doctype, d)
			if len(il) >= 5:
				frappe.publish_realtime("progress",
					dict(progress=[i+1, len(il)], title=_('Deleting {0}').format(doctype), description=d),
						user=frappe.session.user)
		except Exception:
			failed.append(d)

	return failed

@frappe.whitelist()
@frappe.read_only()
def get_sidebar_stats(stats, doctype, filters=[]):
	cat_tags = frappe.db.sql("""select `tag`.parent as `category`, `tag`.tag_name as `tag`
		from `tabTag Doc Category` as `docCat`
		INNER JOIN  `tabTag` as `tag` on `tag`.parent = `docCat`.parent
		where `docCat`.tagdoc=%s
		ORDER BY `tag`.parent asc, `tag`.idx""", doctype, as_dict=1)

	return {"defined_cat":cat_tags, "stats":get_stats(stats, doctype, filters)}

@frappe.whitelist()
@frappe.read_only()
def get_stats(stats, doctype, filters=[]):
	"""get tag info"""
	import json
	tags = json.loads(stats)
	if filters:
		filters = json.loads(filters)
	stats = {}

	try:
		columns = frappe.db.get_table_columns(doctype)
	except frappe.db.InternalError:
		# raised when _user_tags column is added on the fly
		columns = []

	for tag in tags:
		if not tag in columns: continue
		try:
			tagcount = frappe.get_list(doctype, fields=[tag, "count(*)"],
				#filters=["ifnull(`%s`,'')!=''" % tag], group_by=tag, as_list=True)
				filters = filters + ["ifnull(`%s`,'')!=''" % tag], group_by = tag, as_list = True)

			if tag=='_user_tags':
				stats[tag] = scrub_user_tags(tagcount)
				stats[tag].append([_("No Tags"), frappe.get_list(doctype,
					fields=[tag, "count(*)"],
					filters=filters +["({0} = ',' or {0} = '' or {0} is null)".format(tag)], as_list=True)[0][1]])
			else:
				stats[tag] = tagcount

		except frappe.db.SQLError:
			# does not work for child tables
			pass
		except frappe.db.InternalError:
			# raised when _user_tags column is added on the fly
			pass
	return stats

@frappe.whitelist()
def get_filter_dashboard_data(stats, doctype, filters=[]):
	"""get tags info"""
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
			tagcount = frappe.get_list(doctype,
				fields=[tag["name"], "count(*)"],
				filters = filters + ["ifnull(`%s`,'')!=''" % tag["name"]],
				group_by = tag["name"],
				as_list = True)

		if tag["type"] not in ['Check','Select','Date','Datetime','Int',
			'Float','Currency','Percent'] and tag['name'] not in ['docstatus']:
			stats[tag["name"]] = list(tagcount)
			if stats[tag["name"]]:
				data =["No Data", frappe.get_list(doctype,
					fields=[tag["name"], "count(*)"],
					filters=filters + ["({0} = '' or {0} is null)".format(tag["name"])],
					as_list=True)[0][1]]
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

def build_match_conditions(doctype, user=None, as_condition=True):
	match_conditions =  DatabaseQuery(doctype, user=user).build_match_conditions(as_condition=as_condition)
	if as_condition:
		return match_conditions.replace("%", "%%")
	else:
		return match_conditions

def get_filters_cond(doctype, filters, conditions, ignore_permissions=None, with_match_conditions=False):
	if isinstance(filters, string_types):
		filters = json.loads(filters)

	if filters:
		flt = filters
		if isinstance(filters, dict):
			filters = filters.items()
			flt = []
			for f in filters:
				if isinstance(f[1], string_types) and f[1][0] == '!':
					flt.append([doctype, f[0], '!=', f[1][1:]])
				elif isinstance(f[1], (list, tuple)) and \
					f[1][0] in (">", "<", ">=", "<=", "like", "not like", "in", "not in", "between"):

					flt.append([doctype, f[0], f[1][0], f[1][1]])
				else:
					flt.append([doctype, f[0], '=', f[1]])

		query = DatabaseQuery(doctype)
		query.filters = flt
		query.conditions = conditions

		if with_match_conditions:
			query.build_match_conditions()

		query.build_filter_conditions(flt, conditions, ignore_permissions)

		cond = ' and ' + ' and '.join(query.conditions)
	else:
		cond = ''
	return cond
