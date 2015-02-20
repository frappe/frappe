// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

$(document).ready(function() {
	frappe.assets.check();
	frappe.provide('frappe.app');
	$.extend(frappe.app, new frappe.Application());
});

frappe.Application = Class.extend({
	init: function() {
		this.load_startup();
	},

	load_startup: function() {
		this.startup();
	},
	startup: function() {
		this.load_bootinfo();
		this.make_nav_bar();
		this.set_favicon();
		this.setup_keyboard_shortcuts();

		if(frappe.boot) {
			if(localStorage.getItem("session_lost_route")) {
				window.location.hash = localStorage.getItem("session_lost_route");
				localStorage.removeItem("session_lost_route");
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
	},

	load_bootinfo: function() {
		if(frappe.boot) {
			frappe.modules = frappe.boot.modules;
			frappe.model.sync(frappe.boot.docs);
			this.check_metadata_cache_status();
			this.set_globals();
			this.sync_pages();
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
			localStorage.clear();
			console.log("Cleared Cache - New Metadata");
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
					}
				},
				no_spinner: true
			});
		}
	},

	update_notification_count_in_modules: function() {
		$.each(frappe.boot.notification_info.open_count_doctype, function(doctype, count) {
			if(count) {
				$('.open-notification[data-doctype="'+ doctype +'"]')
					.removeClass("hide").html(count);
			} else {
				$('.open-notification[data-doctype="'+ doctype +'"]')
					.addClass("hide");
			}
		});
	},

	set_globals: function() {
		// for backward compatibility
		user = frappe.boot.user.name;
		user_fullname = frappe.user_info(user).fullname;
		user_defaults = frappe.boot.user.defaults;
		user_roles = frappe.boot.user.roles;
		user_email = frappe.boot.user.email;
		sys_defaults = frappe.boot.sysdefaults;
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

		// collapse offcanvas sidebars!
		$(".offcanvas .sidebar").on("click", "a", function() {
			$(".offcanvas").removeClass("active-left active-right");
		});

		$(".offcanvas-main-section-overlay").on("click", function() {
			$(".offcanvas").removeClass("active-left active-right");
		});
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

	setup_keyboard_shortcuts: function() {
		$(document)
			.keydown("meta+g ctrl+g", function(e) {
				$("#navbar-search").focus()
				return false;
			})
			.keydown("meta+s ctrl+s", function(e) {
				e.preventDefault();
				if(cur_frm) {
					cur_frm.save_or_update();
				} else if(frappe.container.page.save_action) {
					frappe.container.page.save_action();
				}
				return false;
			})
			.keydown("esc", function(e) {
				var open_row = $(".grid-row-open");
				if(open_row.length) {
					var grid_row = open_row.data("grid_row");
					grid_row.toggle_view(false);
				}
				return false;
			})
			.keydown("ctrl+down meta+down", function(e) {
				var open_row = $(".grid-row-open");
				if(open_row.length) {
					var grid_row = open_row.data("grid_row");
					grid_row.toggle_view(false, function() { grid_row.open_next() });
					return false;
				}
			})
			.keydown("ctrl+up meta+up", function(e) {
				var open_row = $(".grid-row-open");
				if(open_row.length) {
					var grid_row = open_row.data("grid_row");
					grid_row.toggle_view(false, function() { grid_row.open_prev() });
					return false;
				}
			})
			.keydown("ctrl+n meta+n", function(e) {
				var open_row = $(".grid-row-open");
				if(open_row.length) {
					var grid_row = open_row.data("grid_row");
					grid_row.toggle_view(false, function() { grid_row.grid.add_new_row(grid_row.doc.idx, null, true); });
					return false;
				}
			})
			.keydown("ctrl+shift+r meta+shift+r", function(e) {
				frappe.ui.toolbar.clear_cache();
			});

	}
});

frappe.get_module = function(m) {
	var module = frappe.modules[m];
	if (!module) {
		return;
	}

	module.name = m;

	if(module.type==="module" && !module.link) {
		module.link = "Module/" + m;
	}

	if (!module.link) module.link = "";

	if (!module._id) {
		module._id = module.link.toLowerCase().replace("/", "-");
	}


	if(!module.label) {
		module.label = m;
	}

	if(!module._label) {
		module._label = __(module.label || module.name);
	}

	return module;
};
