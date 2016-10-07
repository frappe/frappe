// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors

frappe.get_indicator = function(doc, doctype) {
	if(doc.__unsaved) {
		return [__("Not Saved"), "orange"];
	}

	if(!doctype) doctype = doc.doctype;

	var settings = frappe.listview_settings[doctype] || {};

	var is_submittable = frappe.model.is_submittable(doctype),
		workflow_fieldname = frappe.workflow.get_state_fieldname(doctype);

	if(doc.docstatus==3) {
		return [__("Queued for saving"), "orange", "docstatus,=,3"];
	}

	if(doc.docstatus==4) {
		return [__("Queued for submission"), "orange", "docstatus,=,4"];
	}

	if(doc.docstatus==5) {
		return [__("Queued for cancellation"), "orange", "docstatus,=,5"];
	}

	// workflow
	if(workflow_fieldname) {
		var value = doc[workflow_fieldname];
		if(value) {
			var colour = "";
			
			if(locals["Workflow State"][value] && locals["Workflow State"][value].style) {
				var colour = {
					"Success": "green",
					"Warning": "orange",
					"Danger": "red",
					"Primary": "blue",
				}[locals["Workflow State"][value].style];
			}
			if(!colour) colour = "darkgrey";

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
