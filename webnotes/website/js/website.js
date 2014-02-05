// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide("website");

$.extend(wn, {
	_assets_loaded: [],
	require: function(url) {
		if(wn._assets_loaded.indexOf(url)!==-1) return;
		$.ajax({
			url: url, //+ "?q=" + Math.floor(Math.random() * 1000), 
			async: false, 
			dataType: "text", 
			success: function(data) {
				if(url.split(".").splice(-1) == "js") {
					var el = document.createElement('script');
				} else {
					var el = document.createElement('style');
				}
				el.appendChild(document.createTextNode(data));
				document.getElementsByTagName('head')[0].appendChild(el);
				wn._assets_loaded.push(url);
			}
		});
	},
	hide_message: function(text) {
		$('.message-overlay').remove();
	},
	call: function(opts) {
		// opts = {"method": "PYTHON MODULE STRING", "args": {}, "callback": function(r) {}}
		wn.prepare_call(opts);
		return $.ajax({
			type: opts.type || "POST",
			url: "/",
			data: opts.args,
			dataType: "json",
			statusCode: {
				404: function(xhr) {
					msgprint("Not Found");
				},
				403: function(xhr) {
					msgprint("Not Permitted");
				},
				200: function(data, xhr) {
					if(opts.callback)
						opts.callback(data);
				}
			}
		}).always(function(data) {
			// executed before statusCode functions
			if(data.responseText) {
				data = JSON.parse(data.responseText);
			}
			wn.process_response(opts, data);
		});
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

		if(!opts.no_spinner) { 
			NProgress.start();
		}
	},
	process_response: function(opts, data) {
		if(!opts.no_spinner) NProgress.done();
		
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
		var modal = $('<div class="modal" style="overflow: auto;" tabindex="-1">\
			<div class="modal-dialog">\
				<div class="modal-content">\
					<div class="modal-header">\
						<a type="button" class="close"\
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
		if(html.substr(0,1)==="[") html = JSON.parse(html);
		if($.isArray(html)) {
			html = html.join("<hr>")
		}
		return wn.get_modal(title || "Message", html).modal("show");
	},
	send_message: function(opts, btn) {
		return wn.call({
			type: "POST",
			method: "webnotes.website.doctype.contact_us_settings.templates.pages.contact.send_message",
			btn: btn,
			args: opts,
			callback: opts.callback
		});
	},
	has_permission: function(doctype, docname, perm_type, callback) {
		return wn.call({
			method: "webnotes.client.has_permission",
			no_spinner: true,
			args: {doctype: doctype, docname: docname, perm_type: perm_type},
			callback: function(r) {
				if(!r.exc && r.message.has_permission) {
					if(callback) { return callback(r); }
				}
			}
		});
	},
	render_user: function() {
		var sid = wn.get_cookie("sid");
		if(sid && sid!=="Guest") {
			$(".btn-login-area").toggle(false);
			$(".logged-in").toggle(true);
			$(".full-name").html(wn.get_cookie("full_name"));
			$(".user-picture").attr("src", wn.get_cookie("user_image"));
		}
	},
	setup_push_state: function() {
		if(wn.supports_pjax()) {
			// hack for chrome's onload popstate call
			window.initial_href = window.location.href
			
			$(document).on("click", "#wrap a", wn.handle_click);
			
			$(window).on("popstate", function(event) {
				// hack for chrome's onload popstate call
				if(window.initial_href==location.href && window.previous_href==undefined) {
					wn.set_force_reload(true);
					return;
				}
				
				window.previous_href = location.href;
				var state = event.originalEvent.state;
				
				if(state) {
					wn.render_json(state);
				} else {
					console.log("state not found!");
				}
			});
		}
	},
	handle_click: function(event) {
		// taken from jquery pjax
		var link = event.currentTarget
		
		if (link.tagName.toUpperCase() !== 'A')
			throw "using pjax requires an anchor element"

		// Middle click, cmd click, and ctrl click should open
		// links in a new tab as normal.
		if ( event.which > 1 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey )
			return
			
		// Ignore cross origin links
		if ( location.protocol !== link.protocol || location.hostname !== link.hostname )
			return

		// Ignore anchors on the same page
		if (link.hash && link.href.replace(link.hash, '') ===
			 location.href.replace(location.hash, ''))
			 return
			 
		// Ignore empty anchor "foo.html#"
		if (link.href === location.href + '#')
			return
		
		// our custom logic
		if (link.href.indexOf("cmd=")!==-1)
			return
			
		event.preventDefault()
		wn.load_via_ajax(link.href);

	},
	load_via_ajax: function(href) {
		console.log("calling ajax");
		
		window.previous_href = href;
		history.pushState(null, null, href);
		
		$.ajax({ url: href, cache: false }).done(function(data) {
			history.replaceState(data, data.title, href);
			wn.render_json(data); 
		})
	},
	render_json: function(data) {
		if(data.reload) {
			window.location = location.href;
		// } else if(data.html) {
		// 	var newDoc = document.open("text/html", "replace");
		// 	newDoc.write(data.html);
		// 	newDoc.close();
		} else {
			$('[data-html-block]').each(function(i, section) {
				var $section = $(section);
				$section.html(data[$section.attr("data-html-block")] || "");
			});
			if(data.title) $("title").html(data.title);
			$(document).trigger("page_change");
		}
	},
	set_force_reload: function(reload) {
		// learned this from twitter's implementation
		window.history.replaceState({"reload": reload}, 
			window.document.title, location.href);
	},
	supports_pjax: function() {
		return (window.history && window.history.pushState && window.history.replaceState &&
		  // pushState isn't reliable on iOS until 5.
		  !navigator.userAgent.match(/((iPod|iPhone|iPad).+\bOS\s+[1-4]|WebApps\/.+CFNetwork)/))
	}
});


// Utility functions

function valid_email(id) {
	return (id.toLowerCase().search("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")==-1) ? 0 : 1;

}

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

wn.get_cookie = getCookie;

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
	if(!window.full_name) {
		if(localStorage) {
			localStorage.setItem("last_visited",
				window.location.href.replace(window.location.origin, ""));
		}
		window.location.href = "login";
	}
}

// check if logged in?
$(document).ready(function() {
	window.full_name = getCookie("full_name");
	window.logged_in = getCookie("sid") && getCookie("sid")!=="Guest";
	$("#website-login").toggleClass("hide", logged_in ? true : false);
	$("#website-post-login").toggleClass("hide", logged_in ? false : true);
	
	// switch to app link
	if(getCookie("system_user")==="yes") {
		$("#website-post-login .dropdown-menu").append('<li class="divider"></li>\
			<li><a href="app.html"><i class="icon-fixed-width icon-th-large"></i> Switch To App</a></li>');
	}
	
	wn.render_user();
	wn.setup_push_state()
	
	$(document).trigger("page_change");
});

$(document).on("page_change", function() {
	$(".page-header").toggleClass("hidden", !!!$(".page-header").text().trim());
	$(".page-footer").toggleClass("hidden", !!!$(".page-footer").text().trim());
	$(".page-breadcrumbs").toggleClass("hidden", !!!$(".page-breadcrumbs").text().trim());

	// add prive pages to sidebar
	if(website.private_pages && $(".page-sidebar").length) {
		$(data.private_pages).prependTo(".page-sidebar");
	}
	
	$(document).trigger("apply_permissions");
	wn.datetime.refresh_when();
});
