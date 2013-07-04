// Copyright 2013 Web Notes Technologies Pvt Ltd
// License: MIT. See license.txt

// wn._("Form")

wn.ui.AppFrame = Class.extend({
	init: function(parent, title, module) {
		this.set_document_title = true;
		this.buttons = {};
		this.fields_dict = {};

		this.$w = $('<div class="appframe-header col col-lg-12">\
			<div class="row appframe-title">\
				<div class="col col-lg-12">\
					<div class="title-button-area btn-group pull-right" \
						style="margin-top: 10px;"></div>\
					<div class="title-button-area-1 btn-group pull-right" \
						style="margin-top: 10px;"></div>\
					<div class="title-area"><h2 style="display: inline-block">\
						<span class="title-icon" style="display: none"></span>\
						<span class="title-text"></span></h2></div>\
					<div class="sub-title-area text-muted small">&nbsp;</div>\
					<div class="status-bar"></div>\
				</div>\
			</div>\
			<div class="info-bar" style="display: none;"><ul class="hidden-sm-inline"></ul></div>\
			<div class="navbar" style="display: none;">\
				<div class="navbar-form pull-left">\
					<div class="btn-group"></div>\
				</div>\
			</div>\
		<div>').prependTo(parent);

		this.$w.find('.close').click(function() {
			window.history.back();
		})
		
		this.toolbar = this.$w.find(".navbar-form");
		if(title) 
			this.set_title(title);
			
	},
	get_title_area: function() {
		return this.$w.find(".title-area");
	},
	set_title: function(txt, full_text) {
		this.title = txt;
		document.title = txt;
		this.$w.find(".breadcrumb .appframe-title").html(txt);
		this.$w.find(".title-text").html(txt);
	},
	set_sub_title: function(txt) {
		this.$w.find(".sub-title-area").html(txt);
	},
	
	add_infobar: function(label, onclick) {
		var $ul = this.$w.find(".info-bar").toggle(true).find("ul"),
			$li = $('<li><a href="#">' + label + '</a></li>')
				.appendTo($ul)
				.click(function() {
					onclick();
					return false;
				})
		return $li;
	},
	
	clear_infobar: function() {
		this.$w.find(".info-bar").toggle(false).find("ul").empty();
	},
	
	add_module_icon: function(module) {
		var module_info = wn.modules[module];
		if(!module_info) {
			module_info = {
				icon: "icon-question-sign",
				color: "#eeeeee"
			}
		}
		
		if(module_info && module_info.icon) {
			this.$w.find(".title-icon").html('<i class="'
				+module_info.icon+'"></i> ')
				.toggle(true)
				.css({
					"background-color": module_info.color,
				})
				.attr("module-name", module)
				.click(function() {
					var module_info = wn.modules[$(this).attr("module-name")];
					wn.set_route(module_info ? module_info.link : "desktop");
				});
		}
	},
	
	set_views_for: function(doctype, active_view) {
		this.doctype = doctype;
		var me = this,
			meta = locals.DocType[doctype],
			views = [],
			module_info = wn.modules[meta.module];
			
		if(module_info) {
			views.push({
				icon: module_info.icon,
				route: module_info.link,
				type: "module"
			})
		}

		views.push({
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
		});

		
		if(!meta.issingle) {
			views.push({
				icon: "icon-list",
				route: "List/" + doctype,
				type: "list"
			});
		}
		
		if(wn.views.calendar[doctype]) {
			views.push({
				icon: "icon-calendar",
				route: "Calendar/" + doctype,
				type: "calendar"
			});
		}

		if(wn.views.calendar[doctype] && wn.views.calendar[doctype]) {
			views.push({
				icon: "icon-tasks",
				route: "Gantt/" + doctype,
				type: "gantt"
			});
		}

		if(wn.model.can_get_report(doctype)) {
			views.push({
				icon: "icon-table",
				route: "Report/" + doctype,
				type: "report"
			});
		}
		
		this.set_views(views, active_view);
	},
	
	set_views: function(views, active_view) {
		var me = this;
		$right = this.$w.find(".title-button-area");
		$.each(views, function(i, e) {
			var btn = $(repl('<button class="btn btn-default" data-route="%(route)s">\
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
				btn.removeClass("btn-default").addClass("btn-info");
			}
		});
	},
	
	add_help_button: function(txt) {
		$('<button class="btn btn-default" button-type="help">\
			<b>?</b></button>')
			.data('help-text', txt)
			.click(function() { msgprint($(this).data('help-text'), 'Help'); })
			.appendTo(this.toolbar);			
	},

	show_toolbar: function() {
		this.toolbar.parent().toggle(true);
	},

	clear_buttons: function() {
		this.toolbar && this.toolbar
			.html('<div class="btn-group"></div>')
			.parent()
			.toggle(false);
		$(".custom-menu").remove();
	},

	add_button: function(label, click, icon, is_title) {
		this.show_toolbar();
		
		args = { label: wn._(label), icon:'' };
		if(icon) {
			args.icon = '<i class="'+icon+'"></i>';
		}
		
		this.buttons[label] && this.buttons[label].remove();
		
		var append_or_prepend = is_title ? "prependTo" : "appendTo";
		
		this.buttons[label] = $(repl('<button class="btn btn-default">\
			%(icon)s <span class="hidden-sm-inline">%(label)s</span></button>', args))
			[append_or_prepend](this.toolbar.find(".btn-group").css({"margin-right": "5px"}))
			.attr("title", wn._(label))
			.click(click);
		if(is_title) {
			this.buttons[label].addClass("btn-title");
		}
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
		this.show_toolbar();
		return $("<label class='col-lg-1'>"+label+" </label>")
			.appendTo(this.toolbar);
	},
	add_select: function(label, options) {
		this.show_toolbar();
		return $("<select class='col-lg-2' style='margin-right: 5px;'>")
			.add_options(options)
			.appendTo(this.toolbar);
	},
	add_data: function(label) {
		this.show_toolbar();
		return $("<input class='col-lg-2' style='margin-right: 5px;' type='text' placeholder='"+ label +"'>")
			.appendTo(this.toolbar);
	}, 
	add_date: function(label, date) {
		this.show_toolbar();
		return $("<input class='col-lg-2' style='margin-right: 5px;' type='text'>").datepicker({
			dateFormat: sys_defaults.date_format.replace("yyyy", "yy"),
			changeYear: true,
		}).val(dateutil.str_to_user(date) || "")
			.appendTo(this.toolbar);
	},
	add_check: function(label) {
		this.show_toolbar();
		return $("<label style='display: inline;'><input type='checkbox' \
			style='margin-right: 5px;'/> " + label + "</label>")
			.appendTo(this.toolbar)
			.find("input");
	},
	add_field: function(df) {
		this.show_toolbar();
		var f = wn.ui.form.make_control({
			df: df,
			parent: this.toolbar,
			only_input: true,
		})
		f.refresh();
		$(f.wrapper)
			.addClass('col-lg-2')
			.css({
				"display": "inline-block",
				"margin-top": "0px",
				"margin-bottom": "-17px",
				"margin-left": "4px"
			})
			.attr("title", df.label).tooltip();
		if(df["default"])
			f.set_input(df["default"])
		this.fields_dict[df.fieldname || df.label] = f;
		return f;
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
	},
	/* deprecated */
	clear_breadcrumbs: function() {
		this.$w.find(".breadcrumb").empty();
	},
	add_breadcrumb: function(icon, link, title) {
		return; // bc
	},
	add_home_breadcrumb: function() {
		this.add_breadcrumb("icon-home", wn.home_page, "Home");
	},
	add_list_breadcrumb: function(doctype) {
		this.add_breadcrumb("icon-list", "List/" + encodeURIComponent(doctype), doctype + " List");
	},
});

// parent, title, single_column
// standard page with appframe

wn.ui.make_app_page = function(opts) {
	/* help: make a standard page layout with a toolbar and title */
	/* options: [
			"parent: [HTMLElement] parent element",
			"single_column: [Boolean] false/true",
			"title: [optional] set this title"
		] 
	*/
	if(opts.single_column) {
		$('<div class="appframe col col-lg-12">\
			<div class="layout-appframe row"></div>\
			<div class="layout-main"></div>\
		</div>').appendTo(opts.parent);
	} else {
		$('<div class="appframe col col-lg-12">\
			<div class="layout-appframe row"></div>\
			<div class="row">\
				<div class="layout-main-section col col-lg-9"></div>\
				<div class="layout-side-section col col-lg-3"></div>\
			</div>\
		</div>').appendTo(opts.parent);
	}
	opts.parent.appframe = new wn.ui.AppFrame($(opts.parent).find('.layout-appframe'));
	if(opts.set_document_title!==undefined)
		opts.parent.appframe.set_document_title = opts.set_document_title;
	if(opts.title) opts.parent.appframe.set_title(opts.title);
}