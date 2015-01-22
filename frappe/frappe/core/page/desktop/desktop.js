frappe.provide('frappe.desktop');

frappe.pages['desktop'].onload = function(wrapper) {
	// setup dialog

	// load desktop
	frappe.desktop.refresh();
}

frappe.pages['desktop'].refresh = function(wrapper) {
	frappe.ui.toolbar.add_dropdown_button("File", __("All Applications"), function() {
		frappe.desktop.show_all_modules();
	}, 'icon-th');
};

frappe.desktop.refresh = function() {
	frappe.desktop.render();

	$("#icon-grid").sortable({
		update: function() {
			new_order = [];
			$("#icon-grid .case-wrapper").each(function(i, e) {
				new_order.push($(this).attr("data-name"));
			});
			frappe.defaults.set_default("_desktop_items", new_order);
		}
	});
}

frappe.desktop.render = function() {
	$("#icon-grid").empty();

	document.title = "Desktop";
	var add_icon = function(m) {
		var module = frappe.get_module(m);

		if(!module || (module.type!=="module" && !module.link && !module.onclick) || module.is_app) {
			return;
		}

		if(module._id && $("#module-icon-" + module._id).length) {
			// icon already exists!
			return;
		}

		module.app_icon = frappe.ui.app_icon.get_html(m);

		$module_icon = $(repl('<div id="module-icon-%(_id)s" class="case-wrapper" \
			data-name="%(name)s" data-link="%(link)s">\
			<div id="module-count-%(_id)s" class="circle" style="display: None">\
				<span class="circle-text"></span>\
			</div>\
			%(app_icon)s\
			<div class="case-label">%(_label)s</div>\
		</div>', module)).click(module.link ? function() {
				var link = $(this).attr("data-link");
				if(link) {
					if(link.substr(0, 1)==="/") {
						window.open(link.substr(1))
					}
					frappe.set_route(link);
				}
			} : module.onclick).css({
				cursor:"pointer"
			}).appendTo("#icon-grid");
	}

	// modules
	var modules_list = frappe.user.get_desktop_items();
	var user_list = frappe.user.get_user_desktop_items();

	$.each(modules_list, function(i, m) {
		var module = frappe.modules[m];
		if(module) {
			if(!in_list(["Setup", "Core"], m) && user_list.indexOf(m)!==-1)
				add_icon(m);
		}
	})

	// setup
	if(user_roles.indexOf('System Manager')!=-1)
		add_icon('Setup')

	if(user_roles.indexOf('Administrator')!=-1)
		add_icon('Core')

	// all applications
	frappe.modules["All Applications"] = {
		icon: "icon-th",
		label: "All Applications",
		_label: __("All Applications"),
		_id: "all_applications",
		color: "#4aa3df",
		link: "",
		onclick: function() {
			frappe.desktop.show_all_modules();
		}
	}
	add_icon("All Applications");

	// notifications
	frappe.desktop.show_pending_notifications();

	$(document).on("notification-update", function() {
		frappe.desktop.show_pending_notifications();
	});

	$(document).trigger("desktop-render");
}

frappe.desktop.show_all_modules = function() {
	if(!frappe.desktop.all_modules_dialog) {
		var d = new frappe.ui.Dialog({
			title: '<i class="icon-th text-muted"></i> '+ __("All Applications")
		});

		var desktop_items = frappe.user.get_desktop_items(true);
		var user_desktop_items = frappe.user.get_user_desktop_items();

		$('<input class="form-control desktop-app-search" \
			type="text" placeholder="' + __("Search Filter") +'>')
			.appendTo(d.body)
			.on("keyup", function() {
				var val = $(this).val();
				$(d.body).find(".list-group-item").each(function() {
					$(this).toggle($(this).attr("data-label").toLowerCase().indexOf(val)!==-1);
				})
			});
		$('<hr><p class="text-right text-muted text-small">'+__("Checked items shown on desktop")+'</p>')
			.appendTo(d.body);
		$wrapper = $('<div class="list-group">').appendTo(d.body);

		// list of applications (frappe.user.get_desktop_items())
		var items = keys(frappe.modules).sort();
		$.each(items, function(i, m) {
			var module = frappe.get_module(m);
			if(module.link && desktop_items.indexOf(m)!==-1) {
				module.app_icon = frappe.ui.app_icon.get_html(m, true);
				module.label = __(module.label);
				$(repl('<div class="list-group-item" data-label="%(name)s">\
				<div class="row">\
					<div class="col-xs-2"><a href="#%(link)s">%(app_icon)s</a></div>\
					<div class="col-xs-10" style="padding-top: 14px;">\
						<a href="#%(link)s">%(label)s</a>\
						<input class="pull-right" type="checkbox" data-name="%(name)s" />\
					</div>\
				</div>\
				</div>', module)).appendTo($wrapper);
			}
		});

		// check shown items
		$wrapper.find('[type="checkbox"]')
			.on("click", function() {
				var user_desktop_items = [];
				$wrapper.find('[type="checkbox"]:checked').each(function(i,ele) {
					user_desktop_items.push($(ele).attr("data-name"));
				})
				frappe.defaults.set_default("_user_desktop_items", user_desktop_items);
				frappe.desktop.refresh();
			})
			.prop("checked", false);
		$.each(user_desktop_items, function(i, m) {
			$wrapper.find('[data-label="'+m+'"] [type="checkbox"]').prop("checked", true);
		})
		frappe.desktop.all_modules_dialog = d;
	}
	$(frappe.desktop.all_modules_dialog.body).find(".desktop-app-search").val("").trigger("keyup");
	frappe.desktop.all_modules_dialog.show();
}

frappe.desktop.show_pending_notifications = function() {

	if (!frappe.boot.notification_info.module_doctypes) {
		return;
	}

	var modules_list = frappe.user.get_desktop_items();
	$.each(modules_list, function(i, module) {
		var module_doctypes = frappe.boot.notification_info.module_doctypes[module];

		var sum = 0;
		if(module_doctypes) {
			if(frappe.boot.notification_info.open_count_doctype) {
				$.each(module_doctypes, function(j, doctype) {
					sum += (frappe.boot.notification_info.open_count_doctype[doctype] || 0);
				});
			}
		} else if(frappe.boot.notification_info.open_count_module
			&& frappe.boot.notification_info.open_count_module[module]!=null) {
			sum = frappe.boot.notification_info.open_count_module[module];
		}
		if (frappe.modules[module]) {
			var notifier = $("#module-count-" + frappe.get_module(module)._id);
			if(notifier.length) {
				notifier.toggle(sum ? true : false);
				notifier.find(".circle-text").html(sum || "");
			}
		}
	});
}
