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
			this.title_right = $("<a class='btn btn-sm "+btn_class+"'>")
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

	add_primary_action: function(label, click, icon, toolbar_or_class) {
		this.sidebar.add_user_action(label, click);
		return;

		if(toolbar_or_class===true) {
			this.add_icon_btn("4", icon, label, click);
			return;
		}

		var wrapper = this.parent.find(".appframe-primary-actions .container");
		this.parent.find(".appframe-primary-actions").removeClass("hide");

		if($.isArray(click)) {
			// if onclick is an array, add a dropdown button
			var $btn_group = $('<div class="btn-group">\
				<button type="button" class="btn btn-primary dropdown-toggle" data-toggle="dropdown">\
					'+label+' <span class="caret"></span>\
				</button>\
				<ul class="dropdown-menu" role="menu">\
				</ul>').appendTo(wrapper);

			var $ul = $btn_group.find(".dropdown-menu");
			$.each(click, function(i, v) {
				var $a = $('<li><a>'+v.label+'</a></li>')
					.appendTo($ul)
					.find('a').on('click', v.click);
				if(v.value) $a.attr('data-value', v.value);
			});

			// activate dropdown
			$btn_group.find(".dropdown-toggle").dropdown();
		} else {
			return $(repl('<button class="btn %(klass)s btn-sm">\
				<i class="%(icon)s"></i> %(label)s</button>', {label:label, icon:icon,
					klass: toolbar_or_class || "btn-primary"}))
				.on("click", click)
				.appendTo(wrapper);
		};

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
	views: {},
	add_view: function(name, html) {
		this.views[name] = $(html).appendTo($(this.parent).find(".appframe"));
		if(!this.current_view) {
			this.current_view = this.views[name];
		} else {
			this.views[name].toggle(false);
		}
		return this.views[name];
	},
	set_view: function(name) {
		this.current_view && this.current_view.toggle(false);
		this.views[name].toggle(true);
		this.current_view = this.views[name];
	}
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
	$(frappe.templates.appframe).appendTo($wrapper);

	var $appframe = $wrapper.find(".appframe");

	opts.parent.appframe = new frappe.ui.AppFrame($wrapper);

	if(opts.single_column) {
		opts.parent.body = opts.parent.appframe.add_view("main", '<div class="layout-main">');
	} else {
		var main = opts.parent.appframe.add_view("main", '<div class="row layout-main">\
			<div class="col-sm-10">\
				<div class="layout-main-section" style="margin: 0px -15px;"></div>\
			</div>\
			<div class="col-sm-2 layout-side-section"></div>\
		</div>');
		opts.parent.body = main.find(".layout-main-section");
	}

	if(opts.set_document_title!==undefined)
		opts.parent.appframe.set_document_title = opts.set_document_title;

	if(opts.title)
		opts.parent.appframe.set_title(opts.title);

	if(opts.icon)
		opts.parent.appframe.get_main_icon(opts.icon);
}
