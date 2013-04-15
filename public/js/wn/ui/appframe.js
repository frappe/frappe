// Copyright 2013 Web Notes Technologies Pvt Ltd
// License: MIT. See license.txt

// wn._("Form")

wn.ui.AppFrame = Class.extend({
	init: function(parent, title, module) {
		this.set_document_title = true;
		this.buttons = {};
		this.$w = $('<div class="span12"></div>').prependTo(parent);
				
		this.$titlebar = $('<div class="appframe-titlebar">\
			<div class="row">\
				<span class="appframe-breadcrumb span3">\
				</span>\
				<span class="appframe-center span6">\
					<span class="appframe-title"></span>\
					<span class="appframe-subject"></span>\
				</span>\
				<span class="appframe-right span3">\
					<span class="btn-group"></span>\
					<span class="close">&times;</span>\
				</span>\
			</div>\
		</div>').appendTo(this.$w);
		
		this.$w.find('.close').click(function() {
			window.history.back();
		})
		
		if(title) 
			this.set_title(title);
			
	},
	title: function(txt) {
		this.set_title(txt);
	},
	set_title: function(txt, full_text) {
		if(this.set_document_title) 
			document.title = txt;
		this.$titlebar.find(".appframe-title").html(txt)
			.attr("title", full_text || txt);
	},
	clear_breadcrumbs: function() {
		this.$w.find(".appframe-breadcrumb").empty();
	},
	add_breadcrumb: function(icon, link, title) {
		if(link) {
			$(repl("<span><a href='#%(link)s' title='%(title)s'><i class='%(icon)s'></i>\
				</a></span>", {
				icon: icon,
				link: link,
				title: wn._(title)
			})).appendTo(this.$w.find(".appframe-breadcrumb"));			
		} else {
			$(repl("<span><i class='%(icon)s'></i></span>", {
				icon: icon,
			})).appendTo(this.$w.find(".appframe-breadcrumb"));			
		}
	},
	add_home_breadcrumb: function() {
		this.add_breadcrumb("icon-home", wn.home_page, "Home");
	},
	add_list_breadcrumb: function(doctype) {
		this.add_breadcrumb("icon-list", "List/" + encodeURIComponent(doctype), doctype + " List");
	},
	add_module_breadcrumb: function(module) {
		var module_info = wn.modules[module];
		if(module_info) {
			this.add_breadcrumb(module_info.icon, module_info.link,
				module_info.label || module);
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
	
	add_button: function(label, click, icon) {
		this.add_toolbar();
		args = { label: label, icon:'' };
		if(icon) {
			args.icon = '<i class="'+icon+'"></i>';
		}
		this.buttons[label] = $(repl('<button class="btn">\
			%(icon)s %(label)s</button>', args))
			.click(click)
			.appendTo(this.toolbar);
		return this.buttons[label];
	},

	add_help_button: function(txt) {
		this.add_toolbar();
		$('<button class="btn" button-type="help">\
			<b>?</b></button>')
			.data('help-text', txt)
			.click(function() { msgprint($(this).data('help-text'), 'Help'); })
			.appendTo(this.toolbar);			
	},

	clear_buttons: function() {
		this.toolbar && this.toolbar.empty();
	},

	add_toolbar: function() {
		if(!this.toolbar)
			this.$w.append('<div class="appframe-toolbar"><div class="btn-group"></div></div>');
		this.toolbar = this.$w.find('.appframe-toolbar .btn-group');
	},
	add_label: function(label) {
		return $("<span class='label'>"+label+" </span>").appendTo(this.toolbar.parent());
	},
	add_select: function(label, options) {
		this.add_toolbar();
		return $("<select style='width: 100px;'>")
			.add_options(options).appendTo(this.toolbar.parent());
	},
	add_data: function(label) {
		this.add_toolbar();
		return $("<input style='width: 100px;' type='text' placeholder='"+ label +"'>")
			.appendTo(this.toolbar.parent());
	}, 
	add_date: function(label, date) {
		this.add_toolbar();
		return $("<input style='width: 80px;' type='text'>").datepicker({
			dateFormat: sys_defaults.date_format.replace("yyyy", "yy"),
			changeYear: true,
		}).val(dateutil.str_to_user(date) || "").appendTo(this.toolbar.parent());
	},
	add_check: function(label) {
		this.add_toolbar();
		return $("<label style='display: inline;'><input type='checkbox' \
			style='margin-top: -2px;'/> " + label + "</label>")
			.appendTo(this.toolbar.parent())
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
		$('<div class="appframe span12">\
			<div class="layout-appframe row"></div>\
			<div class="layout-main"></div>\
		</div>').appendTo(opts.parent);
	} else {
		$('<div class="appframe span12">\
			<div class="layout-appframe row"></div>\
			<div class="row">\
				<div class="layout-main-section span9"></div>\
				<div class="layout-side-section span3"></div>\
			</div>\
		</div>').appendTo(opts.parent);
	}
	opts.parent.appframe = new wn.ui.AppFrame($(opts.parent).find('.layout-appframe'));
	if(opts.set_document_title!==undefined)
		opts.parent.appframe.set_document_title = opts.set_document_title;
	if(opts.title) opts.parent.appframe.title(opts.title);
}