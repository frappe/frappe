// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//

wn.Application = Class.extend({
	init: function() {
		var me = this;
		if(window.app) {
			this.load_app_js(function() { me.load_startup() });			
		} else {
			this.load_startup();
		}
	},
	load_app_js: function(callback) {
		var all_app = localStorage.getItem("all-app");
		
		if(all_app) {
			wn.dom.eval(all_app);
			callback();
			return;
		}
		
		var dialog = new wn.ui.Dialog({
			title: "Loading...",
			width: 500,
			user_cannot_cancel: true
		});
		
		dialog.show();
		
		wn.messages.waiting(dialog.body, "", 5);
		var bar = $(dialog.body).find(".bar");

		$.ajax({
			url: "js/all-app.js",
			success: function(data, status, xhr) {
				// add it to localstorage
				localStorage.setItem('all-app', xhr.responseText);
				dialog.hide();		
				callback();
			},
			xhr: function() {
				var xhr = jQuery.ajaxSettings.xhr();
				interval = setInterval(function() {
					if(xhr.readyState > 2) {
				    	var total =  parseInt(xhr.getResponseHeader('Content-Length'));
				    	var completed = parseInt(xhr.responseText.length);
						var percent = (100.0 / total * completed).toFixed(2);
						bar.css('width', (percent < 10 ? 10 : percent) + '%');
					}
				}, 50);
				wn.last_xhr = xhr;
				return xhr;
			},
			error: function(xhr, status, e) {
				console.log(e.message);
				eval(xhr.responseText);
			}
		});
		
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

		// trigger app startup
		$(document).trigger('startup');
		
		if(wn.boot) {
			// route to home page
			wn.route();	
		}
		
		$(document).trigger('app_ready');
	},
	load_bootinfo: function() {
		if(wn.boot) {
			wn.control_panel = wn.boot.control_panel;
			this.set_globals();
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
		wn.temp_container = $("<div id='#temp-container' style='display: none;'>")
			.appendTo("body");
		wn.container = new wn.views.Container();
		wn.views.make_403();
		wn.views.make_404();
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