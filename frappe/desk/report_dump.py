# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import copy
import json

from six.moves import range

import frappe


@frappe.whitelist()
def get_data(doctypes, last_modified):
	data_map = {}
	for dump_report_map in frappe.get_hooks().dump_report_map:
		data_map.update(frappe.get_attr(dump_report_map))

	out = {}

	doctypes = json.loads(doctypes)
	last_modified = json.loads(last_modified)

	for d in doctypes:
		args = copy.deepcopy(data_map[d])
		dt = d.find("[") != -1 and d[: d.find("[")] or d
		out[dt] = {}

		if args.get("from"):
			modified_table = "item."
		else:
			modified_table = ""

		conditions = order_by = ""
		table = args.get("from") or ("`tab%s`" % dt)

		if d in last_modified:
			if not args.get("conditions"):
				args["conditions"] = []
			args["conditions"].append(modified_table + "modified > '" + last_modified[d] + "'")
			out[dt]["modified_names"] = frappe.db.sql_list(
				"""select %sname from %s
				where %smodified > %s"""
				% (modified_table, table, modified_table, "%s"),
				last_modified[d],
			)

		if args.get("force_index"):
			conditions = " force index (%s) " % args["force_index"]
		if args.get("conditions"):
			conditions += " where " + " and ".join(args["conditions"])
		if args.get("order_by"):
			order_by = " order by " + args["order_by"]

		out[dt]["data"] = [
			list(t)
			for t in frappe.db.sql(
				"""select %s from %s %s %s""" % (",".join(args["columns"]), table, conditions, order_by)
			)
		]

		# last modified
		modified_table = table
		if "," in table:
			modified_table = " ".join(table.split(",")[0].split(" ")[:-1])

		tmp = frappe.db.sql(
			"""select `modified`
			from %s order by modified desc limit 1"""
			% modified_table
		)
		out[dt]["last_modified"] = tmp and tmp[0][0] or ""
		out[dt]["columns"] = list(map(lambda c: c.split(" as ")[-1], args["columns"]))

		if args.get("links"):
			out[dt]["links"] = args["links"]

	for d in out:
		unused_links = []
		# only compress full dumps (not partial)
		if out[d].get("links") and (d not in last_modified):
			for link_key in out[d]["links"]:
				link = out[d]["links"][link_key]
				if link[0] in out and (link[0] not in last_modified):

					# make a map of link ids
					# to index
					link_map = {}
					doctype_data = out[link[0]]

					col_idx = doctype_data["columns"].index(link[1])
					for row_idx in range(len(doctype_data["data"])):
						row = doctype_data["data"][row_idx]
						link_map[row[col_idx]] = row_idx

					for row in out[d]["data"]:
						columns = list(out[d]["columns"])
						if link_key in columns:
							col_idx = columns.index(link_key)
							# replace by id
							if row[col_idx]:
								row[col_idx] = link_map.get(row[col_idx])
				else:
					unused_links.append(link_key)

		for link in unused_links:
			del out[d]["links"][link]

	return out
