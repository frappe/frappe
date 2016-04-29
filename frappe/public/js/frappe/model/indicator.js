// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors

frappe.get_indicator = function(doc, doctype) {
	if(doc.__unsaved) {
		return [__("Not Saved"), "orange"];
	}

	if(!doctype) doctype = doc.doctype;

	var settings = frappe.listview_settings[doctype] || {};

	var is_submittable = frappe.model.is_submittable(doctype),
		workflow_fieldname = frappe.workflow.get_state_fieldname(doctype);

	// workflow
	if(workflow_fieldname) {
		var value = doc[workflow_fieldname];
		if(value) {
			var colour = {
				"Success": "green",
				"Warning": "orange",
				"Danger": "red",
				"Primary": "blue",
			}[locals["Workflow State"][value].style] || "darkgrey";
			return [__(value), colour, workflow_fieldname + ',=,' + value];
		}
	}

	if(is_submittable && doc.docstatus==0 && !settings.has_indicator_for_draft) {
		return [__("Draft"), "red", "docstatus,=,0"];
	}

	if(is_submittable && doc.docstatus==2) {
		return [__("Cancelled"), "red", "docstatus,=,2"];
	}

	if(settings.get_indicator) {
		var indicator = settings.get_indicator(doc);
		if(indicator) return indicator;
	}

	if(is_submittable && doc.docstatus==1) {
		return [__("Submitted"), "blue", "docstatus,=,1"];
	}

	if(doc.status) {
		return [__(doc.status), frappe.utils.guess_colour(doc.status)];
	}
}
