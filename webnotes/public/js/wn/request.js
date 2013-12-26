// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// My HTTP Request

wn.provide('wn.request');
wn.request.url = '/';

// generic server call (call page, object)
wn.call = function(opts) {
	var args = $.extend({}, opts.args);
	
	// cmd
	if(opts.module && opts.page) {
		args.cmd = opts.module+'.page.'+opts.page+'.'+opts.page+'.'+opts.method;
	} else if(opts.doc) {
		$.extend(args, {
			cmd: "runserverobj",
			docs: wn.model.compress(wn.model.get_doclist(opts.doc.doctype,
				opts.doc.name)),
			method: opts.method,
			args: opts.args,
		});	
	} else if(opts.method) {
		args.cmd = opts.method;
	}
		
	// stringify args if required
	for(key in args) {
		if(args[key] && typeof args[key] != 'string') {
			args[key] = JSON.stringify(args[key]);
		}
	}

	return wn.request.call({
		type: opts.type || "POST",
		args: args,
		success: opts.callback,
		error: opts.error,
		btn: opts.btn,
		freeze: opts.freeze,
		show_spinner: !opts.no_spinner,
		progress_bar: opts.progress_bar,
		async: opts.async
	});
}


wn.request.call = function(opts) {
	wn.request.prepare(opts);
	
	// all requests will be post, set _type as POST for commit
	opts.args._type = opts.type;
	
	var ajax_args = {
		url: opts.url || wn.request.url,
		data: opts.args,
		type: 'POST',
		dataType: opts.dataType || 'json',
		success: function(r, xhr) {
			wn.request.cleanup(opts, r);
			opts.success && opts.success(r, xhr.responseText);
		},
		error: function(xhr, textStatus) {
			wn.request.cleanup(opts, {});
			show_alert(wn._("Unable to complete request: ") + textStatus)
			opts.error && opts.error(xhr)
		},
		async: opts.async
	};
	
	wn.last_request = ajax_args.data;
	
	if(opts.progress_bar) {
		var interval = null;
		$.extend(ajax_args, {
			xhr: function() {
				var xhr = jQuery.ajaxSettings.xhr();
				interval = setInterval(function() {
					if(xhr.readyState > 2) {
				    	var total = parseInt(xhr.getResponseHeader('Original-Length') || 0) || 
							parseInt(xhr.getResponseHeader('Content-Length'));
				    	var completed = parseInt(xhr.responseText.length);
						var percent = (100.0 / total * completed).toFixed(2);
						opts.progress_bar.css('width', (percent < 10 ? 10 : percent) + '%');
					}
				}, 50);
				wn.last_xhr = xhr;
				return xhr;
			},
			complete: function() {
				opts.progress_bar.css('width', '100%');
				clearInterval(interval);
			}
		})
	}
	
	return $.ajax(ajax_args);
}

// call execute serverside request
wn.request.prepare = function(opts) {
	// btn indicator
	if(opts.btn) $(opts.btn).set_working();
	
	// navbar indicator
	if(opts.show_spinner) wn.set_loading();
	
	// freeze page
	if(opts.freeze) wn.dom.freeze();
	
	// no cmd?
	if(!opts.args.cmd) {
		console.log(opts)
		throw "Incomplete Request";
	}
}

wn.request.cleanup = function(opts, r) {
	// stop button indicator
	if(opts.btn) $(opts.btn).done_working();
	
	// hide button indicator
	if(opts.show_spinner) wn.done_loading();

	// un-freeze page
	if(opts.freeze) wn.dom.unfreeze();

	// session expired? - Guest has no business here!
	if(r.session_expired || wn.get_cookie("sid")==="Guest") { 
		if(!wn.app.logged_out) {
			msgprint(wn._('Session Expired. Logging you out'));
			wn.app.logout();
		}
		return;
	}
	
	// show messages
	if(r._server_messages) {
		r._server_messages = JSON.parse(r._server_messages)
		msgprint(r._server_messages);
	}
	
	// show errors
	if(r.exc) { 
		r.exc = JSON.parse(r.exc);
		if(r.exc instanceof Array) {
			$.each(r.exc, function(i, v) {
				if(v)console.log(v);
			})
		} else {
			console.log(r.exc);
		}
	};
	
	// debug messages
	if(r._debug_messages) {
		console.log("-")
		console.log("-")
		console.log("-")
		if(opts.args) {
			console.log("<<<< arguments ");
			console.log(opts.args);
			console.log(">>>>")
		}
		$.each(JSON.parse(r._debug_messages), function(i, v) { console.log(v); });
		console.log("<<<< response");
		delete r._debug_messages;
		console.log(r);
		console.log(">>>>")
		console.log("-")
		console.log("-")
		console.log("-")
	}
	
	if(r['403']) {
		wn.show_not_permitted(wn.get_route_str());
	}

	if(r.docs) {
		r.docs = wn.model.sync(r);
	}
	if(r.__messages) {
		$.extend(wn._messages, r.__messages);
	}
	
	wn.last_response = r;
}