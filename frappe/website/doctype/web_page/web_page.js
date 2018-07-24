// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

$.extend(cur_frm.cscript, {
	layout: function(doc) {
		if(!doc.__islocal) {
			if(doc.insert_code) {
				if(!doc.javascript) {
					cur_frm.set_value("javascript", '$(function() { });');
				}
			}
			if(doc.insert_style) {
				if(!doc.css) {
					cur_frm.set_value("css", '#page-'+doc.name+' { }');
				}
			}
		}
	},
	refresh: function(doc) {
		cur_frm.cscript.layout(doc);
		if(cur_frm.doc.template_path) {
			cur_frm.set_read_only();
		}
	},
	insert_style: function(doc) {
		cur_frm.cscript.layout(doc);
	},
	insert_code: function(doc) {
		cur_frm.cscript.layout(doc);
	}
});

frappe.ui.form.on("Web Page", {
	published: function (frm) {
		// If current date is before end date,
		// and web page is manually unpublished,
		// set end date to current date.
		if (!frm.doc.published && frm.doc.end_date) {
			var end_date = frappe.datetime.str_to_obj(frappe.datetime.now_datetime());

			// Set date a few seconds in the future to avoid throwing
			// start and end date validation error
			end_date.setSeconds(end_date.getSeconds() + 5)

			frm.set_value("end_date", end_date);
		}
	}
})
