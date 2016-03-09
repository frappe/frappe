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

		var all_icons = frappe.get_desktop_icons();
		var explore_icon = {
			module_name: 'Explore',
			label: 'Explore',
			_label: __('Explore'),
			_id: 'Explore',
			icon: 'octicon octicon-telescope',
			color: '#7578f6',
			link: 'modules'
		};
		explore_icon.app_icon = frappe.ui.app_icon.get_html(explore_icon);

		all_icons.push(explore_icon);

		frappe.desktop.wrapper.html(frappe.render_template(template, {
			// all visible icons
			desktop_items: all_icons,
		}));

		frappe.desktop.setup_module_click();

		// notifications
		frappe.desktop.show_pending_notifications();
		$(document).on("notification-update", function() {
			me.show_pending_notifications();
		});

		$(document).trigger("desktop-render");
	},

	setup_module_click: function() {
		if(frappe.list_desktop) {
			frappe.desktop.wrapper.on("click", ".desktop-list-item", function() {
				frappe.desktop.open_module($(this));
			});
		} else {
			frappe.desktop.wrapper.on("click", ".app-icon", function() {
				frappe.desktop.open_module($(this).parent());
			});
		}
	},

	open_module: function(parent) {
		var link = parent.attr("data-link");
		if(link) {
			if(link.indexOf('javascript:')===0) {
				eval(link.substr(11));
			} else if(link.substr(0, 1)==="/" || link.substr(0, 4)==="http") {
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

				frappe.call({
					method: 'frappe.desk.doctype.desktop_icon.desktop_icon.set_order',
					args: {
						'new_order': new_order
					},
					quiet: true
				});
			}
		});
	},

	set_background: function() {
		frappe.ui.set_user_background(frappe.boot.user.background_image, null,
			frappe.boot.user.background_style);
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
					var text = sum || '';
					if(text > 99) {
						text = '99+';
					}

					if(circle.length) {
						circle.html(text);
					} else {
						notifier.html(text);
					}
				}
			}
		}
	}
});
