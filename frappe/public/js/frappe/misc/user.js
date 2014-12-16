// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// misc user functions

frappe.user_info = function(uid) {
	if(!uid)
		uid = user;
	if(!(frappe.boot.user_info && frappe.boot.user_info[uid])) {
		return {fullname: toTitle(uid.split("@")[0]) || "Unknown"};
	}
	return frappe.boot.user_info[uid];
}

frappe.avatar = function(user, css_class, title) {
	var image = frappe.utils.get_file_link(frappe.user_info(user).image);
	if(!title) title = frappe.user_info(user).fullname;

	return repl('<span class="avatar %(css_class)s" title="%(title)s">\
		<img src="%(image)s"></span>', {
			image: image,
			title: title,
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
	if(!src) src = "assets/frappe/images/ui/random-polygons.jpg";

	// hack! load background image asap, before page is rendered
	$('<img src="'+src+'" style="height: 1px; width: 1px; margin-bottom: -1px;">').appendTo("body");

	frappe.dom.set_style(repl('%(selector)s { \
		background: url("%(src)s") center center;\
		background-attachment: fixed; \
		%(style)s \
	}', {src:src, selector:selector, style: style==="Fill Screen" ? "background-size: cover;" : ""}));
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
					if(module.link && modules_list.indexOf(m)==-1) {
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
				if(hidden_list.indexOf(m)==-1) return m; else return null;
			});
		}

		// hide based on permission
		modules_list = $.map(modules_list, function(m) {
			var type = frappe.modules[m] && frappe.modules[m].type;
			var ret = null;
			switch(type) {
				case "module":
					if(frappe.boot.user.allow_modules.indexOf(m)!=-1)
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
					ret = m;
					break;
				default:
					ret = m;
			}
			return ret;
		})

		return modules_list;
	},
	get_user_desktop_items: function() {
		var user_list = frappe.defaults.get_default("_user_desktop_items");
		if(!user_list) {
			user_list = frappe.user.get_desktop_items();
		}
		return user_list;
	},
	is_report_manager: function() {
		return frappe.user.has_role(['Administrator', 'System Manager', 'Report Manager']);
	},
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
