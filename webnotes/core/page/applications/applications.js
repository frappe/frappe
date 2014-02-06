wn.pages['applications'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: 'Applications',
		single_column: true
	});

	wn.call({
		method:"webnotes.core.page.applications.applications.get_app_list",
		callback: function(r) {
			var $main = $(wrapper).find(".layout-main");
			
			if(!keys(r.message).length) {
				$main.html('<div class="alert alert-info">No Apps Installed</div>');
				return;
			}
			$main.empty();

			// search
			$('<div class="row">\
				<div class="col-md-6">\
					<input type="text" class="form-control app-search" placeholder="Search" name="search"/>\
				</div>\
			</div><hr>').appendTo($main).find(".app-search").on("keyup", function() {
				var val = $(this).val();
				$main.find(".app-listing").each(function() {
					$(this).toggle($(this).attr("data-title").toLowerCase().indexOf(val)!==-1);
				});
			})

			$.each(r.message, function(app_key, app) {
				wn.modules[app_key] = {
					label: app.app_title,
					icon: app.app_icon,
					color: app.app_color,
					is_app: true
				}
				app.app_icon = wn.ui.app_icon.get_html(app_key);
				$app = $($r('<div style="border-bottom: 1px solid #c7c7c7; margin-bottom: 10px;" \
					class="app-listing" data-title="%(app_title)s">\
						<div style="float: left; width: 80px;">\
							%(app_icon)s\
						</div>\
						<div style="margin-left: 95px;">\
							<div class="row">\
								<div class="col-xs-10">\
									<p><b class="title">%(app_title)s</b></p>\
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
						.attr("data-app", app.app_name)
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