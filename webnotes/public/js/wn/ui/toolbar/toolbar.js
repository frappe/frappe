// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 


wn.ui.toolbar.Toolbar = Class.extend({
	init: function() {
		this.make();
		//this.make_modules();
		this.make_file();
		wn.ui.toolbar.recent = new wn.ui.toolbar.RecentDocs();
		wn.ui.toolbar.bookmarks = new wn.ui.toolbar.Bookmarks();
		this.make_tools();
		this.set_user_name();
		this.make_logout();
		this.make_notification();
		
		$('.dropdown-toggle').dropdown();
		
		$(document).trigger('toolbar_setup');
		
		// clear all custom menus on page change
		$(document).on("page-change", function() {
			$("header .navbar .custom-menu").remove();
		})
	},
	make: function() {
		$('header').append('<div class="navbar navbar-inverse navbar-fixed-top" role="navigation">\
			<div class="container">\
				<div class="navbar-header">\
					<button type="button" class="navbar-toggle" data-toggle="collapse" \
						data-target=".navbar-responsive-collapse">\
						<span class="icon-bar"></span>\
						<span class="icon-bar"></span>\
						<span class="icon-bar"></span>\
					</button>\
					<a class="navbar-brand" href="#"><i class="icon-home"></i></a>\
				</div>\
				<div class="collapse navbar-collapse navbar-responsive-collapse">\
					<ul class="nav navbar-nav navbar-left">\
					</ul>\
					<img src="assets/webnotes/images/ui/spinner.gif" id="spinner"/>\
					<ul class="nav navbar-nav navbar-right">\
						<li class="dropdown">\
							<a class="dropdown-toggle" data-toggle="dropdown" href="#" \
								onclick="return false;" id="toolbar-user-link"></a>\
							<ul class="dropdown-menu" id="toolbar-user">\
							</ul>\
						</li>\
					</ul>\
				</div>\
			</div>\
			</div>');		
	},
	make_home: function() {
		$('.navbar-brand').attr('href', "#");
	},
	
	make_notification: function() {
		$('.navbar .navbar-right').append('<li class="dropdown">\
			<a class="dropdown-toggl" href="#"  data-toggle="dropdown"\
				title="'+wn._("Unread Messages")+'"\
				onclick="return false;"><span class="navbar-new-comments">0</span></a>\
			<ul class="dropdown-menu" id="navbar-notification">\
			</ul>\
		</li>');

		$(document).on("notification-update", function() {
			wn.ui.toolbar.update_notifications();
		})
	},

	// make_modules: function() {
	// 	$('<li class="dropdown">\
	// 		<a class="dropdown-toggle" data-toggle="dropdown" href="#"\
	// 			title="'+wn._("Modules")+'"\
	// 			onclick="return false;">'+wn._("Modules")+'</a>\
	// 		<ul class="dropdown-menu modules">\
	// 		</ul>\
	// 		</li>').prependTo('.navbar .nav:first');
	// 
	// 	var modules_list = wn.user.get_desktop_items().sort();
	// 	var menu_list = $(".navbar .modules");
	// 
	// 	var _get_list_item = function(m) {
	// 		args = {
	// 			module: m,
	// 			module_page: wn.modules[m].link,
	// 			module_label: wn._(wn.modules[m].label || m),
	// 			icon: wn.modules[m].icon
	// 		}
	// 
	// 		return repl('<li><a href="#%(module_page)s" \
	// 			data-module="%(module)s"><i class="%(icon)s" style="display: inline-block; \
	// 				width: 21px; margin-top: -2px; margin-left: -7px;"></i>\
	// 			%(module_label)s</a></li>', args);
	// 	}
	// 
	// 	// desktop
	// 	$('<li><a href="#desktop"><i class="icon-th"></i> '
	// 		+ wn._("Desktop") + '</a></li>\
	// 		<li class="divider"></li>').appendTo(menu_list) 
	// 
	// 	// add to dropdown
	// 	$.each(modules_list,function(i, m) {
	// 		if(m!='Setup') {
	// 			menu_list.append(_get_list_item(m));			
	// 		}
	// 	})
	// 
	// 	// setup for system manager
	// 	if(user_roles.indexOf("System Manager")!=-1) {
	// 		menu_list.append('<li class="divider">' + _get_list_item("Setup"));
	// 	}
	// 
	// },
	
	make_file: function() {
		wn.ui.toolbar.new_dialog = new wn.ui.toolbar.NewDialog();
		wn.ui.toolbar.search = new wn.ui.toolbar.Search();
		wn.ui.toolbar.report = new wn.ui.toolbar.Report();
		$('.navbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" href="#"  data-toggle="dropdown"\
				title="'+wn._("File")+'"\
				onclick="return false;">'+wn._("File")+'</a>\
			<ul class="dropdown-menu" id="navbar-file">\
				<li><a href="#" onclick="return wn.ui.toolbar.new_dialog.show();">\
					<i class="icon-plus"></i> '+wn._('New')+'...</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.search.show();">\
					<i class="icon-search"></i> '+wn._('Search')+'...</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.report.show();">\
					<i class="icon-list"></i> '+wn._('Report')+'...</a></li>\
			</ul>\
		</li>');
	},

	make_tools: function() {
		$('.navbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" data-toggle="dropdown" href="#" \
				title="'+wn._("Tools")+'"\
				onclick="return false;">'+wn._("Tools")+'</a>\
			<ul class="dropdown-menu" id="toolbar-tools">\
				<li><a href="#" onclick="return wn.ui.toolbar.clear_cache();">\
					<i class="icon-fixed-width icon-refresh"></i> '
					+wn._('Clear Cache & Refresh')+'</a></li>\
				<li><a href="#" onclick="return wn.ui.toolbar.show_about();">\
					<i class="icon-fixed-width icon-info-sign"></i> '
					+wn._('About')+'</a></li>\
				<li><a href="http://erpnext.org/attributions.html" target="_blank"><i class="icon-fixed-width icon-heart"></i> '
					+wn._('Attributions')+'</a></li>\
			</ul>\
		</li>');
		
		if(has_common(user_roles,['Administrator','System Manager'])) {
			$('#toolbar-tools').append('<li><a href="#" \
				onclick="return wn.ui.toolbar.download_backup();"><i class="icon-fixed-width icon-download"></i> '
				+wn._('Download Backup')+'</a></li>');
		}
	},
	set_user_name: function() {
		var fn = user_fullname;
		if(fn.length > 15) fn = fn.substr(0,12) + '...';
		$('#toolbar-user-link').html(fn + '<b class="caret"></b>');
	},

	make_logout: function() {
		// logout
		$('#toolbar-user').append('<li><a href="#" onclick="return wn.app.logout();">\
			<i class="icon-fixed-width icon-signout"></i> '+wn._('Logout')+'</a></li>');
	}
});

wn.ui.toolbar.update_notifications = function() {
	var total = 0;
	var doctypes = keys(wn.boot.notification_info.open_count_doctype).sort();
	var modules = keys(wn.boot.notification_info.open_count_module).sort();
	
	$("#navbar-notification").empty();

	$.each(modules, function(i, module) {
		var count = wn.boot.notification_info.open_count_module[module];
		if(count) {
			$(repl('<li><a>\
				<span class="badge pull-right">\
					%(count)s</span> \
				<i class="icon-fixed-width %(icon)s"></i> %(module)s </a></li>', {
					module: module,
					count: count,
					icon: wn.modules[module].icon
				}))
				.appendTo("#navbar-notification")
					.find("a")
					.attr("data-module", module)
					.css({"min-width":"200px"})
					.on("click", function() {
						wn.set_route(wn.modules[$(this).attr("data-module")].link);
					});
			total += count;
		}
	});
	
	if(total) {
		$('<li class="divider"></li>').appendTo("#navbar-notification");
	}
	
	$.each(doctypes, function(i, doctype) {
		var count = wn.boot.notification_info.open_count_doctype[doctype];
		if(count) {
			$(repl('<li><a>\
				<span class="badge pull-right">\
					%(count)s</span> \
				<i class="icon-fixed-width %(icon)s"></i> %(doctype)s </a></li>', {
					doctype: doctype,
					icon: wn.boot.doctype_icons[doctype],
					count: count
				}))
				.appendTo("#navbar-notification")
					.find("a")
					.attr("data-doctype", doctype)
					.css({"min-width":"200px"})
					.on("click", function() {
						wn.views.show_open_count_list(this);
					});
			total += count;
		}
	});
	
	$(".navbar-new-comments")
		.html(total)
		.toggleClass("navbar-new-comments-true", total ? true : false);
	
}

wn.ui.toolbar.clear_cache = function() {
	localStorage && localStorage.clear();
	$c('webnotes.sessions.clear',{},function(r,rt){ 
		if(!r.exc) {
			show_alert(r.message);
			location.reload();
		}
	});
	return false;
}

wn.ui.toolbar.download_backup = function() {
	msgprint(wn._("Your download is being built, this may take a few moments..."));
	return $c('webnotes.utils.backups.get_backup',{},function(r,rt) {});
	return false;
}

wn.ui.toolbar.show_about = function() {
	try {
		wn.ui.misc.about();		
	} catch(e) {
		console.log(e);
	}
	return false;
}

wn.ui.toolbar.show_banner = function(msg) {
	return $('<div class="toolbar-banner"></div>').html(msg).appendTo($('header'));
}