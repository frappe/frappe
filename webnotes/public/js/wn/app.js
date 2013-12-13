// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

if(!console) {
	var console = {
		log: function(txt) {
			// suppress
		}
	}
}

$(document).ready(function() {
	wn.assets.check();
	wn.provide('wn.app');
	$.extend(wn.app, new wn.Application());
});

wn.Application = Class.extend({
	init: function() {
		this.load_startup();
	},
	
	load_startup: function() {
		var me = this;
		if(window.app) {
			return wn.call({
				method: 'startup',
				callback: function(r, rt) {
					wn.provide('wn.boot');
					wn.boot = r;
					if(wn.boot.profile.name==='Guest' || wn.boot.profile.user_type==="Website User") {
						window.location = 'index.html';
						return;
					}
					me.startup();
				}
			});
		} else {
			this.startup();
		}		
	},
	startup: function() {
		// load boot info
		this.load_bootinfo();

		// page container
		this.make_page_container();
		
		// navbar
		this.make_nav_bar();
			
		// favicon
		this.set_favicon();
		
		if(user!="Guest") this.set_user_display_settings();
		
		this.setup_keyboard_shortcuts();
		
		// control panel startup code
		this.run_custom_startup_code();

		if(wn.boot) {
			// route to home page
			wn.route();	
		}
		
		// trigger app startup
		$(document).trigger('startup');

		this.start_notification_updates();
		
		$(document).trigger('app_ready');
	},
	
	set_user_display_settings: function() {
		wn.ui.set_user_background(wn.boot.profile.background_image);
	},
	
	load_bootinfo: function() {
		if(wn.boot) {
			wn.control_panel = wn.boot.control_panel;
			wn.modules = wn.boot.modules;
			this.check_metadata_cache_status();
			this.set_globals();
			this.sync_pages();
		} else {
			this.set_as_guest();
		}
	},
	
	check_metadata_cache_status: function() {
		if(wn.boot.metadata_version != localStorage.metadata_version) {
			localStorage.clear();
			console.log("Cleared Cache - New Metadata");
			localStorage.metadata_version = wn.boot.metadata_version;
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
		if(wn.session_alive) {
			return wn.call({
				method: "webnotes.core.doctype.notification_count.notification_count.get_notifications",
				callback: function(r) {
					if(r.message) {
						$.extend(wn.boot.notification_info, r.message);
						$(document).trigger("notification-update");
					}
				},
				no_spinner: true
			});
		}
	},
	
	set_globals: function() {
		// for backward compatibility
		profile = wn.boot.profile;
		user = wn.boot.profile.name;
		user_fullname = wn.user_info(user).fullname;
		user_defaults = profile.defaults;
		user_roles = profile.roles;
		user_email = profile.email;
		sys_defaults = wn.boot.sysdefaults;		
	},
	sync_pages: function() {
		// clear cached pages if timestamp is not found
		if(localStorage["page_info"]) {
			wn.boot.allowed_pages = [];
			page_info = JSON.parse(localStorage["page_info"]);
			$.each(wn.boot.page_info, function(name, modified) {
				if(page_info[name]!=modified) {
					delete localStorage["_page:" + name];
				}
				wn.boot.allowed_pages.push(name);
			});
		} else {
			wn.boot.allowed_pages = keys(wn.boot.page_info);
		}
		localStorage["page_info"] = JSON.stringify(wn.boot.page_info);
	},
	set_as_guest: function() {
		// for backward compatibility
		profile = {name:'Guest'};
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
			wn.temp_container = $("<div id='temp-container' style='display: none;'>")
				.appendTo("body");
			wn.container = new wn.views.Container();
		}
	},
	make_nav_bar: function() {
		// toolbar
		if(wn.boot) {
			wn.container.wntoolbar = new wn.ui.toolbar.Toolbar();
		}
	},
	logout: function() {
		var me = this;
		me.logged_out = true;
		return wn.call({
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
		window.location.href = 'index.html';
	},
	set_favicon: function() {
		var link = $('link[type="image/x-icon"]').remove().attr("href");
		$('<link rel="shortcut icon" href="' + link + '" type="image/x-icon">').appendTo("head");
		$('<link rel="icon" href="' + link + '" type="image/x-icon">').appendTo("head");
	},
	
	setup_keyboard_shortcuts: function() {
		$(document)
			.keydown("meta+g ctrl+g", function(e) {
				wn.ui.toolbar.search.show();
				return false;
			})
			.keydown("meta+s ctrl+s", function(e) {
				if(cur_frm) {
					cur_frm.save_or_update();
				} else if(wn.container.page.save_action) {
					wn.container.page.save_action();
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

	},
	
	run_custom_startup_code: function() {
		if(wn.control_panel.custom_startup_code)
			eval(wn.control_panel.custom_startup_code);
	}
})