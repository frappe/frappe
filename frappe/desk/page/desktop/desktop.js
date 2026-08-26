// avatar menu items are sorted by `order` (lower first); anything added via
// `add_menu_item()` without one lands after the built-ins but before Logout.
const DEFAULT_MENU_ITEM_ORDER = 50;

frappe.pages["desktop"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Desktop",
		single_column: true,
		hide_sidebar: true,
		hide_workspace_dock: true,
	});

	// Desktop Settings -> Desktop Page picks which grid renders here. `Desktop Icons` is the
	// arrangeable icon grid; it's ~1200 lines in its own bundle (Page.load_assets only serves
	// one <page_name>.js), so load it lazily. Construct and update inside the callback --
	// on_page_show fires before this resolves on first load, so it can't do the initial render.
	if (frappe.boot.desktop_page === "Desktop Icons") {
		frappe.require("desktop_icons.bundle.js").then(() => {
			frappe.pages["desktop"].desktop_page = new frappe.ui.DesktopIconsPage(page);
			frappe.pages["desktop"].desktop_page.update();
		});
		return;
	}

	frappe.pages["desktop"].desktop_page = new DesktopPage(page);
};

frappe.pages["desktop"].on_page_show = function (wrapper) {
	// optional-chained: the lazy Desktop Icons bundle may not have resolved yet
	frappe.pages["desktop"].desktop_page?.update();
};

class DesktopPage {
	constructor(page) {
		this.page = page;
		this.desktop_menu_items = [];
		// Set up the awesomebar + Ctrl+K shortcut only once for the lifetime of the
		// desktop page. `make()` re-renders on every `on_page_show`, but the click
		// handler is delegated on `document` and the search modal is reused, so
		// re-running setup would stack another modal + handler and open duplicate
		// dialogs on Ctrl+K. Keep this flag out of `make()` so it survives navigation.
		this.awesomebar_setup = false;
	}
	update() {
		this.make();
	}
	make() {
		this.page.page_head.hide();
		$(this.page.body).empty();
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
		// Order by the hook's `sequence_id` (lower first); Framework declares 1000 so it
		// always trails. Ties keep installed-apps order since sort() is stable.
		// The destination is the landing ladder: the route the app declares, then its first
		// visible rail entry, then its first navigable module (see app_landing_route).
		//
		// An app that resolves to none of the three **keeps its icon**. It used to be filtered
		// out, which was survivable while every app's rail was every module it owned; now that a
		// rail is exactly the record an app ships, a dock-less app would have had no rail *and*
		// no icon, and therefore no way in at all. The icon leads to the desk's own root, which
		// is somewhere rather than nowhere.
		const apps = (frappe.boot.app_data || [])
			.filter((app) => app.on_apps_screen)
			.map((app) => ({
				...app,
				route: frappe.app.sidebar?.app_landing_route(app) || app.app_route || "/desk",
			}))
			.sort((a, b) => (a.sequence_id ?? 100) - (b.sequence_id ?? 100));

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
			this.add_icon($grid, icon_data, app.route);
		});

		$('[data-toggle="tooltip"]').tooltip({ placement: "bottom" });
	}
	add_icon($grid, icon_data, route) {
		const $icon = $(frappe.render_template("desktop_icon", { icon: icon_data }));
		if (route.startsWith("http")) {
			$icon.attr("target", "_blank");
		}
		$icon.attr("href", route);
		$grid.append($icon);
	}
	setup() {
		$(document).trigger("desktop_screen", { desktop: this });
		this.setup_avatar();
		this.setup_notifications();
		this.setup_cloud_settings();
		this.setup_navbar();
		this.setup_awesomebar();
		this.handle_route_change();
	}

	setup_cloud_settings() {
		const $button = $(".desktop-cloud-settings");
		const settings = frappe.boot.cloud_settings;
		// The bundle is hosted by pilot; without its URL there's nothing to open.
		if (!settings?.enabled || !settings.bundle?.js) {
			$button.addClass("hidden");
			return;
		}

		$button.removeClass("hidden");

		// Warm the cache on hover so the first click feels instant.
		$button.off("mouseenter.cloud-settings").on("mouseenter.cloud-settings", () => {
			this.prefetch_cloud_settings_bundle(settings.bundle);
		});

		$button.off("click.cloud-settings").on("click.cloud-settings", () => {
			this.open_cloud_settings(settings);
		});
	}

	prefetch_cloud_settings_bundle(bundle) {
		if (this._cloud_settings_prefetched) return;
		this._cloud_settings_prefetched = true;
		if (!bundle.js) return;
		const link = document.createElement("link");
		link.rel = "prefetch";
		link.href = bundle.js;
		document.head.appendChild(link);
	}

	async open_cloud_settings(settings) {
		try {
			await this.load_cloud_settings_bundle(settings.bundle);
		} catch (error) {
			// Pilot may be unreachable or the origin blocked; let the user retry.
			console.error("Cloud settings bundle failed to load", error); // eslint-disable-line no-console
			frappe.show_alert({
				message: __("Couldn't open Cloud settings. Please try again."),
				indicator: "red",
			});
			return;
		}
		// A 200 that never registers show() must not stick: clear the promise and
		// bust the URL so the next click cannot reuse the API-less HTTP response.
		if (typeof frappe.cloudSettings?.show !== "function") {
			this.invalidate_cloud_settings_bundle();
			frappe.show_alert({
				message: __("Couldn't open Cloud settings. Please try again."),
				indicator: "red",
			});
			return;
		}
		frappe.cloudSettings.show(settings);
	}

	invalidate_cloud_settings_bundle() {
		this._cloud_settings_loaded = null;
		this._cloud_settings_cache_bust = Date.now();
		// Drop any partial global left by an API-less evaluation so a retry can
		// re-register cleanly.
		delete frappe.cloudSettings;
		document
			.querySelectorAll("script[data-cloud-settings-bundle]")
			.forEach((el) => el.remove());
	}

	cloud_settings_bundle_url(bundle) {
		const base = bundle.js;
		if (!this._cloud_settings_cache_bust) return base;
		const sep = base.includes("?") ? "&" : "?";
		return `${base}${sep}_=${this._cloud_settings_cache_bust}`;
	}

	// Load pilot's cross-origin bundle once. It's a classic-script IIFE, so no CORS
	// is involved, and it carries its own styles (the dialog renders in a shadow
	// root), so there is no stylesheet to link. A failed load rejects and clears
	// the cache so a later click can retry.
	load_cloud_settings_bundle(bundle) {
		if (this._cloud_settings_loaded) return this._cloud_settings_loaded;

		const src = this.cloud_settings_bundle_url(bundle);
		this._cloud_settings_loaded = new Promise((resolve, reject) => {
			const script = document.createElement("script");
			script.src = src;
			script.dataset.cloudSettingsBundle = "1";
			script.onload = resolve;
			script.onerror = () => reject(new Error(`Failed to load ${src}`));
			document.head.appendChild(script);
		}).catch((error) => {
			this._cloud_settings_loaded = null;
			throw error;
		});
		return this._cloud_settings_loaded;
	}

	setup_notifications() {
		this.notifications = new frappe.ui.Notifications({
			wrapper: $(".desktop-notifications"),
			popover: true,
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
				order: 10,
			},
			{
				icon: is_dark ? "sun" : "moon",
				label: "Toggle Theme",
				onClick: function () {
					new frappe.ui.ThemeSwitcher().show();
				},
				order: 20,
			},
			{
				icon: "info",
				label: "About",
				onClick: function () {
					return frappe.ui.toolbar.show_about();
				},
				order: 30,
			},
			{
				icon: "life-buoy",
				label: "Frappe Support",
				onClick: function () {
					window.open("https://support.frappe.io/help", "_blank");
				},
				order: 40,
			},
		];
		// sort() is stable, so items sharing an `order` keep the order they were added in.
		menu_items = [...menu_items, ...this.desktop_menu_items].sort(
			(a, b) => (a.order ?? DEFAULT_MENU_ITEM_ORDER) - (b.order ?? DEFAULT_MENU_ITEM_ORDER)
		);
		// Logout is appended after sorting so it stays last whatever `order` apps pass in.
		menu_items.push({
			icon: "log-out",
			label: "Logout",
			onClick: function () {
				frappe.app.logout();
			},
		});
		frappe.ui.create_menu({
			parent: $(".desktop-avatar"),
			menu_items: menu_items,
			// If it's RTL, we want it to open on the right (false);
			// if it's LTR, we want it to open on the left (true).
			open_on_left: !frappe.utils.is_rtl(),
		});
	}
	// `item.order` is optional; lower sorts higher up the menu. Built-ins occupy
	// 10-40, so omitting it drops the item below them (see DEFAULT_MENU_ITEM_ORDER).
	// Logout is always last and can't be displaced.
	add_menu_item(item) {
		if (this.desktop_menu_items.find((i) => i.label === item.label)) return;
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
