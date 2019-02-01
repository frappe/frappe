// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
/* eslint-disable no-console */

frappe.start_app = function() {
	if(!frappe.Application)
		return;
	frappe.assets.check();
	frappe.provide('frappe.app');
	frappe.app = new frappe.Application();
};

$(document).ready(function() {
	if(!frappe.utils.supportsES6) {
		frappe.msgprint({
			indicator: 'red',
			title: __('Browser not supported'),
			message: __('Some of the features might not work in your browser. Please update your browser to the latest version.')
		});
	}
	frappe.start_app();
});

frappe.Application = Class.extend({
	init: function() {
		this.startup();
	},

	startup: function() {
		frappe.socketio.init();
		frappe.model.init();

		if(frappe.boot.status==='failed') {
			frappe.msgprint({
				message: frappe.boot.error,
				title: __('Session Start Failed'),
				indicator: 'red',
			});
			throw 'boot failed';
		}

		this.load_bootinfo();
		this.load_user_permissions();
		this.make_nav_bar();
		this.set_favicon();
		this.setup_analytics();
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
		} else {
			this.show_notes();
		}

		this.show_update_available();

		if(frappe.ui.startup_setup_dialog && !frappe.boot.setup_complete) {
			frappe.ui.startup_setup_dialog.pre_show();
			frappe.ui.startup_setup_dialog.show();
		}

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
				title: __('Version Updated')
			});
			dialog.set_primary_action(__("Refresh"), function() {
				location.reload(true);
			});
			dialog.get_close_btn().toggle(false);
		});

		// listen to build errors
		this.setup_build_error_listener();

		if (frappe.sys_defaults.email_user_password){
			var email_list =  frappe.sys_defaults.email_user_password.split(',');
			for (var u in email_list) {
				if (email_list[u]===frappe.user.name){
					this.set_password(email_list[u]);
				}
			}
		}

	},
	set_password: function(user) {
		var me=this;
		frappe.call({
			method: 'frappe.core.doctype.user.user.get_email_awaiting',
			args: {
				"user": user
			},
			callback: function(email_account) {
				email_account = email_account["message"];
				if (email_account) {
					var i = 0;
					if (i < email_account.length) {
						me.email_password_prompt( email_account, user, i);
					}
				}
			}
		});
	},

	email_password_prompt: function(email_account,user,i) {
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Email Account setup please enter your password for: '+email_account[i]["email_id"]),
			fields: [
				{	'fieldname': 'password',
					'fieldtype': 'Password',
					'label': 'Email Account Password',
					'reqd': 1
				},
				{
					"fieldtype": "Button",
					"label": __("Submit")
				}
			]
		});
		d.get_input("submit").on("click", function() {
			//setup spinner
			d.hide();
			var s = new frappe.ui.Dialog({
				title: __("Checking one moment"),
				fields: [{
					"fieldtype": "HTML",
					"fieldname": "checking"
				}]
			});
			s.fields_dict.checking.$wrapper.html('<i class="fa fa-spinner fa-spin fa-4x"></i>');
			s.show();
			frappe.call({
				method: 'frappe.core.doctype.user.user.set_email_password',
				args: {
					"email_account": email_account[i]["email_account"],
					"user": user,
					"password": d.get_value("password")
				},
				callback: function(passed) {
					s.hide();
					d.hide();//hide waiting indication
					if (!passed["message"]) {
						frappe.show_alert("Login Failed please try again", 5);
						me.email_password_prompt(email_account, user, i);
					} else {
						if (i + 1 < email_account.length) {
							i = i + 1;
							me.email_password_prompt(email_account, user, i);
						}
					}

				}
			});
		});
		d.show();
	},
	load_bootinfo: function() {
		if(frappe.boot) {
			frappe.modules = {};
			frappe.boot.desktop_icons.forEach(function(m) {
				frappe.modules[m.module_name]=m;
			});
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
				frappe.dom.set_style(frappe.boot.print_css, "print-style");
			}
			frappe.user.name = frappe.boot.user.name;
		} else {
			this.set_as_guest();
		}
	},

	load_user_permissions: function() {
		frappe.defaults.update_user_permissions();

		frappe.realtime.on('update_user_permissions', frappe.utils.debounce(() => {
			frappe.defaults.update_user_permissions();
		}, 500));
	},

	check_metadata_cache_status: function() {
		if(frappe.boot.metadata_version != localStorage.metadata_version) {
			frappe.assets.clear_local_storage();
			frappe.assets.init_local_storage();
		}
	},

	start_notification_updates: function() {
		var me = this;

		// refresh_notifications will be called only once during a 1 second window
		this.refresh_notifications = frappe.utils.debounce(this.refresh_notifications.bind(this), 1000);

		// kickoff
		this.refresh_notifications();

		frappe.realtime.on('clear_notifications', () => {
			me.refresh_notifications();
		});

		// first time loaded in boot
		$(document).trigger("notification-update");

		// refresh notifications if user is back after sometime
		$(document).on("session_alive", function() {
			me.refresh_notifications();
		});
	},

	refresh_notifications: function() {
		var me = this;
		if(frappe.session_alive && frappe.boot && frappe.boot.home_page !== 'setup-wizard') {
			return frappe.call({
				type: 'GET',
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
					.removeClass("hide").html(count > 99 ? "99+" : count);
			} else {
				$('.open-notification.global[data-doctype="'+ doctype +'"]')
					.addClass("hide");
			}
		});
	},

	set_globals: function() {
		frappe.session.user = frappe.boot.user.name;
		frappe.session.user_email = frappe.boot.user.email;
		frappe.session.user_fullname = frappe.user_info().fullname;

		frappe.user_defaults = frappe.boot.user.defaults;
		frappe.user_roles = frappe.boot.user.roles;
		frappe.sys_defaults = frappe.boot.sysdefaults;

		frappe.ui.py_date_format = frappe.boot.sysdefaults.date_format.replace('dd', '%d').replace('mm', '%m').replace('yyyy', '%Y');
		frappe.boot.user.last_selected_values = {};

		// Proxy for user globals
		Object.defineProperties(window, {
			'user': {
				get: function() {
					console.warn('Please use `frappe.session.user` instead of `user`. It will be deprecated soon.');
					return frappe.session.user;
				}
			},
			'user_fullname': {
				get: function() {
					console.warn('Please use `frappe.session.user_fullname` instead of `user_fullname`. It will be deprecated soon.');
					return frappe.session.user;
				}
			},
			'user_email': {
				get: function() {
					console.warn('Please use `frappe.session.user_email` instead of `user_email`. It will be deprecated soon.');
					return frappe.session.user_email;
				}
			},
			'user_defaults': {
				get: function() {
					console.warn('Please use `frappe.user_defaults` instead of `user_defaults`. It will be deprecated soon.');
					return frappe.user_defaults;
				}
			},
			'roles': {
				get: function() {
					console.warn('Please use `frappe.user_roles` instead of `roles`. It will be deprecated soon.');
					return frappe.user_roles;
				}
			},
			'sys_defaults': {
				get: function() {
					console.warn('Please use `frappe.sys_defaults` instead of `sys_defaults`. It will be deprecated soon.');
					return frappe.user_roles;
				}
			}
		});
	},
	sync_pages: function() {
		// clear cached pages if timestamp is not found
		if(localStorage["page_info"]) {
			frappe.boot.allowed_pages = [];
			var page_info = JSON.parse(localStorage["page_info"]);
			$.each(frappe.boot.page_info, function(name, p) {
				if(!page_info[name] || (page_info[name].modified != p.modified)) {
					delete localStorage["_page:" + name];
				}
				frappe.boot.allowed_pages.push(name);
			});
		} else {
			frappe.boot.allowed_pages = Object.keys(frappe.boot.page_info);
		}
		localStorage["page_info"] = JSON.stringify(frappe.boot.page_info);
	},
	set_as_guest: function() {
		frappe.session.user = 'Guest';
		frappe.session.user_email = '';
		frappe.session.user_fullname = 'Guest';

		frappe.user_defaults = {};
		frappe.user_roles = ['Guest'];
		frappe.sys_defaults = {};
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
		if(frappe.boot && frappe.boot.home_page!=='setup-wizard') {
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
					return;
				}
				me.redirect_to_login();
			}
		});
	},
	handle_session_expired: function() {
		if(!frappe.app.session_expired_dialog) {
			var dialog = new frappe.ui.Dialog({
				title: __('Session Expired'),
				keep_open: true,
				fields: [
					{ fieldtype:'Password', fieldname:'password',
						label: __('Please Enter Your Password to Continue') },
				],
				onhide: () => {
					if (!dialog.logged_in) {
						frappe.app.redirect_to_login();
					}
				}
			});
			dialog.set_primary_action(__('Login'), () => {
				frappe.call({
					method: 'login',
					args: {
						usr: frappe.session.user,
						pwd: dialog.get_values().password
					},
					callback: (r) => {
						if (r.message==='Logged In') {
							dialog.logged_in = true;

							// revert backdrop
							$('.modal-backdrop').css({
								'opacity': '',
								'background-color': '#334143'
							});
						}
						dialog.hide();
					},
					statusCode: () => {
						dialog.hide();
					}
				});
			});
			frappe.app.session_expired_dialog = dialog;
		}
		if(!frappe.app.session_expired_dialog.display) {
			frappe.app.session_expired_dialog.show();
			// add backdrop
			$('.modal-backdrop').css({
				'opacity': 1,
				'background-color': '#4B4C9D'
			});
		}
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
		if(window.cur_dialog && cur_dialog.display) {
			// trigger primary
			cur_dialog.get_primary_btn().trigger("click");
		} else if(cur_frm && cur_frm.page.btn_primary.is(':visible')) {
			cur_frm.page.btn_primary.trigger('click');
		} else if(frappe.container.page.save_action) {
			frappe.container.page.save_action();
		}
	},

	set_rtl: function() {
		if (["ar", "he", "fa"].indexOf(frappe.boot.lang) >= 0) {
			var ls = document.createElement('link');
			ls.rel="stylesheet";
			ls.href= "assets/css/frappe-rtl.css";
			document.getElementsByTagName('head')[0].appendChild(ls);
			$('body').addClass('frappe-rtl');
		}
	},

	show_change_log: function() {
		var me = this;
		var d = frappe.msgprint(
			frappe.render_template("change_log", {"change_log": frappe.boot.change_log}),
			__("Updated To New Version")
		);
		d.keep_open = true;
		d.custom_onhide = function() {
			frappe.call({
				"method": "frappe.utils.change_log.update_last_known_versions"
			});
			me.show_notes();
		};
	},

	show_update_available: () => {
		frappe.call({
			"method": "frappe.utils.change_log.show_update_popup"
		});
	},

	setup_analytics: function() {
		if(window.mixpanel) {
			window.mixpanel.identify(frappe.session.user);
			window.mixpanel.people.set({
				"$first_name": frappe.boot.user.first_name,
				"$last_name": frappe.boot.user.last_name,
				"$created": frappe.boot.user.creation,
				"$email": frappe.session.user
			});
		}
	},

	show_notes: function() {
		var me = this;
		if(frappe.boot.notes.length) {
			frappe.boot.notes.forEach(function(note) {
				if(!note.seen || note.notify_on_every_login) {
					var d = frappe.msgprint({message:note.content, title:note.title});
					d.keep_open = true;
					d.custom_onhide = function() {
						note.seen = true;

						// Mark note as read if the Notify On Every Login flag is not set
						if (!note.notify_on_every_login) {
							frappe.call({
								method: "frappe.desk.doctype.note.note.mark_as_seen",
								args: {
									note: note.name
								}
							});
						}

						// next note
						me.show_notes();

					};
				}
			});
		}
	},

	setup_build_error_listener() {
		if (frappe.boot.developer_mode) {
			frappe.realtime.on('build_error', (data) => {
				console.log(data);
			});
		}
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
		// links can have complex values that range beyond simple plain text names, and so do not make for robust IDs.
		// an example from python: "link": r"javascript:eval('window.open(\'timetracking\', \'_self\')')"
		// this snippet allows a module to open a custom html page in the same window.
		module._id = module.module_name.toLowerCase();
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

	// hidden == hidden from desktop
	// blocked == no view from modules either

	var out = [];

	var add_to_out = function(module) {
		module = frappe.get_module(module.module_name, module);
		module.app_icon = frappe.ui.app_icon.get_html(module);
		out.push(module);
	};

	var show_module = function(m) {
		var out = true;
		if(m.type==="page") {
			out = m.link in frappe.boot.page_info;
		} else if(m.force_show) {
			out = true;
		} else if(m._report) {
			out = m._report in frappe.boot.user.all_reports;
		} else if(m._doctype) {
			//out = frappe.model.can_read(m._doctype);
			out = frappe.boot.user.can_read.includes(m._doctype);
		} else {
			if(['Help', 'Settings'].includes(m.module_name)) {
				// no permissions necessary for learn
				out = true;
			} else if(m.module_name==='Setup' && frappe.user.has_role('System Manager')) {
				out = true;
			} else {
				out = frappe.boot.user.allow_modules.indexOf(m.module_name) !== -1;
			}
		}
		if(m.hidden && !show_hidden) {
			out = false;
		}
		if(m.blocked && !show_global) {
			out = false;
		}
		return out;
	};

	let m;
	for (var i=0, l=frappe.boot.desktop_icons.length; i < l; i++) {
		m = frappe.boot.desktop_icons[i];
		if ((['Setup', 'Core'].indexOf(m.module_name) === -1) && show_module(m)) {
			add_to_out(m);
		}
	}

	if(frappe.user_roles.includes('System Manager')) {
		m = frappe.get_module('Setup');
		if(show_module(m)) add_to_out(m);
	}

	if(frappe.user_roles.includes('Administrator')) {
		m = frappe.get_module('Core');
		if(show_module(m)) add_to_out(m);
	}

	return out;
};

frappe.add_to_desktop = function(label, doctype, report) {
	frappe.call({
		method: 'frappe.desk.doctype.desktop_icon.desktop_icon.add_user_icon',
		args: {
			'link': frappe.get_route_str(),
			'label': label,
			'type': 'link',
			'_doctype': doctype,
			'_report': report
		},
		callback: function(r) {
			if(r.message) {
				frappe.show_alert(__("Added"));
			}
		}
	});
};
