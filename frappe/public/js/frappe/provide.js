// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// provide a namespace
if(!window.frappe)
	window.frappe = {};

frappe.provide = function(namespace) {
	// docs: create a namespace //
	var nsl = namespace.split('.');
	var parent = window;
	for(var i=0; i<nsl.length; i++) {
		var n = nsl[i];
		if(!parent[n]) {
			parent[n] = {}
		}
		parent = parent[n];
	}
	return parent;
}

frappe.provide("locals");
frappe.provide("frappe.flags");
frappe.provide("frappe.settings");
frappe.provide("frappe.utils");
frappe.provide("frappe.ui.form");
frappe.provide("frappe.modules");
frappe.provide("frappe.templates");
frappe.provide("frappe.test_data");
frappe.provide('frappe.utils');
frappe.provide('frappe.model');
frappe.provide('frappe.user');
frappe.provide('frappe.session');
frappe.provide('locals.DocType');

// for listviews
frappe.provide("frappe.listview_settings");
frappe.provide("frappe.tour");
frappe.provide("frappe.listview_parent_route");

// constants
window.NEWLINE = '\n';
window.TAB = 9;
window.UP_ARROW = 38;
window.DOWN_ARROW = 40;

// proxy for user globals defined in desk.js

// API globals
window.cur_frm=null;
