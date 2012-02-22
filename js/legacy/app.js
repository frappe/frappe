// App.js

// dialog container
var popup_cont;
var session = {};
var start_sid = null;
if(!wn) var wn = {};

function startup() {
	// save the sid (so that we know if it changes mid-session)
	start_sid = get_cookie('sid');
	
	popup_cont = $a(document.getElementsByTagName('body')[0], 'div');

	// Globals
	// ---------------------------------
	var setup_globals = function(r) {
		wn.boot = r;
		
		profile = r.profile;
		user = r.profile.name;		
		user_fullname = profile.first_name + (r.profile.last_name ? (' ' + r.profile.last_name) : '');
		user_defaults = profile.defaults;
		user_roles = profile.roles;
		user_email = profile.email;
		profile.start_items = r.start_items;
		home_page = r.home_page;
		_p.letter_heads = r.letter_heads;

		sys_defaults = r.sysdefaults;
		// bc
		session.rt = profile.can_read;
		if(r.ipinfo) session.ipinfo = r.ipinfo;
		session.dt_labels = r.dt_labels;
		session.rev_dt_labels = {} // reverse lookup - get doctype by label
		if(r.dt_labels) {
			for(key in r.dt_labels)session.rev_dt_labels[r.dt_labels[key]] = key;
		}

		// control panel
		wn.control_panel = r.control_panel;
	}
	
	var setup_history = function(r) {
		rename_observers.push(nav_obj);
	}
	
	var callback = function(r,rt) {
		if(r.exc) console.log(r.exc);
		setup_globals(r);
		setup_history();

		var a = new Body();
		page_body.run_startup_code();
		
		for(var i=0; i<startup_list.length; i++) {
			startup_list[i]();
		}		
		
		// show a new form on loading?
		
		// open an existing page or record
		var t = to_open();
		if(t) {
			historyChange(t);
		} else if(home_page) {
			// show home oage
			loadpage(home_page);
		}
		page_body.ready();
	}
	if(wn.boot) {
		LocalDB.sync(wn.boot.docs);
		callback(wn.boot, '');
		if(wn.boot.error_messages)
			console.log(wn.boot.error_messages)
		if(wn.boot.server_messages) 
			msgprint(wn.boot.server_messages);
	} else {
		if($i('startup_div'))
			$c('startup',{},callback,null,1);
	}
}

function to_open() {
	if(get_url_arg('page'))
		return get_url_arg('page');
	var h = location.hash;
	if(h) {
		return h.substr(1);
	}
}

function logout() {
	$c('logout', args = {}, function(r,rt) { 
		if(r.exc) {
			msgprint(r.exc);
			return;
		}
		redirect_to_login();
	});
}

function redirect_to_login() {
	if(login_file) 
		window.location.href = login_file;
	else {
		window.location.reload();		
	}
}

// default print style
_p.def_print_style_body = "html, body, div, span, td { font-family: Arial, Helvetica; font-size: 12px; }" + "\npre { margin:0; padding:0;}"	

_p.def_print_style_other = "\n.simpletable, .noborder { border-collapse: collapse; margin-bottom: 10px;}"
	+"\n.simpletable td {border: 1pt solid #000; vertical-align: top; padding: 2px; }"
	+"\n.noborder td { vertical-align: top; }"

_p.go = function(html) {
	var d = document.createElement('div')
	d.innerHTML = html
	$(d).printElement();
}

_p.preview = function(html) {
	var w = window.open('');
	w.document.write(html)
	w.document.close();
}

// setup calendar
function setup_calendar() {

	var p = new Page('_calendar');
	p.wrapper.style.height = '100%'; // IE FIX
	p.wrapper.onshow = function() { 
		wn.require('lib/js/legacy/widgets/calendar.js');

		if(!_c.calendar) {
			_c.calendar = new Calendar();
			_c.calendar.init(p.cont);
			rename_observers.push(_c.calendar);
		}
	}
}

startup_list.push(setup_calendar);

var resize_observers = []
function set_resize_observer(fn) {
	if(resize_observers.indexOf(fn)==-1) resize_observers.push(fn);	
}
window.onresize = function() {
	return;
	var ht = get_window_height();
	for(var i=0; i< resize_observers.length; i++){
		resize_observers[i](ht);
	}
}

get_window_height = function() {
	var ht = window.innerHeight ? window.innerHeight : document.documentElement.offsetHeight ? document.documentElement.offsetHeight : document.body.offsetHeight;
	return ht;
}
