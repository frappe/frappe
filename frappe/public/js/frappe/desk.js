// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.start_app = function() {
	if(!frappe.Application)
		return;
	frappe.assets.check();
	frappe.provide('frappe.app');
	frappe.app = new frappe.Application();
}

$(document).ready(function() {
	frappe.start_app();
});

frappe.Application = Class.extend({
	init: function() {
		this.load_startup();
	},

	load_startup: function() {
		this.startup();
	},
	startup: function() {
		frappe.socket.init();
		frappe.model.init();
		this.load_bootinfo();
		this.make_nav_bar();
		this.set_favicon();
		frappe.ui.keys.setup();
		this.set_rtl();

		if(frappe.boot) {
			if(localStorage.getItem("session_last_route")) {
				window.location.hash = localStorage.getItem("session_last_route");
				localStorage.removeItem("session_last_route");
			}

		}

		// page container
		this.make_page_container();

		// route to home page
		frappe.route();

		// trigger app startup
		$(document).trigger('startup');

		this.start_notification_updates();

		$(document).trigger('app_ready');

		if (frappe.boot.messages) {
			frappe.msgprint(frappe.boot.messages);
		}

		if (frappe.boot.change_log && frappe.boot.change_log.length) {
			this.show_change_log();
		}

		// ask to allow notifications
		frappe.utils.if_notify_permitted();

		// listen to csrf_update
		frappe.realtime.on("csrf_generated", function(data) {
			// handles the case when a user logs in again from another tab
			// and it leads to invalid request in the current tab
			if (data.csrf_token && data.sid===frappe.get_cookie("sid")) {
				frappe.csrf_token = data.csrf_token;
			}
		});

		frappe.realtime.on("version-update", function() {
			var dialog = frappe.msgprint({
				message:__("The application has been updated to a new version, please refresh this page"),
				indicator: 'green',
				title: 'Version Updated'
			});
			dialog.set_primary_action("Refresh", function() {
				location.reload(true);
			});
			dialog.get_close_btn().toggle(false);
		});
	},

	load_bootinfo: function() {
		if(frappe.boot) {
			frappe.modules = {};
			frappe.boot.desktop_icons.forEach(function(m) { frappe.modules[m.module_name]=m; });
			frappe.model.sync(frappe.boot.docs);
			$.extend(frappe._messages, frappe.boot.__messages);
			this.check_metadata_cache_status();
			this.set_globals();
			this.sync_pages();
			moment.locale("en");
			moment.user_utc_offset = moment().utcOffset();
			if(frappe.boot.timezone_info) {
				moment.tz.add(frappe.boot.timezone_info);
			}
			if(frappe.boot.print_css) {
				frappe.dom.set_style(frappe.boot.print_css)
			}
		} else {
			this.set_as_guest();
		}
	},

	check_metadata_cache_status: function() {
		if(frappe.boot.metadata_version != localStorage.metadata_version) {
			frappe.assets.clear_local_storage();
			frappe.assets.init_local_storage();
		}
	},

	start_notification_updates: function() {
		var me = this;
		setInterval(function() {
			me.refresh_notifications();
		}, 30000);

		// first time loaded in boot
		$(document).trigger("notification-update");

		// refresh notifications if user is back after sometime
		$(document).on("session_alive", function() {
			me.refresh_notifications();
		})
	},

	refresh_notifications: function() {
		var me = this;
		if(frappe.session_alive) {
			return frappe.call({
				method: "frappe.desk.notifications.get_notifications",
				callback: function(r) {
					if(r.message) {
						$.extend(frappe.boot.notification_info, r.message);
						$(document).trigger("notification-update");

						// update in module views
						me.update_notification_count_in_modules();

						if(frappe.get_route()[0] != "messages") {
							if(r.message.new_messages.length) {
								frappe.utils.set_title_prefix("(" + r.message.new_messages.length + ")");
							}
						}
					}
				},
				freeze: false
			});
		}
	},

	update_notification_count_in_modules: function() {
		$.each(frappe.boot.notification_info.open_count_doctype, function(doctype, count) {
			if(count) {
				$('.open-notification.global[data-doctype="'+ doctype +'"]')
					.removeClass("hide").html(count > 20 ? "20+" : count);
			} else {
				$('.open-notification.global[data-doctype="'+ doctype +'"]')
					.addClass("hide");
			}
		});
	},

	set_globals: function() {
		// for backward compatibility
		frappe.session.user = frappe.boot.user.name;
		frappe.session.user_fullname = frappe.boot.user.name;
		user = frappe.boot.user.name;
		user_fullname = frappe.user_info(user).fullname;
		user_defaults = frappe.boot.user.defaults;
		user_roles = frappe.boot.user.roles;
		user_email = frappe.boot.user.email;
		sys_defaults = frappe.boot.sysdefaults;
		frappe.ui.py_date_format = frappe.boot.sysdefaults.date_format.replace('dd', '%d').replace('mm', '%m').replace('yyyy', '%Y');
		frappe.boot.user.last_selected_values = {};
	},
	sync_pages: function() {
		// clear cached pages if timestamp is not found
		if(localStorage["page_info"]) {
			frappe.boot.allowed_pages = [];
			page_info = JSON.parse(localStorage["page_info"]);
			$.each(frappe.boot.page_info, function(name, p) {
				if(!page_info[name] || (page_info[name].modified != p.modified)) {
					delete localStorage["_page:" + name];
				}
				frappe.boot.allowed_pages.push(name);
			});
		} else {
			frappe.boot.allowed_pages = keys(frappe.boot.page_info);
		}
		localStorage["page_info"] = JSON.stringify(frappe.boot.page_info);
	},
	set_as_guest: function() {
		// for backward compatibility
		user = {name:'Guest'};
		user = 'Guest';
		user_fullname = 'Guest';
		user_defaults = {};
		user_roles = ['Guest'];
		user_email = '';
		sys_defaults = {};
	},
	make_page_container: function() {
		if($("#body_div").length) {
			$(".splash").remove();
			frappe.temp_container = $("<div id='temp-container' style='display: none;'>")
				.appendTo("body");
			frappe.container = new frappe.views.Container();
		}
	},
	make_nav_bar: function() {
		// toolbar
		if(frappe.boot) {
			frappe.frappe_toolbar = new frappe.ui.toolbar.Toolbar();
		}

	},
	logout: function() {
		var me = this;
		me.logged_out = true;
		return frappe.call({
			method:'logout',
			callback: function(r) {
				if(r.exc) {
					console.log(r.exc);
					return;
				}
				me.redirect_to_login();
			}
		})
	},
	redirect_to_login: function() {
		window.location.href = '/';
	},
	set_favicon: function() {
		var link = $('link[type="image/x-icon"]').remove().attr("href");
		$('<link rel="shortcut icon" href="' + link + '" type="image/x-icon">').appendTo("head");
		$('<link rel="icon" href="' + link + '" type="image/x-icon">').appendTo("head");
	},

	trigger_primary_action: function() {
		if(cur_dialog) {
			// trigger primary
			cur_dialog.get_primary_btn().trigger("click");
		} else if(cur_frm && cur_frm.page.btn_primary.is(':visible')) {
			cur_frm.page.btn_primary.trigger('click');
		} else if(frappe.container.page.save_action) {
			frappe.container.page.save_action();
		}
	},

	set_rtl: function () {
		if (["ar", "he"].indexOf(frappe.boot.lang) >= 0) {
			$('body').addClass('frappe-rtl')
		}
	},

	show_change_log: function() {
		var d = frappe.msgprint(
			frappe.render_template("change_log", {"change_log": frappe.boot.change_log}),
			__("Updated To New Version")
		);
		d.keep_open = true;
		d.custom_onhide = function() {
			frappe.call({
				"method": "frappe.utils.change_log.update_last_known_versions"
			});
		};
	}
});

frappe.get_module = function(m, default_module) {
	var module = frappe.modules[m] || default_module;
	if (!module) {
		return;
	}

	if(module._setup) {
		return module;
	}

	if(module.type==="module" && !module.link) {
		module.link = "modules/" + module.module_name;
	}

	if(module.type==="list" && !module.link) {
		module.link = "List/" + module._doctype;
	}

	if (!module.link) module.link = "";

	if (!module._id) {
		module._id = module.link.toLowerCase().replace("/", "-").replace(' ', '-');
	}


	if(!module.label) {
		module.label = m;
	}

	if(!module._label) {
		module._label = __(module.label);
	}

	if(!module._doctype) {
		module._doctype = '';
	}

	module._setup = true;

	return module;
};

frappe.get_desktop_icons = function(show_hidden, show_global) {
	// filter valid icons
	var out = [];

	var add_to_out = function(module) {
		var module = frappe.get_module(module.module_name, module);
		module.app_icon = frappe.ui.app_icon.get_html(module);
		out.push(module);
	}

	var show_module = function(module) {
		var out = true;
		if(m.type==="page") {
			out = m.link in frappe.boot.page_info;
		}
		else if(m._doctype) {
			out = frappe.model.can_read(m._doctype);
		} else {
			if(m.module_name==='Learn') {
				// no permissions necessary for learn
				out = true;
			} else if(m.module_name==='Setup' && frappe.user.has_role('System Manager')) {
				out = true;
			} else {
				out = frappe.boot.user.allow_modules.indexOf(m.module_name) !== -1
			}
		}
		if(m.hidden&& !show_hidden) {
			out = false;
		}
		if(m.blocked && !show_global) {
			out = false;
		}
		return out;
	}

	for (var i=0, l=frappe.boot.desktop_icons.length; i < l; i++) {
		var m = frappe.boot.desktop_icons[i];
		if ((['Setup', 'Core'].indexOf(m.module_name) === -1)
			&& show_module(m)) {
				add_to_out(m)
		}
	}

	if(user_roles.indexOf('System Manager')!=-1) {
		var m = frappe.get_module('Setup');
		if(show_module(m)) add_to_out(m)
	}

	if(user_roles.indexOf('Administrator')!=-1) {
		var m = frappe.get_module('Core');
		if(show_module(m)) add_to_out(m)
	}

	return out;
};

frappe.add_to_desktop = function(label, doctype) {
	frappe.call({
		method: 'frappe.desk.doctype.desktop_icon.desktop_icon.add_user_icon',
		args: {
			link: frappe.get_route_str(),
			label: label,
			type: 'link',
			_doctype: doctype
		},
		callback: function(r) {
			if(r.message) {
				show_alert(__("Added"));
			}
		}
	});
}
