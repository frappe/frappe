wn.provide('wn.widgets.form');
wn.provide('wn.widgets.report');
wn.provide('wn.utils');
wn.provide('wn.model');
wn.provide('wn.profile');
wn.provide('wn.session');
wn.provide('_f');
wn.provide('_p');
wn.provide('_r');
wn.provide('_c');
wn.provide('_e');
wn.provide('_startup_data')

// setup custom binding for history
wn.settings.no_history = 1;

// constants
var NEWLINE = '\n';
var login_file = '';
var version = 'v170';

// user
var profile=null;
var session = {};
var is_testing = false;
var user=null;
var user_defaults=null;
var user_roles=null;
var user_fullname=null;
var user_email=null;
var user_img = {};
var home_page=null;
var hide_autosuggest=null;

var page_body=null;
var pscript = {};
var selector=null; 

// ui
var top_index=91;

// Name Spaces
// ============

// form
var _f = {};

// print
var _p = {};

// email
var _e = {};

// report buidler
var _r = {};
var FILTER_SEP = '\1';

// calendar 
var _c = {};

var widget_files = {
	'_f.FrmContainer':'form.compressed.js'
	,'_c.CalendarPopup':'widgets/form/date_picker.js'
	,'_r.ReportContainer':'report.compressed.js'
	,'_p.PrintQuery':'widgets/print_query.js'
	,'Calendar':'widgets/calendar.js'
	,'Recommendation':'widgets/recommend.js'
	,'RatingWidget':'widgets/rating.js'
}

// API globals
var frms={};
var cur_frm=null;
var pscript = {};
var validated = true;
var validation_message = '';
var tinymce_loaded = null;
var cur_autosug = null;