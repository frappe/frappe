wn.pages['applications'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: 'Applications',
		single_column: true
	});

	wn.call({
		method:"webnotes.core.page.applications.applications.get_app_list",
		callback: function(r) {
			var $main = $(wrapper).find(".layout-main")
			if(!keys(r.message).length) {
				$main.html('<div class="alert alert-info">No Apps Installed</div>');
				return;
			}
			$main.empty();
			$.each(r.message, function(app_key, app) {
				$.extend(app, app.app_icon);
				$app = $($r('<div style="border-bottom: 1px solid #c7c7c7; margin-bottom: 10px;">\
						<div style="float: left; width: 50px;">\
							<span style="padding: 10px; background-color: %(app_color)s; \
								border-radius: 5px; display: inline-block; ">\
								<i class="%(app_icon)s icon-fixed-width" \
									style="font-size: 30px; color: white; \
										text-align: center; padding-right: 0px;"></i>\
							</span>\
						</div>\
						<div style="margin-left: 70px;">\
							<div class="row">\
								<div class="col-xs-10">\
									<p><b>%(app_name)s</b></p>\
									<p class="text-muted">%(app_description)s\
										<br>Publisher: %(app_publisher)s; Version: %(app_version)s</p>\
								</div>\
								<div class="col-xs-2 button-area"></div>\
							</div>\
						</div>\
					</div>', app))
				$app.appendTo($main)
				
				if(app.installed) {
					$btn = $('<button class="btn btn-success" disabled=disabled>\
						<i class="icon-ok"></i> Installed</button>');
				} else {
					$btn = $('<button class="btn btn-info">Install</button>')
						.attr("data-app", app_key)
						.on("click", function() {
						wn.call({
							method:"webnotes.installer.install_app",
							args: {name: $(this).attr("data-app")},
							callback: function(r) {
								if(!r.exc) {
									msgprint("<i class='icon-ok'></i> Installed");
									msgprint("Refreshing...");
									setTimeout(function() { window.location.reload() }, 2000)
								}
							}
						})
					});
				}
				$btn.appendTo($app.find(".button-area"))
			})
		}
	})
}