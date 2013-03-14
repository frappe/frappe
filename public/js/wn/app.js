// Copyright 2013 Web Notes Technologies Pvt Ltd
// MIT Licensed. See license.txt

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
			wn.call({
				method: 'startup',
				callback: function(r, rt) {
					wn.provide('wn.boot');
					wn.boot = r;
					if(wn.boot.profile.name=='Guest') {
						window.location = 'index.html';
						return;
					}
					me.startup();
				}
			})
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

		// trigger app startup
		$(document).trigger('startup');
		
		if(wn.boot) {
			// route to home page
			wn.route();	
		}
		
		$(document).trigger('app_ready');
	},
	
	set_user_display_settings: function() {
		if(wn.boot.profile.background_image) {
			wn.ui.set_user_background(wn.boot.profile.background_image);
		}
		if(wn.boot.profile.theme) {
			wn.ui.set_theme(wn.boot.profile.theme);
		}		
	},
	
	load_bootinfo: function() {
		if(wn.boot) {
			wn.control_panel = wn.boot.control_panel;
			this.set_globals();
			this.sync_pages();
			
		} else {
			this.set_as_guest();
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
		wn.call({
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
		var favicon ='\
			<link rel="shortcut icon" href="' + link + '" type="image/x-icon"> \
			<link rel="icon" href="' + link + '" type="image/x-icon">'

		$(favicon).appendTo('head');
	}
})