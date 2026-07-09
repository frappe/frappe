frappe.pages["desktop"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Desktop",
		single_column: true,
		hide_sidebar: true,
		hide_workspace_dock: true,
	});
	let desktop_page = new DesktopPage(page);
	frappe.pages["desktop"].desktop_page = desktop_page;
};

frappe.pages["desktop"].on_page_show = function (wrapper) {
	frappe.pages["desktop"].desktop_page.update();
};

class DesktopPage {
	constructor(page) {
		this.page = page;
		this.desktop_menu_items = [];
	}
	update() {
		this.make();
	}
	make() {
		this.page.page_head.hide();
		$(this.page.body).empty();
		this.awesomebar_setup = false;
		$(frappe.render_template("desktop")).appendTo(this.page.body);
		this.render();
	}
	render() {
		this.wrapper = this.page.body.find(".desktop-container");
		this.render_app_icons();
		this.setup();
	}
	render_app_icons() {
		// the apps screen is powered entirely by the `add_to_apps_screen` hook,
		// surfaced as `frappe.boot.app_data`; show one icon per opted-in app.
		const apps = (frappe.boot.app_data || []).filter(
			(app) => app.on_apps_screen && app.app_route
		);

		const $container = $(`<div class="icons-container"></div>`).appendTo(this.wrapper);
		const columns = frappe.is_mobile() ? 3 : null;
		const $grid = $(
			`<div class="icons" style="display: grid;${
				columns ? ` grid-template-columns: repeat(${columns}, 1fr);` : ""
			}"></div>`
		).appendTo($container);

		apps.forEach((app) => {
			const icon_data = {
				label: app.app_title,
				logo_url: app.app_logo_url,
			};
			const $icon = $(frappe.render_template("desktop_icon", { icon: icon_data }));

			const is_external = app.app_route && app.app_route.startsWith("http");
			// opt-in per app (add_to_apps_screen `show_workspace_explorer`): the icon lands on the
			// app's workspaces in the explorer instead of jumping straight in
			const use_explorer =
				app.show_workspace_explorer && !is_external && (app.workspaces || []).length > 0;

			if (use_explorer) {
				$icon.attr("href", `/desk/workspace-explorer/${encodeURIComponent(app.app_name)}`);
				$icon.on("click", (e) => {
					e.preventDefault();
					frappe.set_route("workspace-explorer", app.app_name);
				});
			} else {
				// external apps, and apps that don't opt in, open directly
				if (is_external) $icon.attr("target", "_blank");
				$icon.attr("href", app.app_route);
			}
			$grid.append($icon);
		});

		$('[data-toggle="tooltip"]').tooltip({ placement: "bottom" });
	}
	setup() {
		$(document).trigger("desktop_screen", { desktop: this });
		this.setup_avatar();
		this.setup_notifications();
		this.setup_navbar();
		this.setup_awesomebar();
		this.handle_route_change();
	}
	setup_notifications() {
		this.notifications = new frappe.ui.Notifications({
			wrapper: $(".desktop-notifications"),
			full_height: false,
		});
	}
	setup_avatar() {
		$(".desktop-avatar").html(frappe.avatar(frappe.session.user, "avatar-medium"));
		let is_dark = document.documentElement.getAttribute("data-theme") === "dark";
		let menu_items = [
			{
				icon: "pencil",
				label: "Edit Profile",
				url: `/desk/user/${frappe.session.user}`,
			},
			{
				icon: is_dark ? "sun" : "moon",
				label: "Toggle Theme",
				onClick: function () {
					new frappe.ui.ThemeSwitcher().show();
				},
			},
			{
				icon: "info",
				label: "About",
				onClick: function () {
					return frappe.ui.toolbar.show_about();
				},
			},
			{
				icon: "life-buoy",
				label: "Frappe Support",
				onClick: function () {
					window.open("https://support.frappe.io/help", "_blank");
				},
			},
			{
				icon: "log-out",
				label: "Logout",
				onClick: function () {
					frappe.app.logout();
				},
			},
		];
		if (this.desktop_menu_items && this.desktop_menu_items.length)
			menu_items = [...menu_items, ...this.desktop_menu_items];
		frappe.ui.create_menu({
			parent: $(".desktop-avatar"),
			menu_items: menu_items,
			// If it's RTL, we want it to open on the right (false);
			// if it's LTR, we want it to open on the left (true).
			open_on_left: !frappe.utils.is_rtl(),
		});
	}
	add_menu_item(item) {
		if (this.desktop_menu_items && this.desktop_menu_items.find((i) => i.label === item.label))
			return;
		this.desktop_menu_items.push(item);
	}
	setup_navbar() {
		$(".sticky-top > .navbar").hide();
	}
	setup_awesomebar() {
		if (!frappe.is_mobile()) {
			$(".search-widget-shortcut").html("Ctrl+K");
			if (frappe.utils.is_mac()) {
				$(".search-widget-shortcut").html("⌘K");
			}
		}
		if (this.awesomebar_setup) return;
		this.awesomebar_setup = true;

		if (frappe.boot.desk_settings.search_bar) {
			let awesome_bar = new frappe.search.AwesomeBar();
			awesome_bar.setup(".search-widget-wrapper #search-widget-button");

			frappe.ui.keys.add_shortcut({
				shortcut: "ctrl+k",
				action: function (e) {
					$(".search-widget-wrapper #search-widget-button").click();
					e.preventDefault();
					return false;
				},
				description: __("Toggle Awesomebar"),
				ignore_inputs: true,
			});
		}
	}
	handle_route_change() {
		const me = this;
		frappe.router.on("change", function () {
			if (frappe.get_route()[0] == "desktop" || frappe.get_route()[0] == "") {
				me.setup_navbar();
			} else {
				$(".navbar").show();
			}
		});
	}
}
