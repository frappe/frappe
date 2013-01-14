// Copyright 2013 Web Notes Technologies Pvt Ltd
// MIT Licensed. See license.txt

wn.provide("wn.views.moduleview");
wn.provide("wn.model.open_count_conditions")

wn.views.moduleview.make = function(wrapper, module) {
	var doctypes = [];

	wn.ui.make_app_page({
		parent: wrapper,
		single_column: true,
		title: wn._(wn.modules[module].label || module)
	});
	
	
	wrapper.appframe.add_home_breadcrumb();
	wrapper.appframe.add_breadcrumb(wn.modules[module].icon);
	
	// make columns
	$(wrapper).find(".layout-main").html("<div class='row'>\
		<div class='span6 main-section'></div>\
		<div class='span5 side-section'></div>\
	</div>")
	
	$(wrapper).on("click", ".badge-important", function() {
		var doctype = $(this).parent().attr("data-doctype");
		var condition = wn.model.open_count_conditions[doctype];
		if(condition) {
			wn.set_route("List", doctype, wn.utils.get_url_from_dict(condition));
		}
	});

	$(wrapper).on("click", ".badge-count", function() {
		var doctype = $(this).attr("data-doctype-count");
		wn.set_route("List", doctype);
	});
	
	var add_section = function(section) {
		var table = $(repl("<table class='table table-bordered'>\
		<thead><tr>\
			<th style='font-size: 120%;'><i class='%(icon)s'></i> %(title)s</th></tr></thead>\
		<tbody></tbody>\
		</table>", section)).appendTo(section.right 
			? $(wrapper).find(".side-section")
			: $(wrapper).find(".main-section"));
		section.table = table;
	}
	
	var add_item = function(item, section) {
		if(!item.description) item.description = "";
		if(item.count==null) item.count = "";
		
		$(repl("<tr><td><div class='row'>\
			<span"+
				((item.doctype && item.description) 
					? " data-doctype='"+item.doctype+"'" : "")
				+" class='"+(section.right ? 'span4' : 'span2')
				+"'>%(link)s</span>\
			<span class='help "+(section.right ? 'span4' : 'span3')
				+"'>%(description)s</span>"
			+ ((section.right || !item.doctype) 
				? ''
				: '<span data-doctype-count="%(doctype)s"></span>')
			+ "</div></td></tr>", item))
		.appendTo(section.table.find("tbody"));
	}
	
	// render sections
	$.each(wn.module_page[module], function(i, section) {
		add_section(section);
		$.each(section.items, function(i, item) {
			if(item.doctype) doctypes.push(item.doctype);
			if(item.doctype && !item.route) {
				item.route = "List/" + encodeURIComponent(item.doctype);
			}
			if(item.page && !item.route) {
				item.route = item.page;
			}
			
			// link
			item.link = repl("<a href='#%(route)s'>%(label)s</a>", item);
			
			// doctype permissions
			if(item.doctype && !wn.model.can_read(item.doctype)) {
				item.link = item.label;
			}
			
			// page permissions
			if(item.page && !in_list(wn.boot.allowed_pages, item.page)) {
				item.link = item.label;
			}
			
			if((item.country && wn.boot.control_panel.country==item.country) 
				|| !item.country)
				add_item(item, section)
		})
	});
	
	// render reports
	wn.call({
		method: "webnotes.widgets.moduleview.get_data",
		args: {
			module: module,
			doctypes: doctypes
		},
		callback: function(r) {
			if(r.message) {
				// reports
				if(r.message.reports.length) {
					var section = {
						title: wn._("Custom Reports"),
						right: true,
						icon: "icon-list",
					}
					add_section(section);
					$.each(r.message.reports, function(i, item) {
						if(wn.model.can_read(item.doctype)) {
							if(item.is_query_report) {
								item.link = repl("<a href='#query-report/%(name)s'>%(name)s</a>", item);
							} else {
								item.link = repl("<a href='#Report2/%(doctype)s/%(name)s'>%(name)s</a>", item);
							}
							add_item(item, section);
						}
					})
				}
				// search criteria
				if(r.message.search_criteria.length) {
					var section = {
						title: wn._("Old Style Reports"),
						right: true,
						icon: "icon-list-alt",
					}
					add_section(section);
					$.each(r.message.search_criteria, function(i, item) {
						item.criteria_name_enc = encodeURIComponent(item.criteria_name);
						if(wn.model.can_read(item.parent_doctype || item.doctype)) {
							item.link = repl('<a href="#Report/%(doctype)s/%(criteria_name_enc)s">%(criteria_name)s</a>', 
								item);
							add_item(item, section);
						}
					})
				}
				// counts
				if(r.message.item_count) {
					$.each(r.message.item_count, function(doctype, count) {
						$(wrapper).find("[data-doctype-count='"+doctype+"']")
							.html(count)
							.addClass("badge badge-count")
							.css({cursor:"pointer"});
					})
				}

				// counts
				if(r.message.open_count) {
					$.extend(wn.model.open_count_conditions, r.message.conditions);
					
					$.each(r.message.open_count, function(doctype, count) {
						$(wrapper).find("[data-doctype='"+doctype+"']")
							.append(" <span class='badge badge-important pull-right'\
								style='cursor:pointer'>" + count + "</span>");
					})
				}
			}
		}
	});	
}