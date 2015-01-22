// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// __("Form")

frappe.ui.AppFrame = Class.extend({
	init: function(parent, title, module) {
		this.set_document_title = true;
		this.buttons = {};
		this.fields_dict = {};
		this.parent = parent;

		var $center = parent.find(".titlebar-center-item");
		this.$title_area = $('<span class="title-area">\
				<span class="title-icon text-muted" style="display: none"></span>\
				<span class="title-text"></span>\
			</span>').appendTo($center);

		this.$sub_title_area = $('<div class="title-sub hide"></div>')
			.appendTo($center);

		this.setup_iconbar();

		if(title)
			this.set_title(title);

	},

	setup_iconbar: function() {
		var me = this;
		this.iconbar = new frappe.ui.IconBar(this.parent.find(".appframe-iconbar .container"), 3);
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

	set_title: function(txt) {
		// strip icon
		this.title = txt;
		document.title = txt.replace(/<[^>]*>/g, "");
		this.$title_area.find(".title-text").html(txt);
	},

	set_title_sub: function(txt) {
		// strip icon
		this.$sub_title_area.html(txt).toggleClass("hide", !!!txt);
	},

	set_title_left: function(click) {
		return $("<a>")
			.html('<i class="icon-angle-left text-muted" style="margin-right: 10px; \
				font-weight: bold; text-decoration: none;"></i>')
			.on("click", function() { click.apply(this); })
			.appendTo(this.parent.find(".titlebar-left-item").empty());
	},

	set_title_right: function(txt, click, icon, btn_class) {
		if(!btn_class) btn_class="btn-primary"
		var $right = this.parent.find(".titlebar-item.text-right")
		if(txt) {
			this.title_right && this.title_right.remove();
			this.title_right = $("<a class='btn "+btn_class+"'>")
				.html((icon ? '<i class="'+icon+'"></i> ' : "") + txt)
				.click(click)
				.appendTo($right.attr("data-text", txt));
			return this.title_right;
		} else {
			$right.empty().attr("data-text", "");
			this.title_right = null;
			this.primary_dropdown = null;
			this.primary_action = null;
		}
	},

	get_title_right_text: function() {
		return this.parent.find(".titlebar-item.text-right").attr("data-text");
	},

	clear_primary_action: function() {
		this.parent.find(".appframe-primary-actions").addClass("hide");
		this.parent.find(".appframe-primary-actions .container").empty();
	},

	add_primary_action: function(label, click, icon, toolbar_or_class) {
		if(toolbar_or_class===true) {
			this.add_icon_btn("4", icon, label, click);
			return;
		}
		var wrapper = this.parent.find(".appframe-primary-actions .container");
		this.parent.find(".appframe-primary-actions").removeClass("hide");
		return $(repl('<button class="btn %(klass)s btn-sm">\
			<i class="%(icon)s"></i> %(label)s</button>', {label:label, icon:icon,
				klass: toolbar_or_class || "btn-primary"}))
			.on("click", click)
			.appendTo(wrapper);
	},

	set_views_for: function(doctype, active_view) {
		this.doctype = doctype;
		var me = this,
			meta = locals.DocType[doctype],
			views = [],
			module_info = frappe.modules[meta.module];

		if(module_info) {
			views.push({
				icon: module_info.icon,
				route: "Module/" + meta.module,
				type: "module",
				label: __("Module")
			})
		}

		views.push({
			icon: "icon-file-alt",
			route: "",
			type: "form",
			label: __("Form"),
			set_route: function() {
				console.log(me.doctype);
				if(frappe.views.formview[me.doctype]) {
					frappe.set_route("Form", me.doctype, frappe.views.formview[me.doctype].frm.docname);
				} else {
					new_doc(me.doctype);
				}
				return false;
			}
		});


		if(!meta.issingle) {
			views.push({
				icon: "icon-list",
				route: "List/" + doctype,
				type: "list",
				label: __("List")
			});
		}

		if(frappe.views.calendar[doctype]) {
			views.push({
				icon: "icon-calendar",
				route: "Calendar/" + doctype,
				type: "calendar",
				label: __("Calendar")
			});
		}

		if(frappe.views.calendar[doctype] && frappe.views.calendar[doctype]) {
			views.push({
				icon: "icon-tasks",
				route: "Gantt/" + doctype,
				type: "gantt",
				label: __("Gantt Chart")
			});
		}

		if(frappe.model.can_get_report(doctype)) {
			views.push({
				icon: "icon-table",
				route: "Report/" + doctype,
				type: "report",
				label: __("Report")
			});
		}

		this.set_views(views, active_view);
	},

	set_views: function(views, active_view) {
		var me = this;
		$.each(views, function(i, e) {
			var btn = me.add_icon_btn("3", e.icon, __(e.label) || __(toTitle(e.type)), e.set_route || function() {
				window.location.hash = "#" + $(this).attr("data-route");
			}).attr("data-route", e.route);

			if(e.type===active_view) {
				btn.find("i").css({"color": "#428bca"});
			}
		});
	},

	add_module_icon: function(module, doctype, onclick, sub_title) {
		var module_info = frappe.get_module(module);
		if(!module_info) {
			module_info = {
				icon: "icon-question-sign",
				color: "#ddd"
			}
		}
		var icon = frappe.boot.doctype_icons[doctype] || module_info.icon;

		this.get_main_icon(icon)
			.attr("doctype-name", doctype);

		this.set_title_left(function() {
			var route = frappe.get_route()[0]==module_info.link ? "" : module_info.link;
			frappe.set_route(route);
		});
	},

	get_main_icon: function(icon) {
		return this.$title_area.find(".title-icon")
			.html('<i class="'+icon+' icon-fixed-width"></i> ')
			.toggle(true);
		},

	add_help_button: function(txt) {
		this.add_icon_btn("2", "icon-question-sign", __("Help"),
			function() { msgprint($(this).data('help-text'), 'Help'); })
			.data("help-text", txt);
	},

	add_icon_btn: function(group, icon, label, click) {
		return this.iconbar.add_btn(group, icon, label, click);
	},

	add_button: function(label, click, icon, is_title) {
		return this.iconbar.add_btn("1", icon, __(label), click);
	},

	add_dropdown_button: function(parent, label, click, icon) {
		frappe.ui.toolbar.add_dropdown_button(parent, label, click, icon);
	},

	// appframe::form
	add_label: function(label) {
		this.show_form();
		return $("<label class='col-md-1 appframe-only-label'>"+label+" </label>")
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
	add_break: function() {
		// add further fields in the next line
		this.parent.find(".appframe-form .container")
			.append('<div class="clearfix invisible-xs"></div>');
	},
	add_field: function(df) {
		this.show_form();
		var f = frappe.ui.form.make_control({
			df: df,
			parent: this.parent.find(".appframe-form .container"),
			only_input: df.fieldtype=="Check" ? false : true,
		})
		f.refresh();
		$(f.wrapper)
			.addClass('col-md-2')
			.css({
				"padding-left": "0px",
				"padding-right": "7px",
			})
			.attr("title", __(df.label)).tooltip();
		f.$input.attr("placeholder", __(df.label));

		if(df.fieldtype==="Check") {
			$(f.wrapper).find(":first-child")
				.removeClass("col-md-offset-4 col-md-8");
		} else {
			$(f.wrapper)
				.prepend('<label class="appframe-control-label">' + __(df.label) + '</label>');
		}

		if(df.fieldtype=="Button") {
			$(f.wrapper).find(".appframe-control-label").html("&nbsp;")
			f.$input.addClass("btn-sm").css({"width": "100%", "margin-top": "-1px"});
		}

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

frappe.ui.make_app_page = function(opts) {
	/* help: make a standard page layout with a toolbar and title */
	/* options: [
			"parent: [HTMLElement] parent element",
			"single_column: [Boolean] false/true",
			"title: [optional] set this title"
		]
	*/
	var $wrapper = $(opts.parent)
	$('<div class="app-page container"><div class="appframe-titlebar">\
			<div class="container">\
				<div class="row">\
					<div class="titlebar-item col-sm-8">\
						<h3 class="titlebar-left-item hide"></h2>\
						<h3 class="titlebar-center-item"></h2>\
					</div>\
					<div class="titlebar-item text-right col-sm-4"></div>\
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
		<div class="appframe-primary-actions hide">\
			<div class="container">\
			</div>\
		</div>\
		<div class="appframe-wrapper">\
			<div class="appframe container">\
				<div class="appframe-timestamp hide"></div>\
				<div class="workflow-button-area btn-group pull-right hide"></div>\
				<div class="clearfix"></div>\
			</div>\
		</div></div>\
		<div class="appframe-footer hide"></div>').appendTo($wrapper);

	if(opts.single_column) {
		opts.parent.body = $('<div class="layout-main"></div>').appendTo($wrapper.find(".appframe"));
	} else {
		opts.parent.layout = $('<div class="row">\
			<div class="layout-main-section col-sm-9"></div>\
			<div class="layout-side-section col-sm-3"></div>\
			</div>').appendTo($wrapper.find(".appframe"));

		opts.parent.body = opts.parent.layout.find(".layout-main-section");
	}
	opts.parent.appframe = new frappe.ui.AppFrame($wrapper);
	if(opts.set_document_title!==undefined)
		opts.parent.appframe.set_document_title = opts.set_document_title;
	if(opts.title) opts.parent.appframe.set_title(opts.title);
	if(opts.icon) opts.parent.appframe.get_main_icon(opts.icon);
	if(opts.full_width) $wrapper.find(".app-page").addClass("full-width");

}
