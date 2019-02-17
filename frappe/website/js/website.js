// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
/* eslint-disable no-console */

import hljs from './syntax_highlight';

frappe.provide("website");
frappe.provide("frappe.awesome_bar_path");
window.cur_frm = null;

$.extend(frappe, {
	boot: {
		lang: 'en'
	},
	_assets_loaded: [],
	require: function(url, callback) {

		let async = false;
		if (callback) {
			async = true;
		}

		if(frappe._assets_loaded.indexOf(url)!==-1) {
			callback && callback();
			return;
		}

		return $.ajax({
			url: url,
			async: async,
			dataType: "text",
			success: function(data) {
				var el;
				if(url.split(".").splice(-1) == "js") {
					el = document.createElement('script');
				} else {
					el = document.createElement('style');
				}
				el.appendChild(document.createTextNode(data));
				document.getElementsByTagName('head')[0].appendChild(el);
				frappe._assets_loaded.push(url);

				callback && callback();
			}
		});
	},
	hide_message: function() {
		$('.message-overlay').remove();
	},
	call: function(opts) {
		// opts = {"method": "PYTHON MODULE STRING", "args": {}, "callback": function(r) {}}
		if (typeof arguments[0]==='string') {
			opts = {
				method: arguments[0],
				args: arguments[1],
				callback: arguments[2]
			}
		}

		frappe.prepare_call(opts);
		if(opts.freeze) {
			frappe.freeze();
		}
		return $.ajax({
			type: opts.type || "POST",
			url: "/",
			data: opts.args,
			dataType: "json",
			headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
			statusCode: opts.statusCode || {
				404: function() {
					frappe.msgprint(__("Not found"));
				},
				403: function() {
					frappe.msgprint(__("Not permitted"));
				},
				200: function(data) {
					if(opts.callback)
						opts.callback(data);
					if(opts.success)
						opts.success(data);
				}
			}
		}).always(function(data) {
			if(opts.freeze) {
				frappe.unfreeze();
			}

			// executed before statusCode functions
			if(data.responseText) {
				try {
					data = JSON.parse(data.responseText);
				} catch (e) {
					data = {};
				}
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
			var server_messages = JSON.parse(data._server_messages || '[]');
			server_messages = $.map(server_messages, function(v) {
				// temp fix for messages sent as dict
				try {
					return JSON.parse(v).message;
				} catch (e) {
					return v;
				}
			}).join('<br>');

			if(opts.error_msg) {
				$(opts.error_msg).html(server_messages).toggle(true);
			} else {
				frappe.msgprint(server_messages);
			}
		}

		if(data.exc) {
			// if(opts.btn) {
			// 	$(opts.btn).addClass($(opts.btn).is('button') || $(opts.btn).hasClass('btn') ? "btn-danger" : "text-danger");
			// 	setTimeout(function() { $(opts.btn).removeClass("btn-danger text-danger"); }, 1000);
			// }
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
			// if(opts.btn) {
			// 	$(opts.btn).addClass($(opts.btn).is('button') || $(opts.btn).hasClass('btn') ? "btn-success" : "text-success");
			// 	setTimeout(function() { $(opts.btn).removeClass("btn-success text-success"); }, 1000);
			// }
		}
		if(opts.msg && data.message) {
			$(opts.msg).html(data.message).toggle(true);
		}

		if(opts.always) {
			opts.always(data);
		}
	},
	show_message: function(text, icon) {
		if(!icon) icon="fa fa-refresh fa-spin";
		frappe.hide_message();
		$('<div class="message-overlay"></div>')
			.html('<div class="content"><i class="'+icon+' text-muted"></i><br>'
				+text+'</div>').appendTo(document.body);
	},
	get_sid: function() {
		var sid = frappe.get_cookie("sid");
		return sid && sid !== "Guest";
	},
	send_message: function(opts, btn) {
		return frappe.call({
			type: "POST",
			method: "frappe.www.contact.send_message",
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
					if(callback) {
						return callback(r);
					}
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

			$('.user-image-wrapper').html(frappe.avatar(null, 'avatar-small'));
			$('.user-image-sidebar').html(frappe.avatar(null, 'avatar-small'));
			$('.user-image-myaccount').html(frappe.avatar(null, 'avatar-large'));
		}
	},
	freeze_count: 0,
	freeze: function(msg) {
		// blur
		if(!$('#freeze').length) {
			var freeze = $('<div id="freeze" class="modal-backdrop fade"></div>')
				.appendTo("body");

			freeze.html(repl('<div class="freeze-message-container"><div class="freeze-message">%(msg)s</div></div>',
				{msg: msg || ""}));

			setTimeout(function() {
				freeze.addClass("in");
			}, 1);

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
				if(!frappe.freeze_count) {
					freeze.remove();
				}
			}, 150);
		}
	},

	trigger_ready: function() {
		frappe.ready_events.forEach(function(fn) {
			fn();
		});
	},

	highlight_code_blocks: function() {
		hljs.initHighlighting();
	},
	bind_filters: function() {
		// set in select
		$(".filter").each(function() {
			var key = $(this).attr("data-key");
			var val = frappe.utils.get_url_arg(key).replace(/\+/g, " ");

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
		};

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
				return false;
			}
		});
	},
	do_search: function(val) {
		var path = (frappe.awesome_bar_path && frappe.awesome_bar_path[location.pathname]
			|| window.search_path || location.pathname);

		window.location.href = path + "?txt=" + encodeURIComponent(val);
	},
	set_search_path: function(path) {
		frappe.awesome_bar_path[location.pathname] = path;
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
		});
	},
	get_navbar_search: function() {
		return $(".navbar .search, .sidebar .search");
	},
	is_user_logged_in: function() {
		return frappe.get_cookie("sid") && frappe.get_cookie("sid") !== "Guest";
	},
	add_switch_to_desk: function() {
		$('.switch-to-desk').removeClass('hidden');
	}
});


// Utility functions

window.valid_email = function(id) {
	// eslint-disable-next-line
	return (id.toLowerCase().search("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")==-1) ? 0 : 1;
}

window.validate_email = valid_email;

window.cstr = function(s) {
	return s==null ? '' : s+'';
}

window.is_null = function is_null(v) {
	if(v===null || v===undefined || cstr(v).trim()==="") return true;
};

window.is_html = function is_html(txt) {
	if(txt.indexOf("<br>")==-1 && txt.indexOf("<p")==-1
		&& txt.indexOf("<img")==-1 && txt.indexOf("<div")==-1) {
		return false;
	}
	return true;
};

window.ask_to_login = function ask_to_login() {
	if(!frappe.is_user_logged_in()) {
		if(localStorage) {
			localStorage.setItem("last_visited",
				window.location.href.replace(window.location.origin, ""));
		}
		window.location.href = "login";
	}
};

// check if logged in?
$(document).ready(function() {
	window.full_name = frappe.get_cookie("full_name");
	var logged_in = frappe.is_user_logged_in();
	$("#website-login").toggleClass("hide", logged_in ? true : false);
	$("#website-post-login").toggleClass("hide", logged_in ? false : true);
	$(".logged-in").toggleClass("hide", logged_in ? false : true);

	frappe.bind_navbar_search();

	// switch to app link
	if(frappe.get_cookie("system_user")==="yes" && logged_in) {
		frappe.add_switch_to_desk();
	}

	frappe.render_user();

	$(document).trigger("page-change");
});

$(document).on("page-change", function() {
	$(document).trigger("apply_permissions");
	$('.dropdown-toggle').dropdown();

	//multilevel dropdown fix
	$('.dropdown-menu .dropdown-submenu .dropdown-toggle').on('click', function(e) {
		e.stopPropagation();
		$(this).parent().parent().parent().addClass('open');
	});

	$.extend(frappe, frappe.get_cookies());
	frappe.session = {'user': frappe.user_id};

	frappe.datetime.refresh_when();
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


frappe.ready(function() {
	frappe.call({
		method: 'frappe.website.doctype.website_settings.website_settings.is_chat_enabled',
		callback: (r) => {
			if (r.message) {
				frappe.require('/assets/js/moment-bundle.min.js', () => {
					frappe.require('/assets/js/chat.js', () => {
						frappe.chat.setup();
					});
				});
			}
		}
	});
	frappe.socketio.init(window.socketio_port);
});
