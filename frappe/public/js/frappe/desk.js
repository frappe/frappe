// Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
/* eslint-disable no-console */

// __('Modules') __('Domains') __('Places') __('Administration') # for translation, don't remove

nts.start_app = function () {
	if (!nts.Application) return;
	nts.assets.check();
	nts.provide("nts.app");
	nts.provide("nts.desk");
	nts.app = new nts.Application();
};

$(document).ready(function () {
	if (!nts.utils.supportsES6) {
		nts.msgprint({
			indicator: "red",
			title: __("Browser not supported"),
			message: __(
				"Some of the features might not work in your browser. Please update your browser to the latest version."
			),
		});
	}
	nts.start_app();
});

nts.Application = class Application {
	constructor() {
		this.startup();
	}

	startup() {
		nts.realtime.init();
		nts.model.init();

		this.load_bootinfo();
		this.load_user_permissions();
		this.make_nav_bar();
		this.set_favicon();
		this.set_fullwidth_if_enabled();
		this.add_browser_class();
		this.setup_energy_point_listeners();
		this.setup_copy_doc_listener();
		this.setup_broadcast_listeners();

		nts.ui.keys.setup();

		nts.ui.keys.add_shortcut({
			shortcut: "shift+ctrl+g",
			description: __("Switch Theme"),
			action: () => {
				if (nts.theme_switcher && nts.theme_switcher.dialog.is_visible) {
					nts.theme_switcher.hide();
				} else {
					nts.theme_switcher = new nts.ui.ThemeSwitcher();
					nts.theme_switcher.show();
				}
			},
		});

		nts.ui.add_system_theme_switch_listener();
		const root = document.documentElement;

		const observer = new MutationObserver(() => {
			nts.ui.set_theme();
		});
		observer.observe(root, {
			attributes: true,
			attributeFilter: ["data-theme-mode"],
		});

		nts.ui.set_theme();

		// page container
		this.make_page_container();
		if (
			!window.Cypress &&
			nts.boot.onboarding_tours &&
			nts.boot.user.onboarding_status != null
		) {
			let pending_tours = !nts.boot.onboarding_tours.every(
				(tour) => nts.boot.user.onboarding_status[tour[0]]?.is_complete
			);
			if (pending_tours && nts.boot.onboarding_tours.length > 0) {
				nts.require("onboarding_tours.bundle.js", () => {
					nts.utils.sleep(1000).then(() => {
						nts.ui.init_onboarding_tour();
					});
				});
			}
		}
		this.set_route();

		// trigger app startup
		$(document).trigger("startup");

		$(document).trigger("app_ready");

		if (nts.boot.messages) {
			nts.msgprint(nts.boot.messages);
		}

		if (nts.user_roles.includes("System Manager")) {
			// delayed following requests to make boot faster
			setTimeout(() => {
				this.show_change_log();
				this.show_update_available();
			}, 1000);
		}

		if (!nts.boot.developer_mode) {
			let console_security_message = __(
				"Using this console may allow attackers to impersonate you and steal your information. Do not enter or paste code that you do not understand."
			);
			console.log(`%c${console_security_message}`, "font-size: large");
		}

		this.show_notes();

		if (nts.ui.startup_setup_dialog && !nts.boot.setup_complete) {
			nts.ui.startup_setup_dialog.pre_show();
			nts.ui.startup_setup_dialog.show();
		}

		nts.realtime.on("version-update", function () {
			var dialog = nts.msgprint({
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

		if (nts.sys_defaults.email_user_password) {
			var email_list = nts.sys_defaults.email_user_password.split(",");
			for (var u in email_list) {
				if (email_list[u] === nts.user.name) {
					this.set_password(email_list[u]);
				}
			}
		}

		// REDESIGN-TODO: Fix preview popovers
		this.link_preview = new nts.ui.LinkPreview();

		nts.broadcast.emit("boot", {
			csrf_token: nts.csrf_token,
			user: nts.session.user,
		});
	}

	set_route() {
		if (nts.boot && localStorage.getItem("session_last_route")) {
			nts.set_route(localStorage.getItem("session_last_route"));
			localStorage.removeItem("session_last_route");
		} else {
			// route to home page
			nts.router.route();
		}
		nts.router.on("change", () => {
			$(".tooltip").hide();
		});
	}

	set_password(user) {
		var me = this;
		nts.call({
			method: "nts.core.doctype.user.user.get_email_awaiting",
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
		let d = new nts.ui.Dialog({
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
			var s = new nts.ui.Dialog({
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
			nts.call({
				method: "nts.email.doctype.email_account.email_account.set_email_password",
				args: {
					email_account: email_account[i]["email_account"],
					password: d.get_value("password"),
				},
				callback: function (passed) {
					s.hide();
					d.hide(); //hide waiting indication
					if (!passed["message"]) {
						nts.show_alert(
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
		if (nts.boot) {
			this.setup_workspaces();
			nts.model.sync(nts.boot.docs);
			this.check_metadata_cache_status();
			this.set_globals();
			this.sync_pages();
			nts.router.setup();
			this.setup_moment();
			if (nts.boot.print_css) {
				nts.dom.set_style(nts.boot.print_css, "print-style");
			}
			nts.user.name = nts.boot.user.name;
			nts.router.setup();
		} else {
			this.set_as_guest();
		}
	}

	setup_workspaces() {
		nts.modules = {};
		nts.workspaces = {};
		for (let page of nts.boot.allowed_workspaces || []) {
			nts.modules[page.module] = page;
			nts.workspaces[nts.router.slug(page.name)] = page;
		}
	}

	load_user_permissions() {
		nts.defaults.load_user_permission_from_boot();

		nts.realtime.on(
			"update_user_permissions",
			nts.utils.debounce(() => {
				nts.defaults.update_user_permissions();
			}, 500)
		);
	}

	check_metadata_cache_status() {
		if (nts.boot.metadata_version != localStorage.metadata_version) {
			nts.assets.clear_local_storage();
			nts.assets.init_local_storage();
		}
	}

	set_globals() {
		nts.session.user = nts.boot.user.name;
		nts.session.logged_in_user = nts.boot.user.name;
		nts.session.user_email = nts.boot.user.email;
		nts.session.user_fullname = nts.user_info().fullname;

		nts.user_defaults = nts.boot.user.defaults;
		nts.user_roles = nts.boot.user.roles;
		nts.sys_defaults = nts.boot.sysdefaults;

		nts.ui.py_date_format = nts.boot.sysdefaults.date_format
			.replace("dd", "%d")
			.replace("mm", "%m")
			.replace("yyyy", "%Y");
		nts.boot.user.last_selected_values = {};
	}
	sync_pages() {
		// clear cached pages if timestamp is not found
		if (localStorage["page_info"]) {
			nts.boot.allowed_pages = [];
			var page_info = JSON.parse(localStorage["page_info"]);
			$.each(nts.boot.page_info, function (name, p) {
				if (!page_info[name] || page_info[name].modified != p.modified) {
					delete localStorage["_page:" + name];
				}
				nts.boot.allowed_pages.push(name);
			});
		} else {
			nts.boot.allowed_pages = Object.keys(nts.boot.page_info);
		}
		localStorage["page_info"] = JSON.stringify(nts.boot.page_info);
	}
	set_as_guest() {
		nts.session.user = "Guest";
		nts.session.user_email = "";
		nts.session.user_fullname = "Guest";

		nts.user_defaults = {};
		nts.user_roles = ["Guest"];
		nts.sys_defaults = {};
	}
	make_page_container() {
		if ($("#body").length) {
			$(".splash").remove();
			nts.temp_container = $("<div id='temp-container' style='display: none;'>").appendTo(
				"body"
			);
			nts.container = new nts.views.Container();
		}
	}
	make_nav_bar() {
		// toolbar
		if (nts.boot && nts.boot.home_page !== "setup-wizard") {
			nts.nts_toolbar = new nts.ui.toolbar.Toolbar();
		}
	}
	logout() {
		var me = this;
		me.logged_out = true;
		return nts.call({
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
		nts.app.redirect_to_login();
	}
	redirect_to_login() {
		window.location.href = `/login?redirect-to=${encodeURIComponent(
			window.location.pathname + window.location.search
		)}`;
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
			if (window.cur_dialog && cur_dialog.display && !cur_dialog.is_minimized) {
				// trigger primary
				cur_dialog.get_primary_btn().trigger("click");
			} else if (cur_frm && cur_frm.page.btn_primary.is(":visible")) {
				cur_frm.page.btn_primary.trigger("click");
			} else if (nts.container.page.save_action) {
				nts.container.page.save_action();
			}
		}, 100);
	}

	show_change_log() {
		var me = this;
		let change_log = nts.boot.change_log;

		// nts.boot.change_log = [{
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
			cint(nts.boot.sysdefaults.disable_change_log_notification)
		) {
			return;
		}

		// Iterate over changelog
		var change_log_dialog = nts.msgprint({
			message: nts.render_template("change_log", { change_log: change_log }),
			title: __("Updated To A New Version 🎉"),
			wide: true,
		});
		change_log_dialog.keep_open = true;
		change_log_dialog.custom_onhide = function () {
			nts.call({
				method: "nts.utils.change_log.update_last_known_versions",
			});
			me.show_notes();
		};
	}

	show_update_available() {
		if (!nts.boot.has_app_updates) return;
		nts.xcall("nts.utils.change_log.show_update_popup");
	}

	add_browser_class() {
		$("html").addClass(nts.utils.get_browser().name.toLowerCase());
	}

	set_fullwidth_if_enabled() {
		nts.ui.toolbar.set_fullwidth_if_enabled();
	}

	show_notes() {
		var me = this;
		if (nts.boot.notes.length) {
			nts.boot.notes.forEach(function (note) {
				if (!note.seen || note.notify_on_every_login) {
					var d = new nts.ui.Dialog({ content: note.content, title: note.title });
					d.keep_open = true;
					d.msg_area = $('<div class="msgprint">').appendTo(d.body);
					d.msg_area.append(note.content);
					d.onhide = function () {
						note.seen = true;
						// Mark note as read if the Notify On Every Login flag is not set
						if (!note.notify_on_every_login) {
							nts.call({
								method: "nts.desk.doctype.note.note.mark_as_seen",
								args: {
									note: note.name,
								},
							});
						} else {
							nts.call({
								method: "nts.desk.doctype.note.note.reset_notes",
							});
						}
					};
					d.show();
				}
			});
		}
	}

	setup_build_events() {
		if (nts.boot.developer_mode) {
			nts.require("build_events.bundle.js");
		}
	}

	setup_energy_point_listeners() {
		nts.realtime.on("energy_point_alert", (message) => {
			nts.show_alert(message);
		});
	}

	setup_copy_doc_listener() {
		$("body").on("paste", (e) => {
			try {
				let pasted_data = nts.utils.get_clipboard_data(e);
				let doc = JSON.parse(pasted_data);
				if (doc.doctype) {
					e.preventDefault();
					const sleep = nts.utils.sleep;

					nts.dom.freeze(__("Creating {0}", [doc.doctype]) + "...");
					// to avoid abrupt UX
					// wait for activity feedback
					sleep(500).then(() => {
						let res = nts.model.with_doctype(doc.doctype, () => {
							let newdoc = nts.model.copy_doc(doc);
							newdoc.__newname = doc.name;
							delete doc.name;
							newdoc.idx = null;
							newdoc.__run_link_triggers = false;
							nts.set_route("Form", newdoc.doctype, newdoc.name);
							nts.dom.unfreeze();
						});
						res && res.fail?.(nts.dom.unfreeze);
					});
				}
			} catch (e) {
				//
			}
		});
	}

	/// Setup event listeners for events across browser tabs / web workers.
	setup_broadcast_listeners() {
		// booted in another tab -> refresh csrf to avoid invalid requests.
		nts.broadcast.on("boot", ({ csrf_token, user }) => {
			if (user && user != nts.session.user) {
				nts.msgprint({
					message: __(
						"You've logged in as another user from another tab. Refresh this page to continue using system."
					),
					title: __("User Changed"),
					primary_action: {
						label: __("Refresh"),
						action: () => {
							window.location.reload();
						},
					},
				});
				return;
			}

			if (csrf_token) {
				// If user re-logged in then their other tabs won't be usable without this update.
				nts.csrf_token = csrf_token;
			}
		});
	}

	setup_moment() {
		moment.updateLocale("en", {
			week: {
				dow: nts.datetime.get_first_day_of_the_week_index(),
			},
		});
		moment.locale("en");
		moment.user_utc_offset = moment().utcOffset();
		if (nts.boot.timezone_info) {
			moment.tz.add(nts.boot.timezone_info);
		}
	}
};

nts.get_module = function (m, default_module) {
	var module = nts.modules[m] || default_module;
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
