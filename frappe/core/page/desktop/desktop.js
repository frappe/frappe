frappe.provide('frappe.desktop');

frappe.pages['desktop'].on_page_load = function(wrapper) {
	// load desktop
	if(!frappe.list_desktop) {
		frappe.desktop.set_background();
	}
	frappe.desktop.refresh(wrapper);
};

frappe.pages['desktop'].on_page_show = function(wrapper) {
	if(frappe.list_desktop) {
		$("body").attr("data-route", "list-desktop");
	}
};

$.extend(frappe.desktop, {
	refresh: function(wrapper) {
		if (wrapper) {
			this.wrapper = $(wrapper);
		}

		this.render();
		this.make_sortable();
	},

	render: function() {
		var me = this;
		frappe.utils.set_title("Desktop");

		var template = frappe.list_desktop ? "desktop_list_view" : "desktop_icon_grid";


		this.wrapper.html(frappe.render_template(template, {
			// all visible icons
			desktop_items: this.get_desktop_items(),

			// user visible icons
			user_desktop_items: this.get_user_desktop_items(),
		}));

		this.setup_module_click();

		// notifications
		this.show_pending_notifications();
		$(document).on("notification-update", function() {
			me.show_pending_notifications();
		});

		$(document).trigger("desktop-render");
	},

	get_desktop_items: function(global) {
		var me = this;

		frappe.modules["All Applications"] = {
			icon: "octicon octicon-three-bars",
			label: "All Applications",
			_label: __("All Applications"),
			_id: "all_applications",
			color: "#4aa3df",
			link: "",
			force_show: true,
			onclick: function() {
				me.all_applications.show();
			}
		}

		var desktop_items = [].concat(frappe.user.get_desktop_items(global));

		remove_from_list(desktop_items, "Setup");
		if(user_roles.indexOf('System Manager')!=-1) {
			desktop_items.push('Setup');
		}

		remove_from_list(desktop_items, "Core");
		if(user_roles.indexOf('Administrator')!=-1) {
			desktop_items.push('Core');
		}

		return desktop_items;
	},

	get_user_desktop_items: function() {
		var me = this;

		var user_desktop_items = [].concat(frappe.user.get_user_desktop_items());

		for (var m in frappe.modules) {
			var module = frappe.modules[m];
			if (module.force_show && user_desktop_items.indexOf(m)===-1) {
				user_desktop_items.push(m);
			}
		}

		// filter valid icons
		var out = [];
		for (var i=0, l=user_desktop_items.length; i < l; i++) {
			var m = user_desktop_items[i];
			var module = frappe.get_module(m);

			if (module) {
				module.app_icon = frappe.ui.app_icon.get_html(m);
				out.push(m);
			}
		}
		return out;
	},

	setup_module_click: function() {
		var me = this;

		if(frappe.list_desktop) {
			this.wrapper.on("click", ".desktop-list-item", function() {
				me.open_module($(this));
			});
		} else {
			this.wrapper.on("click", ".app-icon", function() {
				me.open_module($(this).parent());
			});
		}
	},

	open_module: function(parent) {
		var link = parent.attr("data-link");
		if(link) {
			if(link.substr(0, 1)==="/" || link.substr(0, 4)==="http") {
				window.open(link, "_blank");
			} else {
				frappe.set_route(link);
			}
			return false;
		} else {
			module = frappe.get_module(parent.attr("data-name"));
			if (module && module.onclick) {
				module.onclick();
				return false;
			}
		}
	},

	make_sortable: function() {
		if (frappe.dom.is_touchscreen() || frappe.list_desktop) {
			return;
		}

		new Sortable($("#icon-grid").get(0), {
			onUpdate: function(event) {
				new_order = [];
				$("#icon-grid .case-wrapper").each(function(i, e) {
					new_order.push($(this).attr("data-name"));
				});
				frappe.defaults.set_default("_desktop_items", new_order);
			}
		});
	},

	set_background: function() {
		frappe.ui.set_user_background(frappe.boot.user.background_image, null,
			frappe.boot.user.background_style);
	},

	all_applications: {
		show: function() {
			if(!this.dialog) {
				this.make_dialog();
			}
			$(this.dialog.body).find(".desktop-app-search").val("").trigger("keyup");
			this.dialog.show();
		},

		make_dialog: function() {
			this.dialog = new frappe.ui.Dialog({
				title: __("All Applications")
			});

			this.dialog.$wrapper.addClass("all-applications-dialog");
			this.dialog_body = $(this.dialog.body);

			$(frappe.render_template("all_applications_dialog", {
				all_modules: keys(frappe.modules).sort(),
				desktop_items: frappe.desktop.get_desktop_items(true),
				user_desktop_items: frappe.desktop.get_user_desktop_items()
			})).appendTo(this.dialog_body);

			this.bind_events();
		},

		bind_events: function() {
			var me = this;

			this.dialog_body.find(".desktop-app-search").on("keyup", function() {
				var val = ($(this).val() || "").toLowerCase();
				me.dialog_body.find(".list-group-item").each(function() {
					$(this).toggle($(this).attr("data-label").toLowerCase().indexOf(val)!==-1
						|| $(this).attr("data-name").toLowerCase().indexOf(val)!==-1);
				})
			});

			this.dialog_body.find('input[type="checkbox"]').on("click", function() {
				me.save_user_desktop_items();
			});
		},

		save_user_desktop_items: function() {
			var user_desktop_items = [];
			this.dialog_body.find('input[type="checkbox"]:checked').each(function(i, element) {
				user_desktop_items.push($(element).attr("data-name"));
			});
			frappe.defaults.set_default("_user_desktop_items", user_desktop_items);
			frappe.desktop.refresh();
		}
	},

	show_pending_notifications: function() {

		if (!frappe.boot.notification_info.module_doctypes) {
			return;
		}

		var modules_list = frappe.user.get_desktop_items();
		for (var i=0, l=modules_list.length; i < l; i++) {
			var module = modules_list[i];

			var module_doctypes = frappe.boot.notification_info.module_doctypes[module];

			var sum = 0;
			if(module_doctypes) {
				if(frappe.boot.notification_info.open_count_doctype) {
					for (var j=0, k=module_doctypes.length; j < k; j++) {
						var doctype = module_doctypes[j];
						sum += (frappe.boot.notification_info.open_count_doctype[doctype] || 0);
					}
				}
			} else if(frappe.boot.notification_info.open_count_module
				&& frappe.boot.notification_info.open_count_module[module]!=null) {
				sum = frappe.boot.notification_info.open_count_module[module];
			}
			if (frappe.modules[module]) {
				var notifier = $(".module-count-" + frappe.get_module(module)._id);
				if(notifier.length) {
					notifier.toggle(sum ? true : false);
					var circle = notifier.find(".circle-text");
					if(circle.length) {
						circle.html(sum || "");
					} else {
						notifier.html(sum);
					}
				}
			}
		}
	}
});
