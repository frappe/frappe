frappe.provide("frappe.applications");

frappe.pages['applications'].on_page_load = function(parent) {
	frappe.applications.installer = new frappe.applications.Installer(parent);
};

frappe.applications.Installer = Class.extend({
	init: function(parent) {
		this.parent = parent;
		this.get_app_list();
		this.setup_realtime();
	},

	get_app_list: function() {
		var me = this;
		return frappe.call({
			method: "frappe.desk.page.applications.applications.get_app_list",
			callback: function(r) {
				var apps = r.message;

				me.make_page();

				// no apps
				if(!Object.keys(apps).length) {
					me.wrapper.html('<div class="text-muted app-listing padding">' + __("No Apps Installed") + '</div>');
					return;
				}

				me.wrapper.empty();
				me.make_toolbar();
				me.make_app_list(apps);

				// startup with "Featured"
				me.toggle_category();
				me.update_no_result();
			}
		});
	},

	make_toolbar: function() {
		var me = this;
		this.category_select = this.page.add_select(__("Category"),
			[
				{"label": __("Select Category..."), value: "Featured" },
				{"label": __("Not set"), value: "Not set" },
				{"label": __("Domains"), value: "Domains" },
				{"label": __("Developer Tools"), value: "Developer Tools" },
				{"label": __("Integrations"), value: "Integrations" },
				{"label": __("Portal"), value: "Portal" },
				{"label": __("Regional Extensions"), value: "Regional Extensions" },
			]);

		this.category_select.on("change", function() {
			me.search.val("");
			me.toggle_category();
			me.update_no_result();
		});

		this.search = this.page.add_data(__("Search"))
		this.search.on("keyup", function() {
			me.title.text(__("Search Results"));

			var val = ($(this).val() || "").toLowerCase();

			// disable other inputs when searching
			me.category_select.val("Featured").prop("disabled", val.length ? true : false);
			me.show_installed.$input.prop("disabled", val.length ? true : false);

			// filter items
			me.wrapper.find(".app-listing").each(function() {
				$(this).toggle($(this).attr("data-title").toLowerCase().indexOf(val)!==-1);
			});

			me.update_no_result();
		});

		this.show_installed = this.page.add_field({fieldtype:"Check", label:__("Installed") });
		this.show_installed.$input.on("change", function() {
			me.category_select.val("Featured");
			me.search.val("");
			me.toggle_installed($(this).prop("checked"));

			// disable category and search if showing installed
			me.category_select.prop("disabled", $(this).prop("checked"));
			me.search.val("");
			me.search.prop("disabled", $(this).prop("checked"));

			me.update_no_result();
		});

	},

	toggle_installed: function(show) {
		if(show) {
			this.title.text(__("Installed Apps"));

			this.wrapper.find(".app-listing").each(function() {
				$(this).toggle($(this).attr("data-installed")==="1");
			});
		} else {
			this.toggle_category();
		}
	},

	toggle_category: function() {
		var me = this;
		var val = ($(this.category_select).val() || "Featured");

		this.title.text(__(val));
		this.wrapper.find(".app-listing").each(function() {
			// if($(this).attr("data-installed")==="1") {
			// 	var toggle = false;
			// } else
			if(val==="Featured") {
				var toggle = $(this).attr("data-featured") == "1";
			} else {
				var toggle = $(this).attr("data-category") === val;
			}
			$(this).toggle(toggle);
		});

	},

	make_app_list: function(apps) {
		var me = this;
		var modules = {};

		me.title = $('<h3 class="text-muted" style="padding: 0px 15px; \
			font-weight: 400;"></h3>').text(__("Featured")).appendTo(me.wrapper);

		$.each(Object.keys(apps).sort(), function(i, app_key) {
			var app = apps[app_key];

			modules[app_key] = {
				label: app.app_title,
				icon: app.app_icon,
				color: app.app_color,
				is_app: true
			};

			app.app_icon = frappe.ui.app_icon.get_html(modules[app_key]);

			$(frappe.render_template("application_row", {app: app})).appendTo(me.wrapper);
		});

		me.no_result = $('<p class="text-muted" style="padding: 15px;">'
			+ __('No matching apps found') + '</p>').appendTo(me.wrapper).toggle(false);

		this.wrapper.find(".install").on("click", function() {
			me.install_app($(this).attr("data-app"), $(this).attr("data-title"), this);
		});

		this.wrapper.find(".btn-remove").on("click", function() {
			me.remove_app($(this).attr("data-app"), $(this).attr("data-title"), this);
		});

	},

	update_no_result: function() {
		this.no_result.toggle(this.wrapper.find(".app-listing:visible").length ? false : true);
	},

	install_app: function(app_name, app_title, btn) {
		frappe.confirm(__("Install {0}?", [app_title]), function() {
			frappe.call({
				method: "frappe.desk.page.applications.applications.install_app",
				args: { name: app_name },
				freeze: true,
				btn: btn
			});
		});
	},

	remove_app: function(app_name, app_title, btn) {
		frappe.confirm(__("Remove {0} and delete all data?", [app_title]), function() {
			frappe.call({
				method: "frappe.desk.page.applications.applications.remove_app",
				args: { name: app_name },
				freeze: true,
				btn: btn
			});
		});
	},

	make_page: function() {
		if (this.page)
			return;

		frappe.ui.make_app_page({
			parent: this.parent,
			title: __('App Installer'),
			icon: "fa fa-download",
			single_column: true
		});

		this.page = this.parent.page;
		this.wrapper = $('<div></div>').appendTo(this.page.main);

	},

	setup_realtime: function() {
		frappe.realtime.on("install_app_progress", function(data) {
			if(data.status) {
				frappe.update_msgprint(data.status);
			}
		})
	}
});
