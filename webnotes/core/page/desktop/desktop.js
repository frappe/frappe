wn.provide('wn.core.pages.desktop');

wn.core.pages.desktop.refresh = function() {
	wn.core.pages.desktop.render();

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

wn.core.pages.desktop.render = function() {
	document.title = "Desktop";
	var add_icon = function(m) {
		var module = wn.modules[m];
		if(!module)
			return;
		if(!module.label) 
			module.label = m;
		module.name = m;
		module.label = wn._(module.label);
		//module.gradient_css = wn.get_gradient_css(module.color, 45);
		module._link = module.link.toLowerCase().replace("/", "-");
		
		$module_icon = $(repl('<div id="module-icon-%(_link)s" class="case-wrapper" \
				data-name="%(name)s" data-link="%(link)s">\
				<div id="module-count-%(_link)s" class="circle" style="display: None">\
					<span class="circle-text"></span>\
				 </div>\
				<div class="case-border" style="background-color: %(color)s">\
					<i class="%(icon)s"></i>\
				</div>\
				<div class="case-label">%(label)s</div>\
			</div>', module)).click(function() {
				var link = $(this).attr("data-link");
				if(link.substr(0, 1)==="/") {
					window.open(link.substr(1))
				}
				wn.set_route(link);
			}).css({
				cursor:"pointer"
			}).appendTo("#icon-grid");
	}
	
	// modules
	var modules_list = wn.user.get_desktop_items();
	$.each(modules_list, function(i, m) {
		if(m!="Setup")
			add_icon(m);
	})

	// setup
	if(user_roles.indexOf('System Manager')!=-1)
		add_icon('Setup')

	// notifications
	wn.core.pages.desktop.show_pending_notifications();
	
	$(document).on("notification-update", function() {
		wn.core.pages.desktop.show_pending_notifications();
	})

}

wn.core.pages.desktop.show_pending_notifications = function() {

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

pscript.onload_desktop = function(wrapper) {
	// load desktop
	wn.core.pages.desktop.refresh();
}

