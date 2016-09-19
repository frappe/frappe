// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors

frappe.has_indicator = function(doctype) {
	// returns true if indicator is present
	if(frappe.model.is_submittable(this.doctype)) {
		return true;
	} else if(this.settings.get_indicator || this.workflow_state_fieldname) {
		return true;
	} else if(frappe.meta.has_field(doctype, 'enabled') || frappe.meta.has_field(doctype, 'disabled')) {
		return true;
	}
	return false;
}

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
			var colour = {
				"Success": "green",
				"Warning": "orange",
				"Danger": "red",
				"Primary": "blue",
			}[locals["Workflow State"][value].style] || "darkgrey";
			return [__(value), colour, workflow_fieldname + ',=,' + value];
		}
	}

	// draft if document is submittable
	if(is_submittable && doc.docstatus==0 && !settings.has_indicator_for_draft) {
		return [__("Draft"), "red", "docstatus,=,0"];
	}

	// cancelled
	if(is_submittable && doc.docstatus==2) {
		return [__("Cancelled"), "red", "docstatus,=,2"];
	}

	if(settings.get_indicator) {
		var indicator = settings.get_indicator(doc);
		if(indicator) return indicator;
	}

	// if submittable
	if(is_submittable && doc.docstatus==1) {
		return [__("Submitted"), "blue", "docstatus,=,1"];
	}

	// based on status
	if(doc.status) {
		return [__(doc.status), frappe.utils.guess_colour(doc.status)];
	}

	// based on enabled
	if(frappe.meta.has_field(doctype, 'enabled')) {
		if(doc.enabled) {
			return [__('Enabled'), 'blue', 'enabled=1'];
		} else {
			return [__('Disabled'), 'grey', 'enabled=0'];
		}
	}

	// based on disabled
	if(frappe.meta.has_field(doctype, 'disabled')) {
		if(doc.disabled) {
			return [__('Disabled'), 'grey', 'disabled=1'];
		} else {
			return [__('Enabled'), 'blue', 'disabled=0'];
		}
	}
}
