frappe.ui.AppsSwitcher = class AppsSwitcher {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.sidebar_wrapper = $(this.sidebar.wrapper.find(".body-sidebar"));
		this.drop_down_expanded = false;
		this.make();
		this.setup_app_switcher();
		this.set_hover();
	}

	make() {
		this.wrapper = $(
			frappe.render_template("apps_switcher", {
				app_logo_url: frappe.boot.app_data[0].app_logo_url,
				app_title: __(frappe.boot.app_data[0].app_title),
			})
		).prependTo(this.sidebar_wrapper);
		this.app_switcher_dropdown = $(".app-switcher-dropdown");
	}

	setup_app_switcher() {
		this.app_switcher_menu = $(".app-switcher-menu");
		$(".app-switcher-dropdown").on("click", (e) => {
			this.toggle_app_menu();
			e.stopImmediatePropagation();
		});
	}
	toggle_app_menu() {
		this.toggle_active();
		this.app_switcher_menu.toggleClass("hidden");
	}
	create_app_data_map() {
		frappe.boot.app_data_map = {};
		for (var app of frappe.boot.app_data) {
			frappe.boot.app_data_map[app.app_name] = app;
			if (app.workspaces?.length) {
				this.add_app_item(app);
			}
		}
	}
	populate_apps_menu() {
		this.add_private_app();

		this.add_website_select();
		this.add_settings_select();
		this.setup_select_app();
	}

	add_app_item(app) {
		$(`<div class="app-item" data-app-name="${app.app_name}"
			data-app-route="${app.app_route}">
			<a>
				<div class="sidebar-item-icon">
					<img
						class="app-logo"
						src="${app.app_logo_url}"
						alt="${__("App Logo")}"
					>
				</div>
				<span class="app-item-title">${app.app_title}</span>
			</a>
		</div>`).appendTo(this.app_switcher_menu);
	}

	add_private_app() {
		let private_pages = this.sidebar.all_pages.filter((p) => p.public === 0);
		if (private_pages.length === 0) return;

		const app = {
			app_name: "private",
			app_title: __("My Workspaces"),
			app_route: "/app/private",
			app_logo_url: "/assets/frappe/images/frappe-framework-logo.svg",
			workspaces: private_pages,
		};

		frappe.boot.app_data_map["private"] = app;
		$(`<div class="divider"></div>`).prependTo(this.app_switcher_menu);
		$(`<div class="app-item" data-app-name="${app.app_name}"
			data-app-route="${app.app_route}">
			<a>
				<div class="sidebar-item-icon">
					<img
						class="app-logo"
						src="${app.app_logo_url}"
						alt="${__("App Logo")}"
					>
				</div>
				<span class="app-item-title">${app.app_title}</span>
			</a>
		</div>`).prependTo(this.app_switcher_menu);
	}

	setup_select_app() {
		this.app_switcher_menu.find(".app-item").on("click", (e) => {
			let item = $(e.delegateTarget);
			let route = item.attr("data-app-route");
			this.app_switcher_menu.toggleClass("hidden");
			this.toggle_active();

			if (item.attr("data-app-name") == "settings") {
				frappe.quick_edit("Workspace Settings");
				return;
			}
			if (route.startsWith("/app/private")) {
				this.set_current_app("private");
				let ws = Object.values(frappe.workspace_map).find((ws) => ws.public === 0);
				route += "/" + frappe.router.slug(ws.title);
				frappe.set_route(route);
			} else if (route.startsWith("/app")) {
				frappe.set_route(route);
				this.set_current_app(item.attr("data-app-name"));
			} else {
				// new page
				window.open(route);
			}
		});
	}
	// refactor them into one single function
	add_website_select() {
		$(`<div class="divider"></div>`).appendTo(this.app_switcher_menu);
		this.add_app_item(
			{
				app_name: "website",
				app_title: __("Website"),
				app_route: "/",
				app_logo_url: "/assets/frappe/images/web.svg",
			},
			this.app_switcher_menu
		);
	}

	add_settings_select() {
		$(`<div class="divider"></div>`).appendTo(this.app_switcher_menu);
		this.add_app_item({
			app_name: "settings",
			app_title: __("Settings"),
			app_logo_url: "/assets/frappe/images/settings-gear.svg",
		});
		let settings_item = this.app_switcher_menu.children().last();
	}

	set_current_app(app) {
		if (!app) {
			console.warn("set_current_app: app not defined");
			return;
		}
		let app_data = frappe.boot.app_data_map[app] || frappe.boot.app_data_map["frappe"];

		this.sidebar_wrapper
			.find(".app-switcher-dropdown .sidebar-item-icon img")
			.attr("src", app_data.app_logo_url);
		this.sidebar_wrapper
			.find(".app-switcher-dropdown .sidebar-item-label")
			.html(app_data.app_title);

		frappe.frappe_toolbar.set_app_logo(app_data.app_logo_url);

		if (frappe.current_app === app) return;
		frappe.current_app = app;

		// re-render the sidebar
		frappe.app.sidebar.make_sidebar();
	}

	set_hover() {
		const me = this;

		this.app_switcher_dropdown.on("mouseover", function () {
			if ($(this).hasClass("active-sidebar")) return;
			$(this).addClass("hover");

			if (!me.sidebar.sidebar_expanded) {
				$(this).removeClass("hover");
			}
		});

		this.app_switcher_dropdown.on("mouseleave", function () {
			$(this).removeClass("hover");
		});
	}

	toggle_active() {
		this.toggle_dropdown();
		this.app_switcher_dropdown.toggleClass("active-sidebar");
		if (!this.sidebar.sidebar_expanded) {
			this.app_switcher_dropdown.removeClass("active-sidebar");
		}
	}
	toggle_dropdown() {
		if (this.drop_down_expanded) {
			this.drop_down_expanded = false;
		} else {
			this.drop_down_expanded = true;
		}
	}
};
