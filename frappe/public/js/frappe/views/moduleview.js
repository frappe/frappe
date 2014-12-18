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
	if(!method) method = "frappe.desk.moduleview.get";

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

frappe.get_module = function(m) {
	var module = frappe.modules[m];
	if (!module) {
		return;
	}

	module.name = m;

	if(module.type==="module" && !module.link) {
		module.link = "Module/" + m;
	}

	if(module.link) {
		module._id = module.link.toLowerCase().replace("/", "-");
	}

	if(!module.label) {
		module.label = m;
	}

	if(!module._label) {
		module._label = __(module.label || module.name);
	}

	return module;
}


frappe.views.moduleview.ModuleView = Class.extend({
	init: function(wrapper, module) {
		this.module = module;
		this.prepare(wrapper, module);
		this.make(wrapper, module);
	},
	prepare: function(wrapper, module) {
		var me = this;
		$(wrapper).empty();
		frappe.ui.make_app_page({
			parent: wrapper,
			single_column: true,
			title: __(frappe.modules[module] && frappe.modules[module].label || module)
		});
		wrapper.appframe.set_title_left(function() { frappe.set_route(""); });
		wrapper.appframe.set_title_right(__("Refresh"), function() {
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
			method: "frappe.desk.moduleview.get",
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

		me.item_count = message.item_count;
		me.add_reports(message.reports, $layout);
		me.remove_empty_sections($layout);
		me.show_counts($layout);
		me.setup_navigation($layout);

		// for refresh
		this.created_on = new Date();
	},

	make_layout: function(wrapper) {
		return $('<div class="row module-view-layout">\
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
			$nav = $('<li title="'+__(d.label)+'">\
				<a><i class="'+d.icon+' icon-fixed-width"></i><span class="hidden-xs"> '
				+ __(d.label)+'</span></a></li>')
				.attr("data-label", d._label)
				.attr("data-section-label", d.label)
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
			if(item.country && frappe.boot.sysdefaults.country!==item.country) return;

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

				item.description = cstr(item.description) + " ";

				$list_item = $($r('<li class="list-group-item">\
					<div class="row">\
						<div class="col-sm-6 list-item-name">\
							<a class="form-link" data-label="%(label)s"><i class="%(icon)s icon-fixed-width"></i> %(label)s</a></div>\
						<div class="col-sm-6 text-muted list-item-description">%(description)s</div>\
					</div>\
					</li>', item)).appendTo($list);

				// expand col if no description
				if(!item.description) {
					$list_item.find(".list-item-description").remove();
					$list_item.find(".list-item-name").removeClass("col-sm-6").addClass("col-sm-12");
				}

				if(item.onclick) {
					$list_item.find("a")
						.on("click", function() {
							var fn = eval(item.onclick);
							if(typeof(fn)==="function") {
								fn();
							}
						});
				} else {
					var route = item.route;
					if(!route) {
						if(item.type==="doctype") {
							route = "List/" + encodeURIComponent(item.name);
							frappe.listview_parent_route[item.name] = ["Module", me.module];
						} else if(item.type==="page") {
							route = item.route || item.link || item.name;
						} else if(item.type==="report") {
							if(item.is_query_report) {
								route = "query-report/" + encodeURIComponent(item.name);
							} else {
								route = "Report/" + encodeURIComponent(item.doctype) + "/" + encodeURIComponent(item.name);
							}
						}
					}

					$list_item.find("a")
						.attr("href", "#" + route)
				}


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
			icon: "icon-list-alt",
			items: reports
		}
		this.add_section(reports_section, $layout);
		this.add_items(reports_section, $layout);
	},

	remove_empty_sections: function($layout) {
		$layout.find(".contents [data-content-label]").each(function(i, panel) {
			if (!$(panel).find(".list-group").html()) {
				$layout.find('.nav-pills [data-label="' + $(panel).attr("data-content-label") + '"]').remove();
			}
		});
	},

	show_counts: function($layout) {
		var me = this;
		// total count
		$.each(this.item_count, function(label, counts) {
			if(!counts) return false;
			$.each(counts, function(doctype, count) {
				$layout.find("[data-doctype-count='"+doctype+"']")
					.html(count)
					.addClass("badge badge-count pull-right")
					.css({cursor:"pointer"});
			});
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

			var section_label = $(this).parent().attr("data-section-label");
			if(!me.item_count || me.item_count[section_label]==null) {
				frappe.call({
					"method": "frappe.desk.moduleview.get_section_count",
					"args": {
						"module": me.module,
						"section_label": section_label,
					},
					"callback": function(r) {
						me.item_count[section_label] = r.message || {};
						me.show_counts($layout);
					}
				});
			}
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
