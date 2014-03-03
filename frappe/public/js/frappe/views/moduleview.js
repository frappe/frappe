// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views.moduleview");
frappe.provide("frappe.module_page");

frappe.views.ModuleFactory = frappe.views.Factory.extend({
	make: function(route) {
		var module = route[1];
		this.page = this.make_page(false);
		frappe.views.moduleview[module] = this.page;
		this.page.moduleview = new frappe.views.moduleview.ModuleView(this.page, module);
	},
});

frappe.views.moduleview.make = function(wrapper, module, method) {
	if(!method) method = "frappe.widgets.moduleview.get";
	
	wrapper.module_view = new frappe.views.moduleview.ModuleView(wrapper, module, method);

}

frappe.views.show_open_count_list = function(element) {
	var doctype = $(element).attr("data-doctype");
	var condition = frappe.boot.notification_info.conditions[doctype];
	if(condition) {
		frappe.route_options = condition;
		var route = frappe.get_route()
		if(route[0]==="List" && route[1]===doctype) {
			frappe.pages["List/" + doctype].doclistview.refresh();
		} else {
			frappe.set_route("List", doctype);
		}
	}
}

frappe.views.moduleview.ModuleView = Class.extend({
	init: function(wrapper, module) {
		this.prepare(wrapper, module);
		this.make(wrapper, module);
	},
	prepare: function(wrapper, module) {
		var me = this;
		$(wrapper).empty();
		frappe.ui.make_app_page({
			parent: wrapper,
			single_column: true,
			title: frappe._(frappe.modules[module] && frappe.modules[module].label || module)
		});
		wrapper.appframe.add_module_icon(module);
		wrapper.appframe.set_title_left('<i class="icon-angle-left"></i> Home', function() { frappe.set_route(""); });
		wrapper.appframe.set_title_right(frappe._("Refresh"), function() {
			me.make(wrapper, module);
		});
		
		// full refresh
		wrapper.refresh = function() {
			// remake on refresh
			if((new Date() - me.created_on) > (180 * 1000)) {
				me.make(wrapper, module);
			}
		};
		
		// counts
		$(document).on("notification-update", function() {
			if(wrapper.$layout) {
				me.update_open_count(wrapper.$layout);
			}
		});
	},
	make: function(wrapper, module) {
		var me = this;
		return frappe.call({
			method: "frappe.widgets.moduleview.get",
			args: {
				module: module 
			},
			callback: function(r) {
				me.render(wrapper, r.message);
			}
		});
	},
	render: function(wrapper, message) {
		var me = this;
		this.doctypes = [];
		var $layout = this.make_layout(wrapper);
		wrapper.$layout = $layout;

		$.each(message.data, function(i, d) {
			// d is a section
			me.add_section(d, $layout);
			me.add_items(d, $layout);
		});
		
		me.add_reports(message.reports, $layout);
		me.show_counts(message.item_count, $layout);
		me.setup_navigation($layout);
		
		// for refresh
		this.created_on = new Date();
	},
	
	make_layout: function(wrapper) {
		return $('<div class="row">\
				<div class="col-sm-3">\
					<ul class="nav nav-pills nav-stacked"></ul>\
				</div>\
				<div class="col-sm-9 contents">\
				</div>\
			</div>').appendTo($(wrapper).find(".layout-main").empty());
	},
	
	add_section: function(d, $layout) {
		if(!d._label) d._label = d.label.toLowerCase().replace(/ /g, "_");
		var $sections = $layout.find(".nav-pills");
		var $nav = $sections.find('[data-label="'+d._label+'"]');
		
		// if not found, add section
		if(!$nav.length) {
			// create nav tab
			$nav = $('<li><a><i class="'+d.icon+' icon-fixed-width"></i> '
				+ frappe._(d.label)+'</a></li>')
				.attr("data-label", d._label)
				.appendTo($sections);
			
			// create content pane for this nav
			var $content = $('<div class="panel panel-default"></div>')
				.toggle(false)
				.attr("data-content-label", d._label)
				.appendTo($layout.find(".contents"));
			
			$('<div class="panel-heading">').appendTo($content).html('<i class="'+d.icon+'"></i> ' 
				+ d.label);
			
			var $list = $('<ul class="list-group">').appendTo($content);
		}
	},
	
	add_items: function(d, $layout) {
		var me = this;
		var $content = $layout.find('[data-content-label="' + d._label + '"]');
		var $list = $content.find(".list-group");
		
		// add items in each pane
		$.each(d.items, function(i, item) {
			if(item.country && frappe.boot.control_panel.country!==item.country) return;
			
			if((item.type==="doctype" && frappe.model.can_read(item.name)) 
				|| (item.type==="page" && frappe.boot.page_info[item.name])
				|| (item.type==="report" && frappe.model.can_get_report(item.doctype))) {
					
				if(!item.label) {
					item.label = __(item.name);
				}
				if(item.type==="doctype") {
					item.icon = item.icon || frappe.boot.doctype_icons[item.name];
					if(me.doctypes.indexOf(item.name)===-1) {
						me.doctypes.push(item.name);
					}
				} else if(item.type==="report" && item.doctype) {
					item.icon = item.icon || frappe.boot.doctype_icons[item.doctype];
				}
				
				item.description = cstr(item.description);
				
				$list_item = $($r('<li class="list-group-item">\
					<div class="row">\
						<div class="col-sm-6 list-item-name">\
							<a><i class="%(icon)s icon-fixed-width"></i> %(label)s</a></div>\
						<div class="col-sm-6 text-muted list-item-description">%(description)s</div>\
					</div>\
					</li>', item)).appendTo($list);
				
				// expand col if no description
				if(!item.description) {
					$list_item.find(".list-item-description").remove();
					$list_item.find(".list-item-name").removeClass("col-sm-6").addClass("col-sm-12");
				}
				
				$list_item.find("a")
					.on("click", function() {
						if(item.route) {
							frappe.set_route(item.route);
						} else if(item.type==="doctype") {
							frappe.set_route("List", item.name)
						} 
						else if(item.type==="page") {
							frappe.set_route(item.route || item.name);
						}
						else if(item.type==="report") {
							if(item.is_query_report) {
								frappe.set_route("query-report", item.name);
							} else {
								frappe.set_route("Report", item.doctype, item.name);
							}
						}
					});
				
				var show_count = (item.type==="doctype" || (item.type==="page" && item.doctype)) && !item.hide_count
				if(show_count) {
					$(repl('<span data-doctype-count="%(doctype)s" style="margin-left: 2px;"></span>',
						{doctype: item.doctype || item.name})).appendTo($list_item.find(".list-item-name"));
				}
			}
		});
	},
	
	add_reports: function(reports, $layout) {
		if(!(reports && reports.length)) return;
		
		var reports_section = {
			label: __("Custom Reports"),
			icon: "icon-list",
			items: reports
		}
		this.add_section(reports_section, $layout);
		this.add_items(reports_section, $layout);
	},
	
	show_counts: function(item_count, $layout) {
		// total count
		$.each(item_count, function(doctype, count) {
			$layout.find("[data-doctype-count='"+doctype+"']")
				.html(count)
				.addClass("badge badge-count pull-right")
				.css({cursor:"pointer"});
		});
		
		// open count
		this.update_open_count($layout);
	},
	
	setup_navigation: function($layout) {
		var me = this;
		// section selection (can't use tab api - routing)
		var $sections = $layout.find(".nav-pills");
		$sections.find('a').click(function (e) {
			e.preventDefault();
			if($(this).parent().hasClass("active")) {
				return;
			}
			$(this).parents("ul:first").find("li.active").removeClass("active");
			$(this).parent().addClass("active");
			$layout.find(".panel").toggle(false);
			$layout.find('[data-content-label="'+ $(this).parent().attr("data-label") +'"]').toggle(true);
		});
		$sections.find('a:first').trigger("click");
		
		$layout.on("click", ".badge-important", function() {
			frappe.views.show_open_count_list(this);
		});

		$layout.on("click", ".badge-count", function() {
			var doctype = $(this).attr("data-doctype-count");
			frappe.set_route("List", doctype);
		});		
	},
	
	update_open_count: function($layout) {
		var me = this;
		$layout.find(".badge-important").remove();
		if(frappe.boot.notification_info.open_count_doctype) {
			$.each(frappe.boot.notification_info.open_count_doctype, function(doctype, count) {
				if(count && in_list(me.doctypes, doctype)) {
					$('<span>')
						.css({
							"cursor": "pointer",
							"margin-right": "0px"
						})
						.addClass("badge badge-important pull-right")
						.html(count)
						.attr("data-doctype", doctype)
						.insertAfter($layout.find("[data-doctype-count='"+doctype+"']"));
				}
			})
		}
	},
});
