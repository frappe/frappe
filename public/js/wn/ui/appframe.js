// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt

// wn._("Form")

wn.ui.AppFrame = Class.extend({
	init: function(parent, title, module) {
		this.set_document_title = true;
		this.buttons = {};
		this.fields_dict = {};

		this.$w = $('<div class="appframe-header col-md-12">\
			<div class="row appframe-title">\
				<div class="col-md-12">\
					<div class="title-button-area btn-group pull-right" \
						style="margin-top: 10px;"></div>\
					<div class="title-button-area-1 btn-group pull-right" \
						style="margin-top: 10px;"></div>\
					<div class="title-area"><h2 style="display: inline-block">\
						<span class="title-icon" style="display: none"></span>\
						<span class="title-text"></span></h2></div>\
					<div class="sub-title-area text-muted small">&nbsp;</div>\
					<div class="mini-bar"><ul></ul></div>\
				</div>\
			</div>\
			<div class="appframe-toolbar" style="display: none;"></div>\
		<div>').prependTo(parent);

		this.$w.find('.close').click(function() {
			window.history.back();
		})
		
		this.toolbar = this.$w.find(".appframe-toolbar");
		this.setup_toolbar();
		if(title) 
			this.set_title(title);
			
	},
	setup_toolbar: function() {
		$('<div class="btn-group form-group pull-left"></div>\
			<div class="appframe-form"></div>\
			<div class="clearfix"></div>').appendTo(this.toolbar.toggle(false));
	},
	get_title_area: function() {
		return this.$w.find(".title-area");
	},
	set_title: function(txt, full_text) {
		// strip icon
		this.title = txt;
		document.title = txt.replace(/<[^>]*>/g, "");
		this.$w.find(".breadcrumb .appframe-title").html(txt);
		this.$w.find(".title-text").html(txt);
	},
	set_sub_title: function(txt) {
		this.$w.find(".sub-title-area").html(txt);
	},
	
	add_to_mini_bar: function(icon, label, click) {
		var $ul = this.$w.find(".mini-bar ul"),
		$li = $('<li><i class="'+icon+'"></i></li>')
			.attr("title", label)
			.appendTo($ul)
			.click(function() {
				click();
				return false;
			})
		return $li;
	},
	
	hide_mini_bar: function() {
		this.$w.find(".mini-bar").toggle(false);
	},

	show_mini_bar: function() {
		this.$w.find(".mini-bar").toggle(true);
	},
		
	add_module_icon: function(module, doctype, onclick) {
		var module_info = wn.modules[module];
		if(!module_info) {
			module_info = {
				icon: "icon-question-sign",
				color: "#ddd"
			}
		}
		var icon = wn.boot.doctype_icons[doctype] || module_info.icon;
		
		this.$w.find(".title-icon").html('<i class="'+icon+'"></i> ')
			.toggle(true)
			.css({
				"background-color": module_info.color,
			})
			.attr("doctype-name", doctype)
			.attr("module-link", module_info.link)
			.click(onclick || function() {
				var route = wn.get_route();
				if($(this).attr("doctype-name") && route[0]!=="List") {
					wn.set_route("List", $(this).attr("doctype-name"))
				} else if($(this).attr("module-link")!==route[0]){
					wn.set_route($(this).attr("module-link"));
				} else {
					wn.set_route("");
				}
				return false;
			});
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
		$('<button class="btn btn-default pull-right" button-type="help">\
			<b>?</b></button>')
			.data('help-text', txt)
			.click(function() { msgprint($(this).data('help-text'), 'Help'); })
			.insertBefore(this.toolbar.find(".clearfix"));
	},

	show_toolbar: function() {
		this.toolbar.toggle(true);
	},

	clear_buttons: function() {
		this.toolbar.empty();
		this.setup_toolbar();
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
			%(icon)s <span class="hidden-xs-inline">%(label)s</span></button>', args))
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
			
		$('<li class="divider custom-menu"></li>').prependTo(menu);
	},
	add_dropdown_button: function(parent, label, click, icon) {
		var menu = this.get_menu(parent);
		if(menu.find("li:not(.custom-menu)").length && !menu.find(".divider").length) {
			this.add_menu_divider(menu);
		}

		return $('<li class="custom-menu"><a><i class="'
			+icon+'"></i> '+label+'</a></li>')
			.insertBefore(menu.find(".divider"))
			.find("a")
			.click(function() {
				click();
			});
	},
	add_label: function(label) {
		this.show_toolbar();
		return $("<label style='margin-top: 0.8%; margin-left: 5px; margin-right: 5px; float: left;'>"+label+" </label>")
			.appendTo(this.toolbar.find(".appframe-form"));
	},
	add_select: function(label, options) {
		var field = this.add_field({label:label, fieldtype:"Select"})
		return field.$wrapper.find("select").empty().add_options(options);
	},
	add_data: function(label) {
		var field = this.add_field({label: label, fieldtype: "Data"});
		return field.$wrapper.find("input").attr("placeholder", label);
	}, 
	add_date: function(label, date) {
		var field = this.add_field({label: label, fieldtype: "Date", "default": date});
		return field.$wrapper.find("input").attr("placeholder", label);		
	},
	add_check: function(label) {
		this.show_toolbar();
		return $("<div class='checkbox' style='margin-right: 10px; margin-top: 7px; float: left;'><label><input type='checkbox'>" + label + "</label></div>")
			.appendTo(this.toolbar.find(".appframe-form"))
			.find("input");
	},
	add_field: function(df) {
		this.show_toolbar();
		var f = wn.ui.form.make_control({
			df: df,
			parent: this.toolbar.find(".appframe-form"),
			only_input: true,
		})
		f.refresh();
		$(f.wrapper)
			.addClass('col-md-2 form-group')
			.css({
				"padding-left": "0px", 
				"padding-right": "0px",
				"margin-right": "5px"
			})
			.attr("title", wn._(df.label)).tooltip();
		f.$input.attr("placeholder", wn._(df.label));
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
		$('<div class="appframe col-md-12">\
			<div class="layout-appframe row"></div>\
			<div class="layout-main"></div>\
		</div>').appendTo(opts.parent);
	} else {
		$('<div class="appframe col-md-12">\
			<div class="layout-appframe row"></div>\
			<div class="row">\
				<div class="layout-main-section col-md-9"></div>\
				<div class="layout-side-section col-md-3"></div>\
			</div>\
		</div>').appendTo(opts.parent);
	}
	opts.parent.appframe = new wn.ui.AppFrame($(opts.parent).find('.layout-appframe'));
	if(opts.set_document_title!==undefined)
		opts.parent.appframe.set_document_title = opts.set_document_title;
	if(opts.title) opts.parent.appframe.set_title(opts.title);
	if(opts.icon) opts.parent.appframe.add_module_icon(null, opts.icon);
}