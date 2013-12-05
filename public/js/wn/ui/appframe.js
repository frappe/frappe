// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// wn._("Form")

wn.ui.AppFrame = Class.extend({
	init: function(parent, title, module) {
		this.set_document_title = true;
		this.buttons = {};
		this.fields_dict = {};
		this.parent = parent;

		this.$title_area = $('<div class="title-area">\
			<h4>\
				<span class="title-icon text-muted" style="display: none"></span>\
				<span class="title-text"></span>\
			</h4></div>').appendTo(parent.find(".titlebar-item.text-center"));

		this.setup_iconbar();
		
		if(title) 
			this.set_title(title);
			
	},
	
	setup_iconbar: function() {
		var me = this;
		this.iconbar = new wn.ui.IconBar(this.parent.find(".appframe-iconbar .container"), 3);
		this.iconbar.$wrapper.find(".iconbar-3").addClass("pull-right");
		
		this.iconbar.$wrapper.on("shown", function() {
			me.parent.find(".appframe-iconbar").removeClass("hide")
		})
		this.iconbar.$wrapper.on("hidden", function() {
			me.parent.find(".appframe-iconbar").addClass("hide")
		})
	},
	
	// appframe::title
	get_title_area: function() {
		return this.$title_area;
	},

	set_title: function(txt, full_text, user) {
		// strip icon
		this.title = txt;
		document.title = txt.replace(/<[^>]*>/g, "");
		this.$title_area.find(".title-text").html(txt);
		
	},
	
	set_title_left: function(txt, click) {
		return $("<a>")
			.html(txt)
			.on("click", function() { click.apply(this); })
			.appendTo(this.parent.find(".titlebar-item.text-left").empty());
	},
	
	set_title_right: function(txt, click, icon) {
		var $right = this.parent.find(".titlebar-item.text-right")
		if(txt) {
			this.title_right && this.title_right.remove();
			this.title_right = $("<a>")
				.html((icon ? '<i class="'+icon+'"></i> ' : "") + txt)
				.click(click)
				.appendTo($right);
			return this.title_right;
		} else {
			$right.empty();
			this.title_right = null;
			this.primary_dropdown = null;
			this.primary_action = null;
		}
	},
	
	add_primary_action: function(label, click, icon) {
		if(!this.primary_dropdown) {
			if(!this.primary_action) {
				var $right = this.parent.find(".titlebar-item.text-right");
				this.primary_action = $("<a>")
					.html(wn._("Actions") + " <i class='icon-caret-down'></i>")
					.css({"margin-right":"15px", "display":"inline-block"})
					.prependTo($right);
			}
			
			var id = "dropdown-" + wn.dom.set_unique_id();
			this.primary_action
				.attr("id", id)
				.attr("data-toggle", "dropdown")
				.addClass("dropdown-toggle")
				.parent()
					.addClass("dropdown")
			this.primary_dropdown = $('<ul class="dropdown-menu pull-right" role="menu" \
				aria-labelledby="'+ id +'"></ul>')
				.appendTo(this.primary_action.parent()).dropdown();
		}
		
		var $li = $('<li role="presentation"><a role="menuitem" class="text-left">'
			+ (icon ? '<i class="'+icon+' icon-fixed-width"></i> ' : "") + label+'</a></li>')
			.appendTo(this.primary_dropdown)
			.on("click", function() { click && click.apply(this); });
			
		return $li;
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
		$.each(views, function(i, e) {
			var btn = me.add_icon_btn("3", e.icon, wn._(toTitle(e.type)), function() {
				window.location.hash = "#" + $(this).attr("data-route");
			}).attr("data-route", e.route);
				
			if(e.type===active_view) {
				btn.find("i").css({"color": "#428bca"});
			}
		});
	},

	add_module_icon: function(module, doctype, onclick, sub_title) {
		var module_info = wn.modules[module];
		if(!module_info) {
			module_info = {
				icon: "icon-question-sign",
				color: "#ddd"
			}
		}
		var icon = wn.boot.doctype_icons[doctype] || module_info.icon;
		
		this.$title_area.find(".title-icon").html('<i class="'+icon+'"></i> ')
			.toggle(true)
			.attr("doctype-name", doctype)
			.attr("module-link", module_info.link)
			.click(onclick || function() {
				var route = wn.get_route();
				var doctype = $(this).attr("doctype-name");
				if(doctype && route[0]!=="List" && !locals["DocType"][doctype].issingle) {
					wn.set_route("List", doctype)
				} else if($(this).attr("module-link")!==route[0]){
					wn.set_route($(this).attr("module-link"));
				} else {
					wn.set_route("");
				}
				return false;
			});
				
		if(sub_title) {
			this.set_title_left('<i class="icon-angle-left"></i> ' + module, 
				function() { wn.set_route($(this).attr("module-link")); }).attr("module-link", module_info.link)
		}
	},
		
	add_help_button: function(txt) {
		this.add_icon_btn("2", "icon-question-sign", wn._("Help"), 
			function() { msgprint($(this).data('help-text'), 'Help'); })
			.data("help-text", txt);
	},

	add_icon_btn: function(group, icon, label, click) {
		return this.iconbar.add_btn(group, icon, label, click);
	},

	add_button: function(label, click, icon, is_title) {
		return this.iconbar.add_btn("1", icon, wn._(label), click);
	},
	
	// appframe::navbar links
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
	get_menu: function(label) {
		return $("#navbar-" + label.toLowerCase());
	},
	add_menu_divider: function(menu) {
		menu = typeof menu == "string" ?
			this.get_menu(menu) : menu;
			
		$('<li class="divider custom-menu"></li>').prependTo(menu);
	},
	
	// appframe::form
	add_label: function(label) {
		this.show_form();
		return $("<label class='col-md-1'>"+label+" </label>")
			.appendTo(this.parent.find(".appframe-form .container"));
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
		return $("<div class='checkbox' style='margin-right: 10px; margin-top: 7px; float: left;'><label><input type='checkbox'>" + label + "</label></div>")
			.appendTo(this.parent.find(".appframe-form .container"))
			.find("input");
	},
	add_field: function(df) {
		this.show_form();
		var f = wn.ui.form.make_control({
			df: df,
			parent: this.parent.find(".appframe-form .container"),
			only_input: true,
		})
		f.refresh();
		$(f.wrapper)
			.addClass('col-md-2')
			.css({
				"padding-left": "0px", 
				"padding-right": "0px",
				"margin-right": "5px",
			})
			.attr("title", wn._(df.label)).tooltip();
		f.$input.attr("placeholder", wn._(df.label));
		if(df["default"])
			f.set_input(df["default"])
		this.fields_dict[df.fieldname || df.label] = f;
		return f;
	},
	show_form: function() {
		this.parent.find(".appframe-form").removeClass("hide");
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
	$wrapper = $(opts.parent)
	$('<div class="appframe-titlebar">\
			<div class="container">\
				<div class="row">\
					<div class="titlebar-item text-left col-xs-3"></div>\
					<div class="titlebar-item titlebar-center-item text-center col-xs-6"></div>\
					<div class="titlebar-item text-right col-xs-3"></div>\
				</div>\
			</div>\
		</div>\
		<div class="appframe-iconbar hide">\
			<div class="container">\
			</div>\
		</div>\
		<div class="appframe-form hide">\
			<div class="container">\
			</div>\
		</div>\
		<div class="appframe container">\
			<div class="appframe-timestamp hide"></div>\
			<div class="workflow-button-area btn-group pull-right hide"></div>\
		</div>\
		<div class="appframe-footer hide"></div>').appendTo($wrapper);

	if(opts.single_column) {
		$('<div class="layout-main"></div>').appendTo($wrapper.find(".appframe"));
	} else {
		$('<div class="row">\
			<div class="layout-main-section col-sm-9"></div>\
			<div class="layout-side-section col-sm-3"></div>\
			</div>').appendTo($wrapper.find(".appframe"));
	}
	opts.parent.appframe = new wn.ui.AppFrame($wrapper);
	if(opts.set_document_title!==undefined)
		opts.parent.appframe.set_document_title = opts.set_document_title;
	if(opts.title) opts.parent.appframe.set_title(opts.title);
	if(opts.icon) opts.parent.appframe.add_module_icon(null, opts.icon);
}