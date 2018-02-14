// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.desk.form');
frappe.provide('frappe.desk.report');
frappe.provide('frappe.utils');
frappe.provide('frappe.model');
frappe.provide('frappe.user');
frappe.provide('frappe.session');
frappe.provide('locals');
frappe.provide('locals.DocType');

// for listviews
frappe.provide("frappe.listview_settings");
frappe.provide("frappe.listview_parent_route");

// setup custom binding for history
frappe.settings.no_history = 1;

// constants
window.NEWLINE = '\n';
window.TAB = 9;
window.UP_ARROW = 38;
window.DOWN_ARROW = 40;

// proxy for user globals defined in desk.js

// Name Spaces
// ============

// form
window._f = {};
window._p = {};
window._r = {};

// API globals
window.frms={};
window.cur_frm=null;
