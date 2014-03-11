// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.widgets.form');
frappe.provide('frappe.widgets.report');
frappe.provide('frappe.utils');
frappe.provide('frappe.model');
frappe.provide('frappe.user');
frappe.provide('frappe.session');
frappe.provide('_f');
frappe.provide('_p');
frappe.provide('_r');
frappe.provide('_startup_data')
frappe.provide('locals')
frappe.provide('locals.DocType')

// setup custom binding for history
frappe.settings.no_history = 1;

// constants
var NEWLINE = '\n';

// user
var user=null;
var user=null;
var user_defaults=null;
var user_roles=null;
var user_fullname=null;
var user_email=null;
var user_img = {};

var pscript = {};

// Name Spaces
// ============

// form
var _f = {};
var _p = {};
var _r = {};
var FILTER_SEP = '\1';

// API globals
var frms={};
var cur_frm=null;
var pscript = {};
