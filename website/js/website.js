// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt 
if(!window.wn) wn = {};


wn = {
	call: function(opts) {
		wn.prepare_call(opts);
		$.ajax({
			type: "POST",
			url: "server.py",
			data: opts.args,
			dataType: "json",
			success: function(data) {
				wn.process_response(opts, data);
			},
			error: function(response) {
				NProgress.done();
				console.error ? console.error(response) : console.log(response);
			}
		});
	
		return false;
	},
	prepare_call: function(opts) {
		if(opts.btn) {
			$(opts.btn).prop("disabled", true);
		}
	
		if(opts.msg) {
			$(opts.msg).toggle(false);
		}
	
		if(!opts.args) opts.args = {};
	
		// get or post?
		if(!opts.args._type) {
			opts.args._type = opts.type || "GET";
		}

		// method
		if(opts.method) {
			opts.args.cmd = opts.method;
		}

		// stringify
		$.each(opts.args, function(key, val) {
			if(typeof val != "string") {
				opts.args[key] = JSON.stringify(val);
			}
		});

		NProgress.start();
	},
	process_response: function(opts, data) {
		NProgress.done();
		if(opts.btn) {
			$(opts.btn).prop("disabled", false);
		}
		if(data.exc) {
			if(opts.btn) {
				$(opts.btn).addClass("btn-danger");
				setTimeout(function() { $(opts.btn).removeClass("btn-danger"); }, 1000);
			}
			try {
				var err = JSON.parse(data.exc);
				if($.isArray(err)) {
					err = err.join("\n");
				}
				console.error ? console.error(err) : console.log(err);
			} catch(e) {
				console.log(data.exc);
			}
		} else{
			if(opts.btn) {
				$(opts.btn).addClass("btn-success");
				setTimeout(function() { $(opts.btn).removeClass("btn-success"); }, 1000);
			}
		}
		if(opts.msg && data.message) {
			$(opts.msg).html(data.message).toggle(true);
		}
		if(opts.callback)
			opts.callback(data);
	},
	show_message: function(text, icon) {
		if(!icon) icon="icon-refresh icon-spin";
		wn.hide_message();
		$('<div class="message-overlay"></div>')
			.html('<div class="content"><i class="'+icon+' text-muted"></i><br>'
				+text+'</div>').appendTo(document.body);
	},
	hide_message: function(text) {
		$('.message-overlay').remove();
	},
	get_sid: function() {
		var sid = getCookie("sid");
		return sid && sid!=="Guest";
	},
	get_modal: function(title, body_html) {
		var modal = $('<div class="modal" style="overflow: auto;">\
			<div class="modal-dialog">\
				<div class="modal-content">\
					<div class="modal-header">\
						<a type="button" class="close" \
							data-dismiss="modal" aria-hidden="true">&times;</a>\
						<h4 class="modal-title">'+title+'</h4>\
					</div>\
					<div class="modal-body ui-front">'+body_html+'\
					</div>\
				</div>\
			</div>\
			</div>').appendTo(document.body);
			
			return modal;
	},
	msgprint: function(html, title) {
		return wn.get_modal(title || "Message", html).modal("show");
	}
}


// Utility functions

function valid_email(id) { 
	if(id.toLowerCase().search("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")==-1) 
		return 0; else return 1; }

var validate_email = valid_email;

function get_url_arg(name) {
	name = name.replace(/[\[]/,"\\\[").replace(/[\]]/,"\\\]");
	var regexS = "[\\?&]"+name+"=([^&#]*)";
	var regex = new RegExp( regexS );
	var results = regex.exec( window.location.href );
	if(results == null)
		return "";
	else
		return decodeURIComponent(results[1]);		
}

function make_query_string(obj) {
	var query_params = [];
	$.each(obj, function(k, v) { query_params.push(encodeURIComponent(k) + "=" + encodeURIComponent(v)); });
	return "?" + query_params.join("&");
}

function repl(s, dict) {
	if(s==null)return '';
	for(key in dict) {
		s = s.split("%("+key+")s").join(dict[key]);
	}
	return s;
}

function replace_all(s, t1, t2) {
	return s.split(t1).join(t2);
}

function getCookie(name) {
	return getCookies()[name];
}

function getCookies() {
	var c = document.cookie, v = 0, cookies = {};
	if (document.cookie.match(/^\s*\$Version=(?:"1"|1);\s*(.*)/)) {
		c = RegExp.$1;
		v = 1;
	}
	if (v === 0) {
		c.split(/[,;]/).map(function(cookie) {
			var parts = cookie.split(/=/, 2),
				name = decodeURIComponent(parts[0].trimLeft()),
				value = parts.length > 1 ? decodeURIComponent(parts[1].trimRight()) : null;
			if(value && value.charAt(0)==='"') {
				value = value.substr(1, value.length-2);
			}
			cookies[name] = value;
		});
	} else {
		c.match(/(?:^|\s+)([!#$%&'*+\-.0-9A-Z^`a-z|~]+)=([!#$%&'*+\-.0-9A-Z^`a-z|~]*|"(?:[\x20-\x7E\x80\xFF]|\\[\x00-\x7F])*")(?=\s*[,;]|$)/g).map(function($0, $1) {
			var name = $0,
				value = $1.charAt(0) === '"'
						  ? $1.substr(1, -1).replace(/\\(.)/g, "$1")
						  : $1;
			cookies[name] = value;
		});
	}
	return cookies;
}

if (typeof String.prototype.trimLeft !== "function") {
	String.prototype.trimLeft = function() {
		return this.replace(/^\s+/, "");
	};
}
if (typeof String.prototype.trimRight !== "function") {
	String.prototype.trimRight = function() {
		return this.replace(/\s+$/, "");
	};
}
if (typeof Array.prototype.map !== "function") {
	Array.prototype.map = function(callback, thisArg) {
		for (var i=0, n=this.length, a=[]; i<n; i++) {
			if (i in this) a[i] = callback.call(thisArg, this[i]);
		}
		return a;
	};
}

function remove_script_and_style(txt) {
	return (!txt || (txt.indexOf("<script>")===-1 && txt.indexOf("<style>")===-1)) ? txt :
		$("<div></div>").html(txt).find("script,noscript,style,title,meta").remove().end().html();
}

function is_html(txt) {
	if(txt.indexOf("<br>")==-1 && txt.indexOf("<p")==-1 
		&& txt.indexOf("<img")==-1 && txt.indexOf("<div")==-1) {
		return false;
	}
	return true;
}

function ask_to_login() {
	if(!full_name) {
		if(localStorage) {
			localStorage.setItem("last_visited", window.location.href.split("/").slice(-1)[0]);
		}
		window.location.href = "login";
	}
}

// check if logged in?
$(document).ready(function() {
	window.full_name = getCookie("full_name");
	$("#website-login").toggleClass("hide", full_name ? true : false);
	$("#website-post-login").toggleClass("hide", full_name ? false : true);
});

wn.send_message = function(opts, btn) {
	return wn.call({
		type: "POST",
		method: "website.doctype.contact_us_settings.templates.pages.contact.send_message",
		btn: btn,
		args: opts,
		callback: opts.callback
	});
}

