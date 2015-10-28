// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("website");
frappe.provide("frappe.search_path");

$.extend(frappe, {
	_assets_loaded: [],
	require: function(url) {
		if(frappe._assets_loaded.indexOf(url)!==-1) return;
		$.ajax({
			url: url,
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
				frappe._assets_loaded.push(url);
			}
		});
	},
	hide_message: function(text) {
		$('.message-overlay').remove();
	},
	call: function(opts) {
		// opts = {"method": "PYTHON MODULE STRING", "args": {}, "callback": function(r) {}}
		frappe.prepare_call(opts);
		return $.ajax({
			type: opts.type || "POST",
			url: "/",
			data: opts.args,
			dataType: "json",
			headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
			statusCode: {
				404: function(xhr) {
					frappe.msgprint(__("Not found"));
				},
				403: function(xhr) {
					frappe.msgprint(__("Not permitted"));
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
			frappe.process_response(opts, data);
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
			//NProgress.start();
		}
	},
	process_response: function(opts, data) {
		//if(!opts.no_spinner) NProgress.done();

		if(opts.btn) {
			$(opts.btn).prop("disabled", false);
		}

		if (data._server_messages) {
			var server_messages = (JSON.parse(data._server_messages || '[]')).join("<br>");
			if(opts.error_msg) {
				$(opts.error_msg).html(server_messages).toggle(true);
			} else {
				frappe.msgprint(server_messages);
			}
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

		if(opts.always) {
			opts.always(data);
		}
	},
	show_message: function(text, icon) {
		if(!icon) icon="icon-refresh icon-spin";
		frappe.hide_message();
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
		return frappe.get_modal(title || "Message", html).modal("show");
	},
	send_message: function(opts, btn) {
		return frappe.call({
			type: "POST",
			method: "frappe.templates.pages.contact.send_message",
			btn: btn,
			args: opts,
			callback: opts.callback
		});
	},
	has_permission: function(doctype, docname, perm_type, callback) {
		return frappe.call({
			type: "GET",
			method: "frappe.client.has_permission",
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
		var sid = frappe.get_cookie("sid");
		if(sid && sid!=="Guest") {
			$(".btn-login-area").toggle(false);
			$(".logged-in").toggle(true);
			$(".full-name").html(frappe.get_cookie("full_name"));
			$(".user-image").attr("src", frappe.get_cookie("user_image"));
		}
	},
	setup_push_state: function() {
		if(frappe.supports_pjax()) {
			// hack for chrome's onload popstate call
			window.initial_href = window.location.href
			$(document).on("click", "a", frappe.handle_click);

			$(window).on("popstate", function(event) {
				// don't run this on hash change
				if (location.hash && (!window.previous_href || window.previous_href.replace(location.hash, '') ===
					 location.href.replace(location.hash, '')))
					 return;

				// hack for chrome's onload popstate call
				if(window.initial_href==location.href && window.previous_href==undefined) {
					window.history.replaceState({"reload": true},
						window.document.title, location.href);
					return;
				}

				window.previous_href = location.href;
				var state = event.originalEvent.state;
				if(!state) {
					window.location.reload();
					return;
				}
				frappe.render_json(state);
			});
		}
	},
	handle_click: function(event) {
		// taken from jquery pjax
		var link = event.currentTarget

		if (link.tagName.toUpperCase() !== 'A')
			throw "using pjax requires an anchor element";

		// Middle click, cmd click, and ctrl click should open
		// links in a new tab as normal.
		if ( event.which > 1 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey )
			return;

		if (link.getAttribute("target"))
			return;

		// Ignore cross origin links
		if ( location.protocol !== link.protocol || location.hostname !== link.hostname )
			return;

		// Ignore anchors on the same page
		if (link.hash && link.href.replace(link.hash, '') ===
			 location.href.replace(location.hash, ''))
			 return;

		// Ignore empty anchor "foo.html#"
		if (link.href === location.href + '#')
			return;

		// our custom logic
		if (link.href.indexOf("cmd=")!==-1 || link.hasAttribute("no-pjax"))
			return;

		// has an extension, but is not htm/html
		var last_part = (link.href.split("/").slice(-1)[0] || "");
		if (last_part.indexOf(".")!==-1 && (last_part.indexOf(".htm")===-1))
			return;

		event.preventDefault();
		frappe.load_via_ajax(link.href);

	},
	load_via_ajax: function(href) {
		// console.log("calling ajax", href);
		window.previous_href = href;
		history.pushState(null, null, href);

		var _render = function(data) {
			try {
				history.replaceState(data, data.title, href);
			} catch(e) {
				// data too big (?)
				history.replaceState(null, data.title, href);
			}
			scroll(0,0);
			frappe.render_json(data);
		};

		frappe.freeze();
		$.ajax({
			url: href,
			cache: false,
			statusCode: {
				200: _render,
				404: function(xhr) { _render(xhr.responseJSON); }
			}
		}).fail(function(xhr, status, error) {
			window.location.reload();
		}).always(function() {
			frappe.unfreeze();
		});
	},
	render_json: function(data) {
		if (data.reload) {
			window.location.reload();
			return;
		}

		$('[data-html-block]').each(function(i, section) {
			var $section = $(section);
			var stype = $section.attr("data-html-block");


			// handle meta separately
			if (stype==="meta_block") return;

			var block_data = data[stype] || "";

			// NOTE: use frappe.ready instead of $.ready for reliable execution
			if(stype==="script") {
				$section.remove();
				$("<script data-html-block='script'></script>")
					.html(block_data)
					.appendTo("body");
			} else if(stype==="script_lib") {
				// render once
				if(!$("[data-block-html='script_lib'][data-path='"+data.path+"']").length) {
					$("<script data-block-html='script_lib' data-path='"+data.path+"'></script>")
					.html(data.script_lib)
					.appendTo("body");
				}
			} else {
				$section.html(block_data);
			}
		});
		if(data.title) $("title").html(data.title);

		// change meta tags
		$('[data-html-block="meta_block"]').remove();
		if(data.meta_block) {
			$("head").append(data.meta_block);
		}

		// change id of current page
		$(".page-container").attr("id", "page-" + data.path);

		// set data-path value in body
		$("body").attr("data-path", data.path);

		// clear page-header-right
		$(".page-header-right").html("");

		window.ga && ga('send', 'pageview', location.pathname);
		$(document).trigger("page-change");
	},
	supports_pjax: function() {
		return (window.history && window.history.pushState && window.history.replaceState &&
		  // pushState isn't reliable on iOS until 5.
		  !navigator.userAgent.match(/((iPod|iPhone|iPad).+\bOS\s+[1-4]|WebApps\/.+CFNetwork)/))
	},
	get_pathname: function() {
		return location.pathname;
	},
	page_ready_events: {},
	ready: function(fn) {
		// console.log("frappe.ready", frappe.get_pathname());
		if (!frappe.page_ready_events[frappe.get_pathname()]) {
			frappe.page_ready_events[frappe.get_pathname()] = []
		}
		frappe.page_ready_events[frappe.get_pathname()].push(fn);
	},
	freeze_count: 0,
	freeze: function(msg) {
		// blur
		if(!$('#freeze').length) {
			var freeze = $('<div id="freeze" class="modal-backdrop fade"></div>')
				.on("click", function() {
					if (cur_frm && cur_frm.cur_grid) {
						cur_frm.cur_grid.toggle_view();
						return false;
					}
				})
				.appendTo("body");

			freeze.html(repl('<div class="freeze-message-container"><div class="freeze-message">%(msg)s</div></div>',
				{msg: msg || ""}));

			setTimeout(function() { freeze.addClass("in") }, 1);

		} else {
			$("#freeze").addClass("in");
		}
		frappe.freeze_count++;
	},
	unfreeze: function() {
		if(!frappe.freeze_count) return; // anything open?
		frappe.freeze_count--;
		if(!frappe.freeze_count) {
			var freeze = $('#freeze').removeClass("in");
			setTimeout(function() {
				if(!frappe.freeze_count) { freeze.remove(); }
			}, 150);
		}
	},

	trigger_ready: function() {
		var ready_functions = frappe.page_ready_events[frappe.get_pathname()];
		if (ready_functions && ready_functions.length) {
			for (var i=0, l=ready_functions.length; i < l; i++) {
				var ready = ready_functions[i];
				ready && ready();
			}
		}

		// remove them so that they aren't fired again and again!
		delete frappe.page_ready_events[frappe.get_pathname()];
	},
	highlight_code_blocks: function() {
		if(hljs) {
			$('pre code').each(function(i, block) {
				hljs.highlightBlock(block);
			});
		}
	},
	bind_filters: function() {
		// set in select
		$(".filter").each(function() {
			var key = $(this).attr("data-key");
			var val = get_url_arg(key).replace(/\+/g, " ");

			if(val) $(this).val(val);
		});

		// search url
		var search = function() {
			var args = {};
			$(".filter").each(function() {
				var val = $(this).val();
				if(val) args[$(this).attr("data-key")] = val;
			});

			window.location.href = location.pathname + "?" + $.param(args);
		}

		$(".filter").on("change", function() {
			search();
		});
	},
	bind_navbar_search: function() {
		frappe.get_navbar_search().on("keypress", function(e) {
			var val = $(this).val();
			if(e.which===13 && val) {
				$(this).val("").blur();
				frappe.do_search(val);
				$(".offcanvas").removeClass("active-left active-right");
				return false;
			}
		});
	},
	do_search: function(val) {
		var path = (frappe.search_path && frappe.search_path[location.pathname]
			|| window.search_path || location.pathname);
		frappe.load_via_ajax(path + "?txt=" + encodeURIComponent(val));
	},
	set_search_path: function(path) {
		frappe.search_path[location.pathname] = path;
	},
	make_navbar_active: function() {
		var pathname = window.location.pathname;
		$(".navbar-nav a.active").removeClass("active");
		$(".navbar-nav a").each(function() {
			var href = $(this).attr("href");
			if(href===pathname) {
				$(this).addClass("active");
				return false;
			}
		})
	},
	toggle_template_blocks: function() {
		// this assumes frappe base template
		$(".page-footer").toggleClass("hidden",
			!!!$(".page-footer").text().trim());

		// hide breadcrumbs if no breadcrumb content or if it is same as the header
		$("[data-html-block='breadcrumbs'] .breadcrumb").toggleClass("hidden",
			!$("[data-html-block='breadcrumbs']").text().trim() ||
			$("[data-html-block='breadcrumbs']").text().trim()==$("[data-html-block='header']").text().trim());

		// adjust page header block
		var page_header_actions = $(".page-header-actions-block");
		if(page_header_actions.text().trim()) {
			page_header_actions.parent().removeClass("hidden");
			$(".page-header-block").parent().removeClass("col-sm-12").addClass("col-sm-8");
		} else {
			page_header_actions.parent().addClass("hidden");
			$(".page-header-block").parent().removeClass("col-sm-8").addClass("col-sm-12");
		}

	},
	get_navbar_search: function() {
		return $(".navbar .search, .sidebar .search");
	},
	is_user_logged_in: function() {
		return window.full_name ? true : false;
	}
});


// Utility functions

function valid_email(id) {
	return (id.toLowerCase().search("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")==-1) ? 0 : 1;

}

var validate_email = valid_email;

function get_url_arg(name) {
	return get_query_params()[name] || "";
}

function get_query_params() {
	var query_params = {};
	var query_string = location.search.substring(1);
	var query_list = query_string.split("&");
	for (var i=0, l=query_list.length; i < l; i++ ){
		var pair = query_list[i].split("=");
		var key = pair[0];
		if (!key) {
			continue;
		}

		var value = pair[1];
		if (typeof value === "string") {
			value = decodeURIComponent(value);
		}

		if (key in query_params) {
			if (typeof query_params[key] === undefined) {
				query_params[key] = [];
			} else if (typeof query_params[key] === "string") {
				query_params[key] = [query_params[key]];
			}
			query_params[key].push(value);
		} else {
			query_params[key] = value;
		}
	}
	return query_params;
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

frappe.get_cookie = getCookie;

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
	if(!frappe.is_user_logged_in()) {
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

	frappe.bind_navbar_search();

	$(".toggle-sidebar").on("click", function() {
		$(".offcanvas").addClass("active-right");
		return false;
	});

	// collapse offcanvas sidebars!
	$(".offcanvas .sidebar").on("click", "a", function() {
		$(".offcanvas").removeClass("active-left active-right");
	});

	$(".offcanvas-main-section-overlay").on("click", function() {
		$(".offcanvas").removeClass("active-left active-right");
		return false;
	});

	// switch to app link
	if(getCookie("system_user")==="yes") {
		$("#website-post-login .dropdown-menu").append('<li><a href="/desk" no-pjax>Switch To Desk</a></li>');
	}

	frappe.render_user();
	frappe.setup_push_state();

	$(document).trigger("page-change");
});

$(document).on("page-change", function() {
	$(document).trigger("apply_permissions");
	frappe.datetime.refresh_when();
	frappe.toggle_template_blocks();
	frappe.trigger_ready();
	frappe.bind_filters();
	frappe.highlight_code_blocks();
	frappe.make_navbar_active();

	// scroll to hash
	if (window.location.hash) {
		var element = document.getElementById(window.location.hash.substring(1));
		element && element.scrollIntoView(true);
	}
});
