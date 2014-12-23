// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// __("Form")

// parent, title, single_column
// standard page with page

frappe.ui.make_app_page = function(opts) {
	/* help: make a standard page layout with a toolbar and title */
	/* options: [
			"parent: [HTMLElement] parent element",
			"single_column: [Boolean] false/true",
			"title: [optional] set this title"
		]
	*/

	opts.parent.page = new frappe.ui.Page(opts);

}

frappe.ui.Page = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		this.set_document_title = true;
		this.buttons = {};
		this.fields_dict = {};
		this.views = {};

		this.make();
		this.setup_iconbar();

	},

	make: function() {
		this.wrapper = $(this.parent);

		$(frappe.render_template("page", {})).appendTo(this.wrapper);

		if(this.single_column) {
			this.add_view("main", '<div class="layout-main">');
		} else {
			var main = this.add_view("main", '<div class="row layout-main">\
				<div class="col-sm-2 layout-side-section"></div>\
				<div class="col-sm-10">\
					<div class="layout-main-section"></div>\
				</div>\
			</div>');
		}

		this.$title_area = this.wrapper.find("h1");

		this.$sub_title_area = this.wrapper.find("h3");

		if(this.set_document_title!==undefined)
			this.set_document_title = this.set_document_title;

		if(this.title)
			this.set_title(this.title);

		if(this.icon)
			this.get_main_icon(this.icon);

		this.page_actions = this.wrapper.find(".page-actions");
		this.menu = this.page_actions.find(".dropdown-menu");
		this.indicator = this.wrapper.find(".indicator");
		this.btn_primary = this.page_actions.find(".btn-primary");
		this.btn_secondary = this.page_actions.find(".btn-secondary");
		this.menu_btn_group = this.page_actions.find(".btn-group");
	},

	set_indicator: function(label, color) {
		this.clear_indicator().removeClass("hide").html(label).addClass(color);
	},

	clear_indicator: function() {
		return this.indicator.removeClass().addClass("indicator hide");
	},

	set_primary_action: function(label, click) {
		this.btn_primary.removeClass("hide").prop("disabled", false).html(label).on("click", click);
	},

	set_secondary_action: function(label, click) {
		this.btn_secondary.removeClass("hide").prop("disabled", false).html(label).on("click", click);
	},

	clear_primary_action: function() {
		this.btn_primary.addClass("hide");
	},

	clear_actions: function() {
		this.btn_primary.addClass("hide").unbind("click");
		this.btn_secondary.addClass("hide").unbind("click");
	},

	add_menu_item: function(label, click, standard) {
		this.show_menu();

		var $link = $('<li><a class="grey-link">'+ label +'</a><li>');
		$link.find("a").on("click", click);

		if(standard) {
			$link.appendTo(this.menu);
		} else {
			this.divider = this.menu.find(".divider");
			if(!this.divider.length) {
				this.divider = $('<li class="divider user-action"></li>').prependTo(this.menu);
			}
			$link.addClass("user-action").insertBefore(this.divider);
		}

		return $link;
	},

	add_divider: function() {
		return $('<li class="divider"></li>').appendTo(this.menu);
	},

	hide_menu: function() {
		this.menu_btn_group.addClass("hide");
	},

	show_menu: function() {
		this.menu_btn_group.removeClass("hide");
	},

	clear_menu: function() {
		this.menu.empty();
		this.hide_menu();
	},

	clear_user_actions: function() {
		this.menu.find(".user-action").remove();
	},

	setup_iconbar: function() {
		var me = this;
		this.iconbar = new frappe.ui.IconBar(this.wrapper.find(".page-toolbar .container"), 3);
		this.iconbar.$wrapper.find(".iconbar-3").addClass("pull-right");

		this.iconbar.$wrapper.on("shown", function() {
			me.wrapper.find(".page-toolbar").removeClass("hide")
		})
		this.iconbar.$wrapper.on("hidden", function() {
			me.wrapper.find(".page-toolbar").addClass("hide")
		})
	},

	// page::title
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
		return this.add_icon_btn("1", icon, __(label), click);
	},

	add_dropdown_button: function(parent, label, click, icon) {
		frappe.ui.toolbar.add_dropdown_button(parent, label, click, icon);
	},

	// page::form
	add_label: function(label) {
		this.show_form();
		return $("<label class='col-md-1 page-only-label'>"+label+" </label>")
			.appendTo(this.wrapper.find(".page-form .container"));
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
			.appendTo(this.wrapper.find(".page-form .container"))
			.find("input");
	},
	add_break: function() {
		// add further fields in the next line
		this.wrapper.find(".page-form .container")
			.append('<div class="clearfix invisible-xs"></div>');
	},
	add_field: function(df) {
		this.show_form();
		var f = frappe.ui.form.make_control({
			df: df,
			parent: this.wrapper.find(".page-form .container"),
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
				.prepend('<label class="page-control-label">' + __(df.label) + '</label>');
		}

		if(df.fieldtype=="Button") {
			$(f.wrapper).find(".page-control-label").html("&nbsp;")
			f.$input.addClass("btn-sm").css({"width": "100%", "margin-top": "-1px"});
		}

		if(df["default"])
			f.set_input(df["default"])
		this.fields_dict[df.fieldname || df.label] = f;
		return f;
	},
	show_form: function() {
		this.wrapper.find(".page-form").removeClass("hide");
	},
	add_view: function(name, html) {
		this.views[name] = $(html).appendTo($(this.wrapper).find(".page-content"));
		if(!this.current_view) {
			this.current_view = this.views[name];
		} else {
			this.views[name].toggle(false);
		}
		return this.views[name];
	},
	set_view: function(name) {
		this.current_view && this.current_view.toggle(false);
		this.current_view = this.views[name];
		this.views[name].toggle(true);
	}
});
