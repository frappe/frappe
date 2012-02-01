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
function $c(command, args, fn, on_timeout, no_spinner, freeze_msg, btn) {
	var req=newHttpReq();
	ret_fn=function() {
		if (checkResponse(req, on_timeout, no_spinner, freeze_msg)) {
			if(btn)$(btn).done_working();
			if(!no_spinner)
				hide_loading(); // Loaded

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
			if(r.exc) { 
				errprint(r.exc); 
				console.log(r.exc);
			};
			if(r.server_messages) { msgprint(r.server_messages);};
			if(r.docs) { LocalDB.sync(r.docs); }
			saveAllowed = true;
			if(fn)fn(r, rtxt);
		}
	}
	if(btn) $(btn).set_working();
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
	if(start_sid && start_sid != get_cookie('sid') && user && user!='Guest') {
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
function $c_obj(doclist, method, arg, call_back, no_spinner, freeze_msg, btn) {
	var args = { 'method':method, 'arg': (typeof arg=='string' ? arg : JSON.stringify(arg)) }
	
	if(typeof doclist=='string') args.doctype = doclist; 
	else args.docs = compress_doclist(doclist)

	// single
	$c('runserverobj',args, call_back, null, no_spinner, freeze_msg, btn);
}

// For call a page metho
function $c_page(module, page, method, arg, call_back, no_spinner, freeze_msg, btn) {
	if(arg && !arg.substr) arg = JSON.stringify(arg);
	$c(module+'.page.'+page+'.'+page+'.'+method,{'arg':arg}, 
		call_back, null, no_spinner, freeze_msg, btn);
}

// generic server call (call page, object)
wn.call = function(args) {
	if(args.module && args.page) {
		$c_page(args.module, args.page, args.method, args.args, args.callback, 
			args.no_spinner, false, args.btn);
	} else if(args.docs) {
		$c_obj(args.doc, args.method, args.args, args.callback, args.no_spinner,
			false, args.btn);
	} else {
		$c(args.method, args.args, args.callback, false, args.no_spinner, false, args.btn);
	}
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
		temp.target = '_blank';
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