// My HTTP Request

var outUrl = "index.cgi";
var NULL_CHAR = '^\5*';

// check response of HTTP request, only if ready
function checkResponse(r, on_timeout, no_spinner, freeze_msg) {
	try {
	 	if (r.readyState==4 && r.status==200) return true; else return false; 
	} catch(e) {
		// $i("icon_loading").style.visibility = "hidden"; WAINING MESSAGE
		msgprint("error:Request timed out, try again");
		if(on_timeout)
			on_timeout();

		hide_loading();

		if(freeze_msg)
			unfreeze();
		return false;
	}
}

var pending_req = 0;

// new XMLHttpRequest object
function newHttpReq() { 
	if (!isIE) 
 		var r=new XMLHttpRequest(); 
	else if (window.ActiveXObject) 
		var r=new ActiveXObject("Microsoft.XMLHTTP"); 
	return r;
}

// call execute serverside request
function $c(command, args, fn, on_timeout, no_spinner, freeze_msg) {
	var req=newHttpReq();
	ret_fn=function() {
		if (checkResponse(req, on_timeout, no_spinner, freeze_msg)) {
			if(!no_spinner)hide_loading(); // Loaded

			var rtxt = req.responseText;
						
			try { 
				var r = JSON.parse(rtxt); 
			} catch(e) { 
				alert('Handler Exception:' + rtxt);
				return; 
			}
			// unfreeze
			if(freeze_msg)unfreeze();
			
			if(!validate_session(r,rtxt)) return;
			if(r.exc) { errprint(r.exc); };
			if(r.server_messages) { msgprint(r.server_messages);};
			if(r.docs) { LocalDB.sync(r.docs); }
			saveAllowed = true;
			if(fn)fn(r, rtxt);
		}
	}
	req.onreadystatechange=ret_fn;
	req.open("POST",outUrl,true);
	req.setRequestHeader("ENCTYPE", "multipart/form-data");
	req.setRequestHeader("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8");
	args['cmd']=command;
	req.send(makeArgString(args)); 
	if(!no_spinner)set_loading(); // Loading
	if(freeze_msg)freeze(freeze_msg,1);
}

function validate_session(r,rt) {
	// check for midway change in session
	if(r.message=='Logged In') {
		start_sid = get_cookie('sid');
		return true;
	}
	if(start_sid && start_sid != get_cookie('sid') && user!='Guest') {
		page_body.set_session_changed();	
		return;
	}

	// check for expired session
	if(r.exc && r.session_status=='Session Expired') {
		resume_session();
		return;
	}

	// check for logged out sesion
	if(r.exc && r.session_status=='Logged Out') {
		msgprint('You have been logged out');
		setTimeout('redirect_to_login()', 3000);
		return;
	}
	
	if(r.exc && r.exc_type && r.exc_type=='PermissionError') {
		loadpage('_home');
	}
	
	return true;
}

// For calling an object
function $c_obj(doclist, method, arg, call_back, no_spinner, freeze_msg) {
	var args = { 'method':method, 'arg': (typeof arg=='string' ? arg : JSON.stringify(arg)) }
	
	if(typeof doclist=='string') args.doctype = doclist; 
	else args.docs = compress_doclist(doclist)

	// single
	$c('runserverobj',args, call_back, null, no_spinner, freeze_msg);	
}

// For call a page metho
function $c_page(module, page, method, arg, call_back, no_spinner, freeze_msg) {
	if(arg && !arg.substr) arg = JSON.stringify(arg);
	$c(module+'.page.'+page+'.'+page+'.'+method,{'arg':arg}, call_back, null, no_spinner, freeze_msg);
}

// For calling an for output as csv
function $c_obj_csv(doclist, method, arg) {
	// single
	
	var args = {}
	args.cmd = 'runserverobj';
	args.as_csv = 1;
	args.method = method;
	args.arg = arg;
	
	if(doclist.substr)
		args.doctype = doclist;		
	else
		args.docs = compress_doclist(doclist);

	// open
	open_url_post(outUrl, args);
}


// For loading a matplotlib Plot
function $c_graph(img, control_dt, method, arg) {
	img.src = outUrl + '?' + makeArgString({cmd:'get_graph', dt:control_dt, method:method, arg:arg});
}

function my_eval(co) {
	var w = window;

	// Evaluate script
	if (!w.execScript) {
		if (/Gecko/.test(navigator.userAgent)) {
			eval(co, w); // Firefox 3.0
		} else {
			eval.call(w, co);
		}
	} else {
		w.execScript(co); // IE
	}
}


// For loading javascript file on demand using AJAX
function $c_js(fn, callback) {
	var req=newHttpReq();

	ret_fn=function() {
		if (checkResponse(req, function() { }, 1, null)) {
			if(req.responseText.substr(0,9)=='Not Found') {
				alert(req.responseText);
				return;	
			}
			hide_loading();
			my_eval(req.responseText);
			callback();
		}
	}

	req.onreadystatechange=ret_fn;
	req.open("POST",'cgi-bin/getjsfile.cgi',true);
	req.setRequestHeader("ENCTYPE", "multipart/form-data");
	req.setRequestHeader("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8");
	req.send(makeArgString({filename:fn})); 
	set_loading();
}

var load_queue = {};
var currently_loading = {};
var widgets = {};
var single_widgets = {};

// load a widget on demand
// --------------------------------------------------------------
function new_widget(widget, callback, single_type) {
	var namespace = '';
	var widget_name = widget;
	
	if(widget.search(/\./) != -1) {
		namespace = widget.split('.')[0];
		widget_name = widget.split('.')[1];
	}

	var widget_loaded = function() {		
		currently_loading[widget] = 0;
		for(var i in load_queue[widget]) {
			// callback
			load_queue[widget][i](create_widget());
		}

		// clear the queue
		load_queue[widget] = [];
	}

	var create_widget = function() {
		if(single_type && single_widgets[widget_name]) 
			return null;
		
		if(namespace)
			var w = new window[namespace][widget_name]();
		else
			var w = new window[widget_name]();
		
		// add to singles
		if(single_type) 
			single_widgets[widget_name] = w;
			
		return w;
	}
	
	if(namespace ? window[namespace][widget_name] : window[widget_name]) {
		// loaded?
		callback(create_widget());
	} else {

		// loading in process
		if(!load_queue[widget]) load_queue[widget] = [];
		load_queue[widget].push(callback);
		
		// load only if not currently loading
		if(!currently_loading[widget]) {
			$c_js(widget_files[widget], widget_loaded);
		}

		// flag it as loading
		currently_loading[widget] = 1;	
	}
}

function makeArgString(dict) {
	var varList = [];

	for(key in dict){
		varList[varList.length] = key + '=' + encodeURIComponent(dict[key]);
	}
	return varList.join('&');
}

// call a url as POST
function open_url_post(URL, PARAMS, new_window) {
	var temp=document.createElement("form");
	temp.action=URL;
	temp.method="POST";
	temp.style.display="none";
	if(new_window){

	}
	for(var x in PARAMS) {
		var opt=document.createElement("textarea");
		opt.name=x;
		opt.value=PARAMS[x];
		temp.appendChild(opt);
	}
	document.body.appendChild(temp);
	temp.submit();
	return temp;
}

// Resume sessions
var resume_dialog = null;

function resume_session() {
	if(!resume_dialog) {
		var d = new Dialog(400,200,'Session Expired');
		d.make_body([
			['Password','password','Re-enter your password to resume the session'], ['Button','Go']]);

		// check password
		d.widgets['Go'].onclick = function() {
			resume_dialog.widgets['Go'].set_working();
			var callback = function(r, rt) {
				resume_dialog.widgets['Go'].done_working();
				if(r.message == 'Logged In') {
					
					// okay
					resume_dialog.allow_close=1;
					resume_dialog.hide();
					setTimeout('resume_dialog.allow_close=0',100);
				} else {
					
					// wrong password
					msgprint('Wrong Password, try again');
					resume_dialog.wrong_count++;
					if(resume_dialog.wrong_count > 2) logout();
				}
			}
			$c('resume_session',{pwd:resume_dialog.widgets['password'].value},callback)
		}
		d.onhide = function() {
			if(!resume_dialog.allow_close) logout();
		}
		resume_dialog = d;
	}
	resume_dialog.wrong_count = 0;
	resume_dialog.show();
}