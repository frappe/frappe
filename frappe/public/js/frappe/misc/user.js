// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// misc user functions

frappe.user_info = function(uid) {
	if(!uid)
		uid = user;

	if(!(frappe.boot.user_info && frappe.boot.user_info[uid])) {
		var user_info = {fullname: toTitle(uid.split("@")[0]) || "Unknown"};
	} else {
		var user_info = frappe.boot.user_info[uid];
	}

	user_info.abbr = get_abbr(user_info.fullname);

	return user_info;
}

var get_abbr = function(txt, max_length) {
	if (!txt) return "";
	var abbr = "";
	$.each(txt.split(" "), function(i, w) {
		if (abbr.length >= (max_length || 2)) {
			// break
			return false;

		} else if (!w.trim().length) {
			// continue
			return true;
		}

		abbr += w.trim()[0];
	});

	return abbr || "?";
}

frappe.avatar = function(user, css_class, title) {
	var image = frappe.utils.get_file_link(frappe.user_info(user).image);
	if(!title) title = frappe.user_info(user).fullname;

	return repl('<span class="avatar %(css_class)s" title="%(title)s">\
		<img src="%(image)s" alt="%(abbr)s"></span>', {
			image: image,
			title: title,
			abbr: frappe.user_info(user).abbr,
			css_class: css_class || "avatar-small"
		});
}

frappe.gravatars = {};
frappe.get_gravatar = function(email_id) {
	frappe.require("/assets/frappe/js/lib/md5.min.js");
	if(!frappe.gravatars[email_id]) {
		frappe.gravatars[email_id] = "https://secure.gravatar.com/avatar/" + md5(email_id) + "?d=retro";
	}
	return frappe.gravatars[email_id];
}

frappe.ui.set_user_background = function(src, selector, style) {
	if(!selector) selector = "#page-desktop";
	if(!style) style = "Fill Screen";
	if(src) {
		var background = repl('background: url("%(src)s") center center;', {src: src});
	} else {
		var background = "background-color: #4B4C9D;";
	}

	frappe.dom.set_style(repl('%(selector)s { \
		%(background)s \
		background-attachment: fixed; \
		%(style)s \
	}', {
		selector:selector,
		background:background,
		style: style==="Fill Screen" ? "background-size: cover;" : ""
	}));
}

frappe.provide('frappe.user');

$.extend(frappe.user, {
	name: (frappe.boot ? frappe.boot.user.name : 'Guest'),
	full_name: function(uid) {
		return uid===user ?
			__("You") :
			frappe.user_info(uid).fullname;
	},
	image: function(uid) {
		return frappe.user_info(uid).image;
	},
	abbr: function(uid) {
		return frappe.user_info(uid).abbr;
	},
	has_role: function(rl) {
		if(typeof rl=='string')
			rl = [rl];
		for(var i in rl) {
			if((frappe.boot ? frappe.boot.user.roles : ['Guest']).indexOf(rl[i])!=-1)
				return true;
		}
	},
	get_desktop_items: function(global) {
		// get user sequence preference
		var modules_list = null;
		if(!global) {
			var user_list = frappe.defaults.get_default("_desktop_items");
			if(user_list && user_list.length)
				var modules_list = user_list;

			if(modules_list) {
				// add missing modules - they will be hidden anyways by the view
				$.each(frappe.modules, function(m, module) {
					var module = frappe.get_module(m);
					if(modules_list.indexOf(m)===-1) {
						modules_list.push(m);
					}
				});
			}
		}

		if(!modules_list || !modules_list.length) {
			// all modules
			modules_list = keys(frappe.modules).sort();
		}

		// filter hidden modules
		if(frappe.boot.hidden_modules && modules_list) {
			var hidden_list = JSON.parse(frappe.boot.hidden_modules);
			var modules_list = $.map(modules_list, function(m) {
				if(hidden_list.indexOf(m)==-1 || (frappe.modules[m] && frappe.modules[m].force_show)) return m; else return null;
			});
		}

		// hide based on permission
		modules_list = $.map(modules_list, function(m) {
			var type = frappe.modules[m] && frappe.modules[m].type;
			var ret = null;
			switch(type) {
				case "module":
					if(frappe.boot.user.allow_modules.indexOf(m)!=-1 || frappe.modules[m].is_help)
						ret = m;
					break;
				case "page":
					if(frappe.boot.allowed_pages.indexOf(frappe.modules[m].link)!=-1)
						ret = m;
					break;
				case "list":
					if(frappe.model.can_read(frappe.modules[m].doctype))
						ret = m;
					break;
				case "view":
					ret = m;
					break;
				case "setup":
					if(frappe.user.has_role("System Manager") || frappe.user.has_role("Administrator"))
						ret = m;
					break;
				default:
					ret = m;
			}

			return ret;
		});

		return modules_list;
	},
	get_user_desktop_items: function() {
		if(!frappe.user.modules) {
			var user_list = frappe.defaults.get_default("_user_desktop_items");
			if(!user_list) {
				user_list = frappe.user.get_desktop_items();
			}

			// filter_blocked_modules
			user_list = $.map(user_list, function(m) {
				if(frappe.user.is_module_blocked(m)) {
					return null;
				} else {
					return m;
				}
			});

			frappe.user.modules = user_list;
		}
		return frappe.user.modules;
	},
	is_module_blocked: function(m) {
		return frappe.boot.user.block_modules && frappe.boot.user.block_modules.indexOf(m)!==-1;
	},
	is_report_manager: function() {
		return frappe.user.has_role(['Administrator', 'System Manager', 'Report Manager']);
	},

	get_formatted_email: function(email) {
		var fullname = frappe.user.full_name(email);

		if (!fullname) {
			return email;
		} else {
			// to quote or to not
			var quote = '';

			// only if these special characters are found
			// why? To make the output same as that in python!
			if (fullname.search(/[\[\]\\()<>@,:;".]/) !== -1) {
				quote = '"';
			}

			return repl('%(quote)s%(fullname)s%(quote)s <%(email)s>', {
				fullname: fullname,
				email: email,
				quote: quote
			});
		}
	}
});

frappe.session_alive = true;
$(document).bind('mousemove', function() {
	if(frappe.session_alive===false) {
		$(document).trigger("session_alive");
	}
	frappe.session_alive = true;
	if(frappe.session_alive_timeout)
		clearTimeout(frappe.session_alive_timeout);
	frappe.session_alive_timeout = setTimeout('frappe.session_alive=false;', 30000);
})
