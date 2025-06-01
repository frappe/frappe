// Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors

nts.has_indicator = function (doctype) {
	// returns true if indicator is present
	if (nts.model.is_submittable(doctype)) {
		return true;
	} else if (
		(nts.listview_settings[doctype] || {}).get_indicator ||
		nts.workflow.get_state_fieldname(doctype)
	) {
		return true;
	} else if (
		nts.meta.has_field(doctype, "enabled") ||
		nts.meta.has_field(doctype, "disabled")
	) {
		return true;
	} else if (
		nts.meta.has_field(doctype, "status") &&
		nts.get_meta(doctype).states.length
	) {
		return true;
	}
	return false;
};

nts.get_indicator = function (doc, doctype, show_workflow_state) {
	if (doc.__unsaved) {
		return [__("Not Saved"), "orange"];
	}

	if (!doctype) doctype = doc.doctype;

	let meta = nts.get_meta(doctype);
	var workflow = nts.workflow.workflows[doctype];
	var without_workflow = workflow ? workflow["override_status"] : true;

	var settings = nts.listview_settings[doctype] || {};

	var is_submittable = nts.model.is_submittable(doctype);
	let workflow_fieldname = nts.workflow.get_state_fieldname(doctype);

	let avoid_status_override = (nts.workflow.avoid_status_override[doctype] || []).includes(
		doc[workflow_fieldname]
	);
	// workflow
	if (
		workflow_fieldname &&
		(!without_workflow || show_workflow_state) &&
		!avoid_status_override
	) {
		var value = doc[workflow_fieldname];
		if (value) {
			let colour = "";

			if (locals["Workflow State"][value] && locals["Workflow State"][value].style) {
				colour = {
					Success: "green",
					Warning: "orange",
					Danger: "red",
					Primary: "blue",
					Inverse: "black",
					Info: "light-blue",
				}[locals["Workflow State"][value].style];
			}
			if (!colour) colour = "gray";

			return [__(value), colour, workflow_fieldname + ",=," + value];
		}
	}

	// draft if document is submittable
	if (is_submittable && doc.docstatus == 0 && !settings.has_indicator_for_draft) {
		return [__("Draft"), "red", "docstatus,=,0"];
	}

	// cancelled
	if (is_submittable && doc.docstatus == 2 && !settings.has_indicator_for_cancelled) {
		return [__("Cancelled"), "red", "docstatus,=,2"];
	}

	// based on document state
	if (doc.status && meta && meta.states && meta.states.find((d) => d.title === doc.status)) {
		let state = meta.states.find((d) => d.title === doc.status);
		let color_class = nts.scrub(state.color, "-");
		return [__(doc.status), color_class, "status,=," + doc.status];
	}

	if (settings.get_indicator) {
		var indicator = settings.get_indicator(doc);
		if (indicator) return indicator;
	}

	// if submittable
	if (is_submittable && doc.docstatus == 1) {
		return [__("Submitted"), "blue", "docstatus,=,1"];
	}

	// based on status
	if (doc.status) {
		return [__(doc.status), nts.utils.guess_colour(doc.status), "status,=," + doc.status];
	}

	// based on enabled
	if (nts.meta.has_field(doctype, "enabled")) {
		if (doc.enabled) {
			return [__("Enabled"), "blue", "enabled,=,1"];
		} else {
			return [__("Disabled"), "grey", "enabled,=,0"];
		}
	}

	// based on disabled
	if (nts.meta.has_field(doctype, "disabled")) {
		if (doc.disabled) {
			return [__("Disabled"), "grey", "disabled,=,1"];
		} else {
			return [__("Enabled"), "blue", "disabled,=,0"];
		}
	}
};
