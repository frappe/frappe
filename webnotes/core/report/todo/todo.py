# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes import _
from webnotes.widgets.reportview import execute as runreport
from webnotes.utils import getdate

def execute(filters=None):
	priority_map = {"High": 3, "Medium": 2, "Low": 1}
	
	todo_list = runreport(doctype="ToDo", fields=["name", "date", "description",
		"priority", "reference_type", "reference_name", "assigned_by", "owner"], 
		filters=[["ToDo", "checked", "!=", 1]])
	
	todo_list.sort(key=lambda todo: (priority_map.get(todo.priority, 0), 
		todo.date and getdate(todo.date) or getdate("1900-01-01")), reverse=True)
		
	columns = [_("ID")+":Link/ToDo:90", _("Priority")+"::60", _("Date")+ ":Date", 
		_("Description")+"::150", _("Assigned To/Owner") + ":Link/Profile:120", 
		_("Assigned By")+":Link/Profile:120", _("Reference")+"::200"]

	result = []
	for todo in todo_list:
		if todo.reference_type:
			todo.reference = """<a href="#Form/%s/%s">%s: %s</a>""" % \
				(todo.reference_type, todo.reference_name, todo.reference_type, todo.reference_name)
		else:
			todo.reference = None
		result.append([todo.name, todo.priority, todo.date, todo.description,
			todo.owner, todo.assigned_by, todo.reference])
	
	return columns, result
	
