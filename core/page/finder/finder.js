wn.pages['finder'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: 'Finder',
		single_column: true
	});
	
	var $body = $(wrapper).find(".layout-main").addClass("row");
	var start = 0;

	var $modules = $('<div class="col-sm-3">\
		<div class="panel panel-info">\
			<div class="panel-heading">Modules</div>\
			<table class="table">\
				<tbody></tbody>\
			</table>\
		</div>\
	</div>').appendTo($body).find("tbody");
	
	var $doctypes = $('<div class="col-sm-3">\
		<div class="panel panel-info">\
			<div class="panel-heading">DocTypes</div>\
			<table class="table">\
				<tbody></tbody>\
			</table>\
		</div>\
	</div>').appendTo($body).find("tbody");

	var $list = $('<div class="col-sm-6">\
		<div class="panel panel-default">\
			<div class="panel-heading">Documents</div>\
			<table class="table">\
				<tbody></tbody>\
			</table>\
		</div>\
	</div>').appendTo($body).find("tbody");
	
	// modules
	$.each(keys(wn.boot.notification_info.module_doctypes).sort(), function(i, module) {
		$($r('<tr><td><a data-module="%(module)s" class="module-link">%(module)s</a></td></tr>', 
			{module: module})).appendTo($modules);
	});

	$modules.on("click", ".module-link", function() {
		// doctypes
		var module = $(this).attr("data-module");
		$doctypes.empty();
		$.each(wn.boot.notification_info.module_doctypes[module].sort(), function(i, doctype) {
			$($r('<tr><td><a data-doctype="%(doctype)s" class="doctype-link">%(doctype)s</a></td></tr>', 
				{doctype: doctype})).appendTo($doctypes)
		});
	});
	
	
	$doctypes.on("click", ".doctype-link", function() {
		$list.empty();
		var doctype = $(this).attr("data-doctype");
		wn.call({
			method: "webnotes.widgets.reportview.get",
			args: {
				doctype: doctype,
				fields: ["name", "modified", "owner"],
				limit_start: start || 0,
			},
			callback: function(r) {
				console.log(r);
				if(r.message.values) {
					$.each(r.message.values, function(i, v) {
						$($r('<tr><td>\
							<a data-name="%(name)s" href="#Form/%(doctype)s/%(name)s">%(name)s</a>\
							<span class="text-muted text-small">%(owner)s</span>\
							<span class="text-muted pull-right">%(modified)s</span>\
							</td></tr>', {
								doctype: doctype,
								name: v[1],
								owner: v[0],
								modified: comment_when(v[2])
							})).appendTo($list)
					})
				}
			}
		})
	})
}