// Copyright 2013 Web Notes Technologies Pvt Ltd
// License: MIT. See license.txt

// wn._("Form")

wn.ui.AppFrame = Class.extend({
	init: function(parent, title, module) {
		this.set_document_title = true;
		this.buttons = {};
		this.$w = $('<div class="col-span-12">\
			<div class="row appframe-header">\
				<div class="col-span-12"></div>\
			</div>\
			</div>')
			.prependTo(parent)
			.find(".appframe-header div");

		$('<!-- div>\
			<ul class="breadcrumb" style="height: 32px;">\
				<span class="appframe-right pull-right">\
					<span class="btn-group"></span>\
				</span>\
			</ul>\
		</div>\
		<div class="toolbar-area"></div -->\
		<img class="title-status-img hidden-phone"\
			style="position: absolute; top: 10px; left: 40%; width: 160px; display:none" />\
		<div class="title-button-area btn-group pull-right" style="margin-top: 10px;"></div>\
		<div class="title-area"><h2 style="display: inline-block">\
			<span class="title-icon"></span><span class="title-text"></span></h2></div>\
		<div class="sub-title-area text-muted small" \
			style="margin-top: -10px;"></div>\
		<div class="btn-group appframe-toolbar" \
			style="display: none; margin-top: 15px;"></div>\
		').appendTo(this.$w);
		
		this.$w.find('.close').click(function() {
			window.history.back();
		})
		
		this.toolbar = this.$w.find(".appframe-toolbar");
		
		if(title) 
			this.set_title(title);
			
	},
	get_title_area: function() {
		return this.$w.find(".title-area");
	},
	set_title: function(txt, full_text) {
		this.title = txt;
		this.$w.find(".breadcrumb .appframe-title").html(txt);
		this.$w.find(".title-text").html(txt);
	},
	set_sub_title: function(txt) {
		this.$w.find(".sub-title-area").html(txt);
	},
	clear_breadcrumbs: function() {
		this.$w.find(".breadcrumb").empty();
	},
	add_breadcrumb: function(icon, link, title) {
		if(link) {
			$(repl('<li style="margin-top: 5px;"><a href="#%(link)s" title="%(title)s"><i class="%(icon)s"></i></a>\
			  	<span class="divider">/</span></li>', {
				icon: icon,
				link: link,
				title: wn._(title)
			})).appendTo(this.$w.find(".breadcrumb"));
		} else {
			$(repl("<li style='margin-top: 5px;' class='active'><i class='%(icon)s'></i> \
				<span class='appframe-title'></span>\
				<span class='appframe-subject'></span></li>", {
				icon: icon,
			})).appendTo(this.$w.find(".breadcrumb"));
			if(this.title) this.set_title(this.title);
		}
	},
	add_home_breadcrumb: function() {
		this.add_breadcrumb("icon-home", wn.home_page, "Home");
	},
	add_list_breadcrumb: function(doctype) {
		this.add_breadcrumb("icon-list", "List/" + encodeURIComponent(doctype), doctype + " List");
	},
	add_module_icon: function(module) {
		var module_info = wn.modules[module];
		if(module_info) {
			this.$w.find(".title-icon").html('<i class="'
				+module_info.icon+'"></i> ')
				.css({"cursor":"pointer"})
				.attr("module-name", module)
				.click(function() {
					wn.set_route(wn.modules[$(this).attr("module-name")].link);
				});
			this.$w.prepend("<div>").css({
				"border-top": "7px solid " + module_info.color
			});
			// this.$w.find(".title-area").css({
			// 	"border-left": "5px solid " + module_info.color
			// })
		}
	},
	
	set_views_for: function(doctype, active_view) {
		this.doctype = doctype;
		var me = this;
		var views = [{
				icon: "icon-file-alt",
				route: "",
				type: "form",
				set_route: function() {
					if(wn.views.formview[me.doctype]) {
						wn.set_route("Form", me.doctype, wn.views.formview[me.doctype].frm.docname);
					} else {
						new_doc(doctype);
					}
				}
			}];
		
		if(!locals.DocType[doctype].issingle) {
			views.push({
				icon: "icon-list",
				route: "List/" + doctype,
				type: "list"
			});
		}
		
		if(locals.DocType[doctype].__calendar_js) {
			views.push({
				icon: "icon-calendar",
				route: "Calendar/" + doctype,
				type: "calendar"
			});
		}
		
		if(wn.model.can_get_report(doctype)) {
			views.push({
				icon: "icon-table",
				route: "Report2/" + doctype,
				type: "report"
			});
		}
		
		this.set_views(views, active_view);
	},
	
	set_views: function(views, active_view) {
		var me = this;
		$right = this.$w.find(".appframe-right .btn-group");
		$.each(views, function(i, e) {
			var btn = $(repl('<button class="btn" data-route="%(route)s">\
				<i class="%(icon)s"></i></button>', e))
				.click(e.set_route || function() {
					window.location.hash = "#" + $(this).attr("data-route");
				})
				.css({
					width: "39px"
				})
				.attr("title", wn._(toTitle(e.type)))
				.appendTo($right);
				
			if(e.type==active_view) {
				btn.addClass("btn-inverse");
			}
		});
	},
	
	add_help_button: function(txt) {
		$('<button class="btn" button-type="help">\
			<b>?</b></button>')
			.data('help-text', txt)
			.click(function() { msgprint($(this).data('help-text'), 'Help'); })
			.appendTo(this.toolbar);			
	},

	clear_buttons: function() {
		this.toolbar && this.toolbar.empty().toggle(false);
		$(".custom-menu").remove();
	},

	add_button: function(label, click, icon, title_toolbar) {
		!title_toolbar && this.toolbar.toggle(true);
		
		args = { label: label, icon:'' };
		if(icon) {
			args.icon = '<i class="'+icon+'"></i>';
		}
		this.buttons[label] = $(repl('<button class="btn">\
			%(icon)s %(label)s</button>', args))
			.appendTo(title_toolbar ? this.$w.find(".title-button-area") : this.toolbar)
			.click(click);
		return this.buttons[label];
	},
	get_menu: function(label) {
		return $("#navbar-" + label.toLowerCase());
	},
	add_menu_divider: function(menu) {
		menu = typeof menu == "string" ?
			this.get_menu(menu) : menu;
			
		$('<li class="divider custom-menu"></li>').appendTo(menu);
	},
	add_dropdown_button: function(parent, label, click, icon) {
		var menu = this.get_menu(parent);
		if(menu.find("li:not(.custom-menu)").length && !menu.find(".divider").length) {
			this.add_menu_divider(menu);
		}

		return $('<li class="custom-menu"><a><i class="'
			+icon+'"></i> '+label+'</a></li>')
			.appendTo(menu)
			.find("a")
			.click(function() {
				click();
			});
	},
	add_label: function(label) {
		return $("<span class='label'>"+label+" </span>")
			.appendTo($("<li>").appendTo(this.toolbar));
	},
	add_select: function(label, options) {
		this.add_toolbar();
		return $("<select class='col-span-2' style='margin-top: 5px;'>")
			.add_options(options)
			.appendTo($("<li>").appendTo(this.toolbar));
	},
	add_data: function(label) {
		this.add_toolbar();
		return $("<input class='col-span-2' style='margin-top: 5px;' type='text' placeholder='"+ label +"'>")
			.appendTo($("<li>").appendTo(this.toolbar));
	}, 
	add_date: function(label, date) {
		this.add_toolbar();
		return $("<input class='col-span-2' style='margin-top: 5px;' type='text'>").datepicker({
			dateFormat: sys_defaults.date_format.replace("yyyy", "yy"),
			changeYear: true,
		}).val(dateutil.str_to_user(date) || "")
			.appendTo($("<li>").appendTo(this.toolbar));
	},
	add_check: function(label) {
		this.add_toolbar();
		return $("<label style='display: inline;'><input type='checkbox' \
			style='margin-top: 5px;'/> " + label + "</label>")
			.appendTo($("<li>").appendTo(this.toolbar))
			.find("input");
	},
	add_ripped_paper_effect: function(wrapper) {
		if(!wrapper) var wrapper = wn.container.page;
		var layout_main = $(wrapper).find('.layout-main');
		if(!layout_main.length) {
			layout_main = $(wrapper).find('.layout-main-section');
		}
		layout_main.css({"padding-top":"25px"});
		$('<div class="ripped-paper-border"></div>')
			.prependTo(layout_main)
			.css({"width": $(layout_main).width()});
	}
});

// parent, title, single_column
// standard page with appframe

wn.ui.make_app_page = function(opts) {
	if(opts.single_column) {
		$('<div class="appframe col-span-12">\
			<div class="layout-appframe row"></div>\
			<div class="layout-main"></div>\
		</div>').appendTo(opts.parent);
	} else {
		$('<div class="appframe col-span-12">\
			<div class="layout-appframe row"></div>\
			<div class="row">\
				<div class="layout-main-section col-span-9"></div>\
				<div class="layout-side-section col-span-3"></div>\
			</div>\
		</div>').appendTo(opts.parent);
	}
	opts.parent.appframe = new wn.ui.AppFrame($(opts.parent).find('.layout-appframe'));
	if(opts.set_document_title!==undefined)
		opts.parent.appframe.set_document_title = opts.set_document_title;
	if(opts.title) opts.parent.appframe.set_title(opts.title);
}