frappe.provide("frappe.applications");

frappe.pages['applications'].on_page_load = function(parent) {
	frappe.applications.installer = new frappe.applications.Installer(parent);
};

frappe.applications.Installer = Class.extend({
	init: function(parent) {
		this.parent = parent;
		this.get_app_list();
	},

	get_app_list: function() {
		var me = this;
		return frappe.call({
			method: "frappe.desk.page.applications.applications.get_app_list",
			callback: function(r) {
				var apps = r.message;

				me.make_page();

				// no apps
				if(!keys(apps).length) {
					me.wrapper.html('<div class="text-muted app-listing padding">' + __("No Apps Installed") + '</div>');
					return;
				}

				me.wrapper.empty();
				me.make_search();
				me.make_app_list(apps);
			}
		});
	},

	make_search: function() {
		var me = this;
		$('<div class="padding search-wrapper panel-bg"><div class="form-group">\
			<input type="text" class="form-control app-search" placeholder="Search" name="search"/></div></div>')
			.appendTo(this.wrapper)
			.find(".app-search")
				.on("keyup", function() {
					var val = ($(this).val() || "").toLowerCase();
					me.wrapper.find(".app-listing").each(function() {
						$(this).toggle($(this).attr("data-title").toLowerCase().indexOf(val)!==-1);
					});
				});
	},

	make_app_list: function(apps) {
		var me = this;
		var modules = {};

		$.each(Object.keys(apps).sort(), function(i, app_key) {
			var app = apps[app_key];

			modules[app_key] = {
				label: app.app_title,
				icon: app.app_icon,
				color: app.app_color,
				is_app: true
			};

			app.app_icon = frappe.ui.app_icon.get_html(app_key, null, modules);

			$(frappe.render_template("application_row", {app: app})).appendTo(me.wrapper);
		});

		this.wrapper.find(".install").on("click", function() {
			me.install_app($(this).attr("data-app"));
		});

	},

	install_app: function(app_name) {
		frappe.call({
			method: "frappe.desk.page.applications.applications.install_app",
			args: { name: app_name },
			callback: function(r) {
				if(!r.exc) {
					msgprint(__("Installed"));
					msgprint(__("Refreshing..."));
					setTimeout(function() { window.location.reload() }, 2000)
				}
			}
		});
	},

	make_page: function() {
		if (this.page)
			return;

		frappe.ui.make_app_page({
			parent: this.parent,
			title: __('Application Installer'),
			icon: "icon-download",
			single_column: true
		});

		this.page = this.parent.page;
		this.wrapper = $('<div></div>').appendTo(this.page.main);

	}
});
