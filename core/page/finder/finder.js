// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt 

// todo
// - basic search in documents

wn.pages['finder'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: 'Finder',
		single_column: true
	});
	wrapper.appframe.add_module_icon("Finder");
	
	var $body = $(wrapper).find(".layout-main").addClass("row");
	var start = 0,
		doctype = null,
		module = null;

	var get_col = function(colsize, icon, label, panel_class) {
		return $('<div class="col-sm-'+colsize+'">\
			<div class="panel panel-'+panel_class+'">\
				<div class="panel-heading"><i class="icon-'+icon+'"></i> '+label+'</div>\
				<div class="list-group">\
				</div>\
			</div>\
		</div>').appendTo($body).find(".list-group");
	}

	var $modules = get_col(3, "briefcase", "Modules", "default");
	var $doctypes = get_col(3, "folder-close", "Document Types", "default");
	var $list = get_col(6, "file", "Documents", "info");

	var reset_module = function() {
		$doctypes.empty();
		$('<div class="list-group-item row-select text-muted text-center">\
			Select Module</div>').appendTo($doctypes);
		module = null;
		reset_doctype();
	}
	
	var reset_doctype = function() {
		$list.empty();
		$('<div class="list-group-item row-select text-muted text-center">\
			Select Document Type</div>').appendTo($list);
		start=0;
	}
	
	reset_module();
	
	// modules
	$.each(keys(wn.boot.notification_info.module_doctypes).sort(), function(i, module) {
		$($r('<a class="list-group-item row-select module-link" \
				data-module="%(module)s">%(module)s\
				<span class="pull-right"><i class="icon-chevron-right"></i></span></a>', 
			{module: module})).appendTo($modules);
	});

	$modules.on("click", ".module-link", function() {
		// list doctypes
		reset_module();

		// select module
		$modules.find(".list-group-item.active").removeClass("active");
		$(this).addClass("active");

		// show doctypes
		$doctypes.find(".row-select").remove();
		module = $(this).attr("data-module");
		
		$.each(wn.boot.notification_info.module_doctypes[module].sort(), function(i, doctype) {
			$($r('<a class="list-group-item doctype-link" \
					data-doctype="%(doctype)s">%(doctype)s\
					<span class="pull-right"><i class="icon-chevron-right"></i></a>', 
				{doctype: doctype})).appendTo($doctypes)
		});
	});
	
	
	$doctypes.on("click", ".doctype-link", function() {
		reset_doctype();

		// select doctype
		$doctypes.find(".list-group-item.active").removeClass("active");
		$(this).addClass("active");

		doctype = $(this).attr("data-doctype");
		render_list();
	})
	
	$list.on("click", ".btn-more", function() {
		start = start+20;
		render_list();
	});
	
	$list.on("click", ".btn-search", function() {
		filter_list();
	})

	$list.on("keypress", ".input-search", function(e) {
		if(e.which===13)
			filter_list();
	})
	

	var filter_list = function() {
		start = 0;
		$list.find(".document-item").remove();
		render_list();
	}

	var render_list = function() {
		// remove more btn if any
		$list.find(".row-more, .row-select").remove();
		
		// loading indicator...
		add_list_row('<i class="icon-refresh icon-spin text-muted"></i>')
			.addClass("row-loading text-center")
		
		var args = {
			doctype: doctype,
			fields: ["name", "modified", "owner"],
			limit_start: start || 0,
			limit_page_length: 20
		};

		if($(".input-search").val()) {
			args.filters = [[doctype, "name", "like", "%" + $(".input-search").val() + "%"]]
		}
		
		wn.call({
			method: "webnotes.widgets.reportview.get",
			args: args,
			callback: function(r) {
				$list.find(".row-loading").remove();
				
				if(!$list.find(".input-search").length) {
					// make search
					$('<div class="list-group-item">\
						<div class="input-group">\
							<input type="text" class="form-control input-search">\
							<span class="input-group-btn">\
								<button class="btn btn-default btn-search" type="button">\
									<i class="icon-search"></i></button>\
							</span>\
						</div>\
					</div>').appendTo($list);
				}
				
				if(r.message.values) {
					$.each(r.message.values, function(i, v) {
						$($r('<a class="list-group-item document-item" \
								data-name="%(name)s" href="#Form/%(doctype)s/%(name)s">%(name)s\
							<span class="text-muted text-small">%(owner)s</span>\
							<span class="text-muted pull-right">%(modified)s</span></a>', {
								doctype: doctype,
								name: v[1],
								owner: v[0],
								modified: comment_when(v[2])
							})).appendTo($list);
					})
					if(r.message.values.length==20) {
						add_list_row('More...').addClass("row-more text-center btn-more text-muted");
					}
				} else {
					add_list_row('<i class="icon-ban-circle"></i>').addClass("text-center text-muted");
				}
			}
		})
	}
	
	var add_list_row = function(html) {
		return $('<a class="list-group-item">'+html+'</a>').appendTo($list);
	}
}