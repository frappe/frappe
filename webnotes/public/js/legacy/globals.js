// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide('wn.widgets.form');
wn.provide('wn.widgets.report');
wn.provide('wn.utils');
wn.provide('wn.model');
wn.provide('wn.profile');
wn.provide('wn.session');
wn.provide('_f');
wn.provide('_p');
wn.provide('_r');
wn.provide('_startup_data')
wn.provide('locals')
wn.provide('locals.DocType')

// setup custom binding for history
wn.settings.no_history = 1;

// constants
var NEWLINE = '\n';

// user
var profile=null;
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
