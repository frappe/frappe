// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.pages['Setup'].onload = function(wrapper) { 
	if(msg_dialog && msg_dialog.display) msg_dialog.hide();
	wn.ui.make_app_page({
		parent: wrapper,
		title: wn._('Setup'),
		single_column: true
	});

	wrapper.appframe.add_module_icon("Setup");
	wrapper.appframe.set_title_right(wn._("Refresh"), function() {
		wn.setup.make(wrapper);
	});
	
	wn.setup.make(wrapper);
	
}

wn.setup = {
	make: function(wrapper) {
		wn.call({
			method: "webnotes.core.page.setup.setup.get",
			callback: function(r) {
				wn.setup.render(r.message, $(wrapper).find(".layout-main").empty())
			}
		})
	},
	render: function(data, wrapper) {
		$('<div class="row">\
			<div class="col-sm-3">\
				<ul class="nav nav-pills nav-stacked"></ul>\
			</div>\
			<div class="col-sm-9 contents">\
			</div>\
		</div>').appendTo(wrapper);
		
		var $sections = wrapper.find(".nav-pills");
		$.each(data, function(i, d) {
			d._label = d.label.toLowerCase().replace(/ /g, "_");
			var $nav = $sections.find('[data-label="'+d._label+'"]');
			
			if(!$sections.find('[data-label="'+d._label+'"]').length) {
				$nav = $('<li><a><i class="'+d.icon+' icon-fixed-width"></i> '
					+ wn._(d.label)+'</a></li>')
					.attr("data-label", d._label)
					.appendTo($sections);
				var $content = $('<div class="panel panel-default"></div>')
					.toggle(false)
					.attr("id", d._label)
					.appendTo(wrapper.find(".contents"))
				$('<div class="panel-heading">').appendTo($content).html('<i class="'+d.icon+'"></i> ' 
					+ d.label);
				var $list = $('<ul class="list-group">').appendTo($content);
			} else {
				var $content = $("#" + d._label);
				var $list = $content.find(".list-group");
			}
			
			// add items
			$.each(d.items, function(i, item) {
				if((item.type==="doctype" && wn.model.can_read(item.name)) 
					|| (item.type==="page" && wn.boot.page_info[item.name])) {
					
					if(!item.label) {
						item.label = item.name;
					}
					if(item.type==="doctype") {
						item.icon = wn.boot.doctype_icons[item.name];
					}
					
					$list_item = $($r('<li class="list-group-item">\
					<div class="row">\
						<div class="col-xs-4"><a><i class="%(icon)s icon-fixed-width"></i> %(label)s</a></div>\
						<div class="col-xs-8 text-muted">%(description)s</div>\
					</div>\
					</li>', item)).appendTo($list);
					
					$list_item.find("a")
						.attr("data-type", item.type)
						.attr("data-name", item.link || item.name)
						.on("click", function() {
							if($(this).attr("data-type")==="doctype") {
								wn.set_route("List", $(this).attr("data-name"))
							} 
							else if($(this).attr("data-type")==="page") {
								wn.set_route($(this).attr("data-name"))
							}
						});
				}
			})
		})
		
		// section selection (can't use tab api - routing)
		$sections.find('a').click(function (e) {
			e.preventDefault();
			if($(this).parent().hasClass("active")) {
				return;
			}
			$(this).parents("ul:first").find("li.active").removeClass("active");
			$(this).parent().addClass("active");
			wrapper.find(".panel").toggle(false);
			$("#" + $(this).parent().attr("data-label")).toggle(true);
		});
		
		$sections.find('a:first').trigger("click");
	}
}
