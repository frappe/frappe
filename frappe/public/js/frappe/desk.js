// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
/* eslint-disable no-console */

// __('Modules') __('Domains') __('Places') __('Administration') # for translation, don't remove

frappe.start_app = function () {
	if (!frappe.Application) return;
	frappe.assets.check();
	frappe.provide("frappe.app");
	frappe.provide("frappe.desk");
	frappe.app = new frappe.Application();
};

$(document).ready(function () {
	if (!frappe.utils.supportsES6) {
		frappe.msgprint({
			indicator: "red",
			title: __("Browser not supported"),
			message: __(
				"Some of the features might not work in your browser. Please update your browser to the latest version."
			),
		});
	}
	frappe.start_app();
});

frappe.Application = class Application {
	constructor() {
		this.startup();
	}

	startup() {
		frappe.socketio.init();
		frappe.model.init();

		this.setup_frappe_vue();
		this.load_bootinfo();
		this.load_user_permissions();
		this.make_nav_bar();
		this.set_favicon();
		this.setup_analytics();
		this.set_fullwidth_if_enabled();
		this.add_browser_class();
		this.setup_energy_point_listeners();
		this.setup_copy_doc_listener();

		frappe.ui.keys.setup();

		frappe.ui.keys.add_shortcut({
			shortcut: "shift+ctrl+g",
			description: __("Switch Theme"),
			action: () => {
				if (frappe.theme_switcher && frappe.theme_switcher.dialog.is_visible) {
					frappe.theme_switcher.hide();
				} else {
					frappe.theme_switcher = new frappe.ui.ThemeSwitcher();
					frappe.theme_switcher.show();
				}
			},
		});

		frappe.ui.add_system_theme_switch_listener();
		const root = document.documentElement;

		const observer = new MutationObserver(() => {
			frappe.ui.set_theme();
		});
		observer.observe(root, {
			attributes: true,
			attributeFilter: ["data-theme-mode"],
		});

		frappe.ui.set_theme();

		// page container
		this.make_page_container();
		if (
			!window.Cypress &&
			frappe.boot.onboarding_tours &&
			frappe.boot.user.onboarding_status != null
		) {
			let pending_tours = !frappe.boot.onboarding_tours.every(
				(tour) => frappe.boot.user.onboarding_status[tour[0]]?.is_complete
			);
			if (pending_tours && frappe.boot.onboarding_tours.length > 0) {
				frappe.require("onboarding_tours.bundle.js", () => {
					frappe.utils.sleep(1000).then(() => {
						frappe.ui.init_onboarding_tour();
					});
				});
			}
		}
		this.set_route();

		// trigger app startup
		$(document).trigger("startup");

		$(document).trigger("app_ready");

		if (frappe.boot.messages) {
			frappe.msgprint(frappe.boot.messages);
		}

		if (frappe.user_roles.includes("System Manager")) {
			// delayed following requests to make boot faster
			setTimeout(() => {
				this.show_change_log();
				this.show_update_available();
			}, 1000);
		}

		if (!frappe.boot.developer_mode) {
			let console_security_message = __(
				"Using this console may allow attackers to impersonate you and steal your information. Do not enter or paste code that you do not understand."
			);
			console.log(`%c${console_security_message}`, "font-size: large");
		}

		this.show_notes();

		if (frappe.ui.startup_setup_dialog && !frappe.boot.setup_complete) {
			frappe.ui.startup_setup_dialog.pre_show();
			frappe.ui.startup_setup_dialog.show();
		}

		frappe.realtime.on("version-update", function () {
			var dialog = frappe.msgprint({
				message: __(
					"The application has been updated to a new version, please refresh this page"
				),
				indicator: "green",
				title: __("Version Updated"),
			});
			dialog.set_primary_action(__("Refresh"), function () {
				location.reload(true);
			});
			dialog.get_close_btn().toggle(false);
		});

		// listen to build errors
		this.setup_build_events();

		if (frappe.sys_defaults.email_user_password) {
			var email_list = frappe.sys_defaults.email_user_password.split(",");
			for (var u in email_list) {
				if (email_list[u] === frappe.user.name) {
					this.set_password(email_list[u]);
				}
			}
		}

		// REDESIGN-TODO: Fix preview popovers
		this.link_preview = new frappe.ui.LinkPreview();
	}

	set_route() {
		if (frappe.boot && localStorage.getItem("session_last_route")) {
			frappe.set_route(localStorage.getItem("session_last_route"));
			localStorage.removeItem("session_last_route");
		} else {
			// route to home page
			frappe.router.route();
		}
		frappe.router.on("change", () => {
			$(".tooltip").hide();
		});
	}

	setup_frappe_vue() {
		Vue.prototype.__ = window.__;
		Vue.prototype.frappe = window.frappe;
	}

	set_password(user) {
		var me = this;
		frappe.call({
			method: "frappe.core.doctype.user.user.get_email_awaiting",
			args: {
				user: user,
			},
			callback: function (email_account) {
				email_account = email_account["message"];
				if (email_account) {
					var i = 0;
					if (i < email_account.length) {
						me.email_password_prompt(email_account, user, i);
					}
				}
			},
		});
	}

	email_password_prompt(email_account, user, i) {
		var me = this;
		const email_id = email_account[i]["email_id"];
		let d = new frappe.ui.Dialog({
			title: __("Password missing in Email Account"),
			fields: [
				{
					fieldname: "password",
					fieldtype: "Password",
					label: __(
						"Please enter the password for: <b>{0}</b>",
						[email_id],
						"Email Account"
					),
					reqd: 1,
				},
				{
					fieldname: "submit",
					fieldtype: "Button",
					label: __("Submit", null, "Submit password for Email Account"),
				},
			],
		});
		d.get_input("submit").on("click", function () {
			//setup spinner
			d.hide();
			var s = new frappe.ui.Dialog({
				title: __("Checking one moment"),
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "checking",
					},
				],
			});
			s.fields_dict.checking.$wrapper.html('<i class="fa fa-spinner fa-spin fa-4x"></i>');
			s.show();
			frappe.call({
				method: "frappe.email.doctype.email_account.email_account.set_email_password",
				args: {
					email_account: email_account[i]["email_account"],
					password: d.get_value("password"),
				},
				callback: function (passed) {
					s.hide();
					d.hide(); //hide waiting indication
					if (!passed["message"]) {
						frappe.show_alert(
							{ message: __("Login Failed please try again"), indicator: "error" },
							5
						);
						me.email_password_prompt(email_account, user, i);
					} else {
						if (i + 1 < email_account.length) {
							i = i + 1;
							me.email_password_prompt(email_account, user, i);
						}
					}
				},
			});
		});
		d.show();
	}
	load_bootinfo() {
		if (frappe.boot) {
			this.setup_workspaces();
			frappe.model.sync(frappe.boot.docs);
			this.check_metadata_cache_status();
			this.set_globals();
			this.sync_pages();
			frappe.router.setup();
			this.setup_moment();
			if (frappe.boot.print_css) {
				frappe.dom.set_style(frappe.boot.print_css, "print-style");
			}
			frappe.user.name = frappe.boot.user.name;
			frappe.router.setup();
		} else {
			this.set_as_guest();
		}
	}

	setup_workspaces() {
		frappe.modules = {};
		frappe.workspaces = {};
		for (let page of frappe.boot.allowed_workspaces || []) {
			frappe.modules[page.module] = page;
			frappe.workspaces[frappe.router.slug(page.name)] = page;
		}
	}

	load_user_permissions() {
		frappe.defaults.load_user_permission_from_boot();

		frappe.realtime.on(
			"update_user_permissions",
			frappe.utils.debounce(() => {
				frappe.defaults.update_user_permissions();
			}, 500)
		);
	}

	check_metadata_cache_status() {
		if (frappe.boot.metadata_version != localStorage.metadata_version) {
			frappe.assets.clear_local_storage();
			frappe.assets.init_local_storage();
		}
	}

	set_globals() {
		frappe.session.user = frappe.boot.user.name;
		frappe.session.logged_in_user = frappe.boot.user.name;
		frappe.session.user_email = frappe.boot.user.email;
		frappe.session.user_fullname = frappe.user_info().fullname;

		frappe.user_defaults = frappe.boot.user.defaults;
		frappe.user_roles = frappe.boot.user.roles;
		frappe.sys_defaults = frappe.boot.sysdefaults;

		frappe.ui.py_date_format = frappe.boot.sysdefaults.date_format
			.replace("dd", "%d")
			.replace("mm", "%m")
			.replace("yyyy", "%Y");
		frappe.boot.user.last_selected_values = {};

		// Proxy for user globals
		Object.defineProperties(window, {
			user: {
				get: function () {
					console.warn(
						"Please use `frappe.session.user` instead of `user`. It will be deprecated soon."
					);
					return frappe.session.user;
				},
			},
			user_fullname: {
				get: function () {
					console.warn(
						"Please use `frappe.session.user_fullname` instead of `user_fullname`. It will be deprecated soon."
					);
					return frappe.session.user;
				},
			},
			user_email: {
				get: function () {
					console.warn(
						"Please use `frappe.session.user_email` instead of `user_email`. It will be deprecated soon."
					);
					return frappe.session.user_email;
				},
			},
			user_defaults: {
				get: function () {
					console.warn(
						"Please use `frappe.user_defaults` instead of `user_defaults`. It will be deprecated soon."
					);
					return frappe.user_defaults;
				},
			},
			roles: {
				get: function () {
					console.warn(
						"Please use `frappe.user_roles` instead of `roles`. It will be deprecated soon."
					);
					return frappe.user_roles;
				},
			},
			sys_defaults: {
				get: function () {
					console.warn(
						"Please use `frappe.sys_defaults` instead of `sys_defaults`. It will be deprecated soon."
					);
					return frappe.user_roles;
				},
			},
		});
	}
	sync_pages() {
		// clear cached pages if timestamp is not found
		if (localStorage["page_info"]) {
			frappe.boot.allowed_pages = [];
			var page_info = JSON.parse(localStorage["page_info"]);
			$.each(frappe.boot.page_info, function (name, p) {
				if (!page_info[name] || page_info[name].modified != p.modified) {
					delete localStorage["_page:" + name];
				}
				frappe.boot.allowed_pages.push(name);
			});
		} else {
			frappe.boot.allowed_pages = Object.keys(frappe.boot.page_info);
		}
		localStorage["page_info"] = JSON.stringify(frappe.boot.page_info);
	}
	set_as_guest() {
		frappe.session.user = "Guest";
		frappe.session.user_email = "";
		frappe.session.user_fullname = "Guest";

		frappe.user_defaults = {};
		frappe.user_roles = ["Guest"];
		frappe.sys_defaults = {};
	}
	make_page_container() {
		if ($("#body").length) {
			$(".splash").remove();
			frappe.temp_container = $("<div id='temp-container' style='display: none;'>").appendTo(
				"body"
			);
			frappe.container = new frappe.views.Container();
		}
	}
	make_nav_bar() {
		// toolbar
		if (frappe.boot && frappe.boot.home_page !== "setup-wizard") {
			frappe.frappe_toolbar = new frappe.ui.toolbar.Toolbar();
		}
	}
	logout() {
		var me = this;
		me.logged_out = true;
		return frappe.call({
			method: "logout",
			callback: function (r) {
				if (r.exc) {
					return;
				}
				me.redirect_to_login();
			},
		});
	}
	handle_session_expired() {
		if (!frappe.app.session_expired_dialog) {
			var dialog = new frappe.ui.Dialog({
				title: __("Session Expired"),
				keep_open: true,
				fields: [
					{
						fieldtype: "Password",
						fieldname: "password",
						label: __("Please Enter Your Password to Continue"),
					},
				],
				onhide: () => {
					if (!dialog.logged_in) {
						frappe.app.redirect_to_login();
					}
				},
			});
			dialog.get_field("password").disable_password_checks();
			dialog.set_primary_action(__("Login"), () => {
				dialog.set_message(__("Authenticating..."));
				frappe.call({
					method: "login",
					args: {
						usr: frappe.session.user,
						pwd: dialog.get_values().password,
					},
					callback: (r) => {
						if (r.message === "Logged In") {
							dialog.logged_in = true;

							// revert backdrop
							$(".modal-backdrop").css({
								opacity: "",
								"background-color": "#334143",
							});
						}
						dialog.hide();
					},
					statusCode: () => {
						dialog.hide();
					},
				});
			});
			frappe.app.session_expired_dialog = dialog;
		}
		if (!frappe.app.session_expired_dialog.display) {
			frappe.app.session_expired_dialog.show();
			// add backdrop
			$(".modal-backdrop").css({
				opacity: 1,
				"background-color": "#4B4C9D",
			});
		}
	}
	redirect_to_login() {
		window.location.href = "/";
	}
	set_favicon() {
		var link = $('link[type="image/x-icon"]').remove().attr("href");
		$('<link rel="shortcut icon" href="' + link + '" type="image/x-icon">').appendTo("head");
		$('<link rel="icon" href="' + link + '" type="image/x-icon">').appendTo("head");
	}
	trigger_primary_action() {
		// to trigger change event on active input before triggering primary action
		$(document.activeElement).blur();
		// wait for possible JS validations triggered after blur (it might change primary button)
		setTimeout(() => {
			if (window.cur_dialog && cur_dialog.display) {
				// trigger primary
				cur_dialog.get_primary_btn().trigger("click");
			} else if (cur_frm && cur_frm.page.btn_primary.is(":visible")) {
				cur_frm.page.btn_primary.trigger("click");
			} else if (frappe.container.page.save_action) {
				frappe.container.page.save_action();
			}
		}, 100);
	}

	show_change_log() {
		var me = this;
		let change_log = frappe.boot.change_log;

		// frappe.boot.change_log = [{
		// 	"change_log": [
		// 		[<version>, <change_log in markdown>],
		// 		[<version>, <change_log in markdown>],
		// 	],
		// 	"description": "ERP made simple",
		// 	"title": "ERPNext",
		// 	"version": "12.2.0"
		// }];

		if (
			!Array.isArray(change_log) ||
			!change_log.length ||
			window.Cypress ||
			cint(frappe.boot.sysdefaults.disable_change_log_notification)
		) {
			return;
		}

		// Iterate over changelog
		var change_log_dialog = frappe.msgprint({
			message: frappe.render_template("change_log", { change_log: change_log }),
			title: __("Updated To A New Version 🎉"),
			wide: true,
		});
		change_log_dialog.keep_open = true;
		change_log_dialog.custom_onhide = function () {
			frappe.call({
				method: "frappe.utils.change_log.update_last_known_versions",
			});
			me.show_notes();
		};
	}

	show_update_available() {
		if (frappe.boot.sysdefaults.disable_system_update_notification) return;

		frappe.call({
			method: "frappe.utils.change_log.show_update_popup",
		});
	}

	setup_analytics() {
		if (window.mixpanel) {
			window.mixpanel.identify(frappe.session.user);
			window.mixpanel.people.set({
				$first_name: frappe.boot.user.first_name,
				$last_name: frappe.boot.user.last_name,
				$created: frappe.boot.user.creation,
				$email: frappe.session.user,
			});
		}
	}

	add_browser_class() {
		$("html").addClass(frappe.utils.get_browser().name.toLowerCase());
	}

	set_fullwidth_if_enabled() {
		frappe.ui.toolbar.set_fullwidth_if_enabled();
	}

	show_notes() {
		var me = this;
		if (frappe.boot.notes.length) {
			frappe.boot.notes.forEach(function (note) {
				if (!note.seen || note.notify_on_every_login) {
					var d = frappe.msgprint({ message: note.content, title: note.title });
					d.keep_open = true;
					d.custom_onhide = function () {
						note.seen = true;

						// Mark note as read if the Notify On Every Login flag is not set
						if (!note.notify_on_every_login) {
							frappe.call({
								method: "frappe.desk.doctype.note.note.mark_as_seen",
								args: {
									note: note.name,
								},
							});
						}

						// next note
						me.show_notes();
					};
				}
			});
		}
	}

	setup_build_events() {
		if (frappe.boot.developer_mode) {
			frappe.require("build_events.bundle.js");
		}
	}

	setup_energy_point_listeners() {
		frappe.realtime.on("energy_point_alert", (message) => {
			frappe.show_alert(message);
		});
	}

	setup_copy_doc_listener() {
		$("body").on("paste", (e) => {
			try {
				let pasted_data = frappe.utils.get_clipboard_data(e);
				let doc = JSON.parse(pasted_data);
				if (doc.doctype) {
					e.preventDefault();
					const sleep = frappe.utils.sleep;

					frappe.dom.freeze(__("Creating {0}", [doc.doctype]) + "...");
					// to avoid abrupt UX
					// wait for activity feedback
					sleep(500).then(() => {
						let res = frappe.model.with_doctype(doc.doctype, () => {
							let newdoc = frappe.model.copy_doc(doc);
							newdoc.__newname = doc.name;
							delete doc.name;
							newdoc.idx = null;
							newdoc.__run_link_triggers = false;
							frappe.set_route("Form", newdoc.doctype, newdoc.name);
							frappe.dom.unfreeze();
						});
						res && res.fail(frappe.dom.unfreeze);
					});
				}
			} catch (e) {
				//
			}
		});
	}

	setup_moment() {
		moment.updateLocale("en", {
			week: {
				dow: frappe.datetime.get_first_day_of_the_week_index(),
			},
		});
		moment.locale("en");
		moment.user_utc_offset = moment().utcOffset();
		if (frappe.boot.timezone_info) {
			moment.tz.add(frappe.boot.timezone_info);
		}
	}
};

frappe.get_module = function (m, default_module) {
	var module = frappe.modules[m] || default_module;
	if (!module) {
		return;
	}

	if (module._setup) {
		return module;
	}

	if (!module.label) {
		module.label = m;
	}

	if (!module._label) {
		module._label = __(module.label);
	}

	module._setup = true;

	return module;
};
