wn.provide('wn.desktop');

wn.pages['desktop'].onload = function(wrapper) {
	// setup dialog
	
	// load desktop
	wn.desktop.refresh();
}

wn.pages['desktop'].refresh = function(wrapper) {
	wn.ui.toolbar.add_dropdown_button("File", wn._("All Applications"), function() { 
		wn.desktop.show_all_modules();
	}, 'icon-th');
	
}

wn.desktop.refresh = function() {
	wn.desktop.render();

	$("#icon-grid").sortable({
		update: function() {
			new_order = [];
			$("#icon-grid .case-wrapper").each(function(i, e) {
				new_order.push($(this).attr("data-name"));
			});
			wn.defaults.set_default("_desktop_items", new_order);
		}
	});
}

wn.desktop.render = function() {
	$("#icon-grid").empty();
	
	document.title = "Desktop";
	var add_icon = function(m) {
		var module = wn.modules[m];
		
		if(!module || (!module.link && !module.onclick) || module.is_app)
			return;
		if(module.link)
			module._link = module.link.toLowerCase().replace("/", "-");

		module.app_icon = wn.ui.app_icon.get_html(m);
		
		$module_icon = $(repl('<div id="module-icon-%(_link)s" class="case-wrapper" \
			data-name="%(name)s" data-link="%(link)s">\
			<div id="module-count-%(_link)s" class="circle" style="display: None">\
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
					wn.set_route(link);
				}
			} : module.onclick).css({
				cursor:"pointer"
			}).appendTo("#icon-grid");
	}
	
	// modules
	var modules_list = wn.user.get_desktop_items();
	var user_list = wn.user.get_user_desktop_items();
	$.each(modules_list, function(i, m) {
		var module = wn.modules[m];
		if(module) {
			if(!module.label) {
				module.label = m;
			}
			module.name = m;
			module._label = wn._(module.label);
		
			if(m!="Setup" && user_list.indexOf(m)!==-1)
				add_icon(m);
		}
	})

	// setup
	if(user_roles.indexOf('System Manager')!=-1)
		add_icon('Setup')

	// all applications
	wn.modules["All Applications"] = {
		icon: "icon-th",
		label: "All Applications",
		_label: wn._("All Applications"),
		color: "#4aa3df",
		link: "",
		onclick: function() {
			wn.desktop.show_all_modules();
		}
	}
	add_icon("All Applications")

	// notifications
	wn.desktop.show_pending_notifications();
	
	$(document).on("notification-update", function() {
		wn.desktop.show_pending_notifications();
	})

}

wn.desktop.show_all_modules = function() {
	if(!wn.desktop.all_modules_dialog) {
		var d = new wn.ui.Dialog({
			title: '<i class="icon-th text-muted"></i> All Applications'
		});
		
		var desktop_items = wn.user.get_desktop_items();
		var user_desktop_items = wn.user.get_user_desktop_items();
		
		$('<input class="form-control desktop-app-search" \
			type="text" placeholder="Search Filter">')
			.appendTo(d.body)
			.on("keyup", function() {
				var val = $(this).val();
				$(d.body).find(".list-group-item").each(function() {
					$(this).toggle($(this).attr("data-label").toLowerCase().indexOf(val)!==-1);
				})
			});
		$('<hr><p class="text-right text-muted text-small">'+wn._("Checked items shown on desktop")+'</p>')
			.appendTo(d.body);
		$wrapper = $('<div class="list-group">').appendTo(d.body);
		
		// list of applications (wn.user.get_desktop_items())
		$.each(keys(wn.modules).sort(), function(i, m) {
			var module = wn.modules[m];
			if(module.link && desktop_items.indexOf(m)!==-1) {
				module.app_icon = wn.ui.app_icon.get_html(m, true);
				$(repl('<div class="list-group-item" data-label="%(label)s">\
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
				// update user_desktop_items (when checked or un-checked)
				var user_desktop_items = wn.user.get_user_desktop_items();
				var module = $(this).attr("data-name");
				if($(this).prop("checked")) {
					user_desktop_items.push(module);
				} else {
					if(user_desktop_items.indexOf(module)!==-1) {
						user_desktop_items.splice(user_desktop_items.indexOf(module), 1);
					}
				}
				wn.defaults.set_default("_user_desktop_items", user_desktop_items);
				wn.desktop.refresh();
			})
			.prop("checked", false);
		$.each(user_desktop_items, function(i, m) {
			$wrapper.find('[data-label="'+m+'"] [type="checkbox"]').prop("checked", true);
		})
		wn.desktop.all_modules_dialog = d;
	}
	$(wn.desktop.all_modules_dialog.body).find(".desktop-app-search").val("").trigger("keyup");
	wn.desktop.all_modules_dialog.show();
}

wn.desktop.show_pending_notifications = function() {

	if (!wn.boot.notification_info.module_doctypes) {
		return;
	}

	var modules_list = wn.user.get_desktop_items();
	$.each(modules_list, function(i, module) {
		var module_doctypes = wn.boot.notification_info.module_doctypes[module];

		var sum = 0;
		if(module_doctypes) {
			if(wn.boot.notification_info.open_count_doctype) {
				$.each(module_doctypes, function(j, doctype) {
					sum += (wn.boot.notification_info.open_count_doctype[doctype] || 0);
				});
			}
		} else if(wn.boot.notification_info.open_count_module 
			&& wn.boot.notification_info.open_count_module[module]!=null) {
			sum = wn.boot.notification_info.open_count_module[module];
		}
		if (wn.modules[module]) {
			var notifier = $("#module-count-" + wn.modules[module]._link);
			if(notifier.length) {
				notifier.toggle(sum ? true : false);
				notifier.find(".circle-text").html(sum || "");
			}
		}
	});
}
