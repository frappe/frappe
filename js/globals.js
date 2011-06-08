var wn = {} // global namespace

wn.widgets = {form:{},report:{}}
wn.utils = {}
wn.model = {}
wn.profile = {}
wn.session = {}

// constants
var NEWLINE = '\n';
var login_file = '';
var version = 'v170';

// user
var profile;
var session = {};
var is_testing = false;
var user;
var user_defaults;
var user_roles;
var user_fullname;
var user_email;
var user_img = {};
var home_page;

var page_body;
var pscript = {};
var selector; 
var keypress_observers = [];
var click_observers = [];

var editAreaLoader;

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

var Recommendation;
var RatingWidget;

// API globals
var frms={};
var cur_frm;
var pscript = {};
var validated = true;
var validation_message = '';
var tinymce_loaded;

var $c_get_values;
var get_server_fields;
var set_multiple;
var set_field_tip;
var refresh_field;
var refresh_many;
var set_field_options;
var set_field_permlevel;
var hide_field;
var unhide_field;
var print_table;
var sendmail;

// icons
var exp_icon = "images/ui/right-arrow.gif"; 
var min_icon = "images/ui/down-arrow.gif";

// space holder div
var space_holder_div = $a(null,'div','space_holder');
space_holder_div.innerHTML = 'Loading...'
