import "./sidebar_item";
import "./dock";

// A module's icon. The dock row wins over the Sidebar's `header_icon`, so the header matches the tile.
frappe.get_module_icon = function (module) {
	if (!module) return null;
	const rows = (frappe.boot.app_data || []).flatMap((app) => [
		...((frappe.boot.dock || {})[app.app_name] || []),
		...(app.dock || []),
	]);
	const row = rows.find((r) => r.link_type === "Sidebar" && r.link_to === module && r.icon);
	return row?.icon || frappe.boot.module_sidebars?.[module]?.header_icon || null;
};

// Route prefixes that name an entity of another kind. `dashboard-view` is itself a Page, so it is
// checked before page_info.
const ENTITY_VIEW_ROUTES = {
	"query-report": "Report",
	"dashboard-view": "Dashboard",
};

// Also named by the router, the workspace view and the arrangement editor; it matches
// `workspace.PRIVATE_MODULE` on the server.
frappe.provide("frappe.ui");
frappe.ui.PRIVATE_SHELL = "Private";

// How strongly an item's href claims `path` (0 means not at all). An item also claims the URLs
// under it, a workspace only its own. Matching filters beat length, and a longer href beats a
// shorter one.
function route_claim(raw_href, link_type, path, params) {
	const [href_path, query] = (raw_href || "").split("?");
	const href = strip_trailing_slash(decodeURIComponent(href_path.split("#")[0]));

	// A root href strips to "", which would claim every page.
	if (!href) return 0;

	const exact = path === href;
	const under = path.startsWith(href + "/");
	if (!exact && !(under && link_type !== "Workspace")) return 0;

	let filtered = false;
	if (query) {
		for (const [key, value] of new URLSearchParams(query)) {
			if (String(params[key]) !== String(value)) return 0;
		}
		filtered = true;
	}

	return (filtered ? 1e6 : 0) + href.length * 2 + (exact ? 1 : 0);
}

function strip_trailing_slash(path) {
	return path.replace(/\/$/, "");
}

// Mirrors `linked_entities` in sidebar.py: a Page item with a `route` also links `<page>/<route>`.
function linked_entities(item) {
	if (!item.link_to) return [];
	if (item.link_type === "Page" && item.route) {
		return [item.link_to, `${item.link_to}/${item.route}`];
	}
	return [item.link_to];
}

// Banners an app shows for its own modules (see erpnext's sidebar_banners.js). Each is a function
// returning { module, app, icon, installed: { title, message }, promo: { title, message, link } },
// so its strings are translated when the sidebar renders.
frappe.ui.sidebar_banners = frappe.ui.sidebar_banners || [];

frappe.ui.Sidebar = class Sidebar {
	constructor() {
		if (!frappe.boot.setup_complete) {
			return;
		}
		this.make_dom();
		this.all_sidebar_items = frappe.boot.module_sidebars;
		this.$items = [];
		this.fields_for_dialog = [];
		this.sidebar_items = [];
		this.$items_container = this.wrapper.find(".sidebar-items");
		this.$standard_items_sections = this.wrapper.find(".body-sidebar");
		this.$sidebar = this.wrapper.find(".body-sidebar");
		this.items = [];
		this.cards = [];
		this.setup_events();
		this.standard_items_setup = false;
	}

	load_sidebar_data() {
		try {
			this.add_standard_items();
			this.sidebar_data = frappe.boot.module_sidebars[this.current_module];
			this.sidebar_items = this.sidebar_data.items;
			this.all_sidebar_items = frappe.boot.module_sidebars;
			this.nest_section_items();
		} catch (e) {
			console.log(e);
		}
	}
	// A companion app's rail is its host's (`Dock.mount_on`).
	rail_host_for(app_name) {
		return (frappe.boot.app_rail_host && frappe.boot.app_rail_host[app_name]) || app_name;
	}

	setup_promotional_banners() {
		if (
			frappe.defaults.is_enabled("disable_product_suggestion") ||
			!frappe.user.has_role("System Manager")
		)
			return;

		let module = this.all_sidebar_items?.[this.current_module]?.["module"] || "";
		if (!module) return;

		this.$promotional_banners = this.wrapper.find(".promotional-banners");
		this.$promotional_banners.empty();
		this.promotional_banners = frappe.ui.sidebar_banners
			.map((make_banner) => make_banner())
			.filter((banner) => banner.module === module)
			.map(({ app, installed, promo, icon }) => {
				const installed_app = (frappe.boot.apps_data.apps || []).find(
					(a) => a.name === app
				);
				return installed_app?.route
					? { ...installed, link: installed_app.route, icon, is_internal: true }
					: { ...promo, icon };
			});

		this.render_promotional_banners();
	}

	render_promotional_banners() {
		let me = this;

		if (this.promotional_banners.length === 0) {
			this.$promotional_banners.hide();
			return;
		}

		this.$promotional_banners.show();

		this.promotional_banners.forEach((banner) => {
			const target = banner.is_internal ? "" : ` target="_blank"`;
			let banner_html = $(`
				<a class="promotional-banner px-2"${target} title="${banner.message}">
					<span class="promotional-banner-title">${banner.title}</span>
				</a>
			`);

			// Via .attr(): banner.link can be server-derived, and interpolating it risks
			// injection.
			banner_html.attr("href", banner.link);
			banner_html.prepend(banner.icon);
			me.$promotional_banners.append(banner_html);
		});
	}

	remove_onboarding_wrapper() {
		this.$onboarding.empty();
		this.wrapper.find(".onboarding-sidebar").removeClass("hidden");

		if (!this.sidebar_data?.module_onboarding) {
			this.wrapper.find(".onboarding-sidebar").addClass("hidden");
		}
	}

	setup_onboarding() {
		let me = this;
		this.$onboarding = this.wrapper.find(".user-onboarding");

		if (!this.sidebar_data || !this.sidebar_data.module_onboarding) {
			this.remove_onboarding_wrapper();
			return;
		}

		let module_name = this.sidebar_data.module_onboarding;

		if (this?.onboarding_widget[module_name]) {
			return;
		}

		this.remove_onboarding_wrapper();
		if (module_name && !frappe.is_mobile()) {
			if (
				this?.onboarding_widget[module_name] &&
				this.onboarding_widget[module_name].hide_panel
			) {
				return;
			}

			return frappe
				.call({
					method: "frappe.desk.desktop.get_onboarding_data",
					args: {
						module: module_name,
					},
					type: "GET",
				})
				.then((data) => {
					if (data.message?.length > 0) {
						let onboarding_data = data.message[0];
						me.onboarding_widget = {};
						me.onboarding_widget[module_name] = new frappe.ui.UserOnboarding({
							title: onboarding_data.title,
							steps: onboarding_data.items,
							wrapper: me.$onboarding,
							header_icon: me.sidebar_header.header_icon,
						});
					} else {
						this.wrapper.find(".onboarding-sidebar").addClass("hidden");
					}
				});
		} else {
			this.wrapper.find(".onboarding-sidebar").addClass("hidden");
		}
	}

	nest_section_items() {
		const me = this;
		let currentSection = null;
		const updated_items = [];

		this.sidebar_items.forEach((item) => {
			item.nested_items = [];

			if (item.type === "Section Break") {
				currentSection = item;
				updated_items.push(item);
			} else if (currentSection && item.child) {
				item.parent = currentSection;
				currentSection.nested_items.push(item);
			} else {
				updated_items.push(item);
			}
		});
		this.sidebar_items = updated_items;
	}
	setup(current_module) {
		if (!this.onboarding_widget) {
			this.onboarding_widget = {};
		}

		$(document).trigger("sidebar_setup", { sidebar: this });
		this.current_module = current_module;

		this.load_sidebar_data();
		this.$sidebar.attr("data-title", this.current_module);
		this.refresh_header();
		this.make_sidebar();
		this.add_sidebar_cards();
		this.setup_promotional_banners();
		this.setup_onboarding();

		this.wrapper.find(".onboarding-sidebar").click(() => {
			if (this.sidebar_data?.module_onboarding) {
				delete this.onboarding_widget[this.sidebar_data.module_onboarding];
			}

			this.setup_onboarding();
		});
	}
	add_card(card) {
		if (this.cards && this.cards.find((i) => i.title === card.title)) return;
		card.parent = this.wrapper.find(".body-sidebar-cards");
		delete card.styles;
		this.cards.push(card);
	}
	add_sidebar_cards() {
		this.wrapper.find(".body-sidebar-cards").html("");
		this.cards.forEach((card) => {
			let card_obj = new frappe.ui.Card(card);
			card.obj = card_obj;
		});
	}

	setup_events() {
		const me = this;
		frappe.router.on("change", function () {
			frappe.app.sidebar.set_workspace_sidebar();
			// setup() is skipped when the sidebar did not change, so the header is refreshed here.
			frappe.app.sidebar.refresh_header();
			frappe.app.sidebar.refresh_dock();
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+/",
			action: () => me.toggle_width(),
			description: __("Toggle sidebar"),
		});
	}

	// One header for the life of the desk, since its menu is bound to the element it was given.
	refresh_header() {
		if (!this.current_module) return;

		if (this.sidebar_header) {
			this.sidebar_header.refresh();
		} else {
			this.sidebar_header = new frappe.ui.SidebarHeader(this);
		}
	}

	// The app that owns the sidebar on screen, read from the sidebar's own `app` rather than the
	// route.
	get_sidebar_app() {
		if (!this.current_module) return null;
		const sidebar = frappe.boot.module_sidebars[this.current_module];
		const app_name = sidebar && sidebar.app;
		return app_name
			? frappe.boot.app_data.find((a) => a.app_name === this.rail_host_for(app_name))
			: null;
	}

	// The app a shell belongs to, by name, or null for a shell in no app.
	app_for_sidebar(shell) {
		const sidebar = shell && frappe.boot.module_sidebars?.[shell];
		const app_name = sidebar && sidebar.app;
		return app_name ? this.rail_host_for(app_name) : null;
	}

	// Whether moving to `entity_shell` leaves the app `shell` belongs to. The shell on screen does
	// not survive that.
	crosses_app(shell, entity_shell) {
		if (!entity_shell || entity_shell === shell) return false;
		const here = this.app_for_sidebar(shell);
		const there = this.app_for_sidebar(entity_shell);
		return !!here && !!there && here !== there;
	}

	// The real Module Def behind the shell on screen, which is named after its sidebar.
	current_module_def() {
		if (!this.current_module) return null;
		const sidebar = frappe.boot.module_sidebars[this.current_module];
		return (sidebar && sidebar.module) || this.current_module;
	}

	// Whether there is a rail to draw. An app with no permitted entries gets none.
	dock_enabled() {
		return this.collect_dock_entries(this.get_sidebar_app()).length > 0;
	}

	refresh_dock() {
		if (!this.dock) {
			this.dock = new frappe.ui.Dock(this);
		}
		this.dock.refresh();
	}

	refresh() {
		this.apply_page_visibility();
		if (!this.page_allows_sidebar() && !this.page_allows_dock()) return;
		// Again, now that the routed doctype's meta has loaded.
		this.set_workspace_sidebar();
		this.refresh_header();
		this.refresh_dock();
	}

	// Both shells start hidden and are shown only once the page on screen allows them.

	current_page() {
		return frappe.container && frappe.container.page && frappe.container.page.page;
	}

	// Below md the panel is a drawer the navbar opens, so there `hide_sidebar` only closes it.
	page_allows_sidebar() {
		const page = this.current_page();
		if (!page) return false;
		return !page.hide_sidebar || this.panel_can_close();
	}

	// Only a drawer (below md) closes; on a desktop the panel folds instead.
	panel_can_close() {
		return frappe.is_mobile();
	}

	page_allows_dock() {
		const page = this.current_page();
		return !!page && !page.hide_dock;
	}

	// The only place that turns either shell on.
	apply_page_visibility() {
		if (!this.wrapper) return;
		const page = this.current_page();

		const allowed = this.page_allows_sidebar();
		// A drawer stays in the document for the navbar, so a page that hides the sidebar closes
		// it instead.
		if (allowed && page && page.hide_sidebar && this.sidebar_expanded) this.close();

		this.wrapper.toggle(allowed);
		this.refresh_dock();
	}

	toggle(hide) {
		if (!this.wrapper) return;
		this.wrapper.toggle(!hide);
		this.refresh_dock();
	}
	make_dom() {
		this.load_expanded_state();
		const hidden = !this.sidebar_expanded && this.hides_when_collapsed();
		this.wrapper = $(
			frappe.render_template("sidebar", {
				expanded: this.sidebar_expanded || hidden,
				avatar: frappe.avatar(frappe.session.user, "avatar-medium"),
				navbar_settings: frappe.boot.navbar_settings,
			})
		)
			.toggleClass("sidebar-hidden", hidden)
			// Hidden until a page allows it, so a page that hides the sidebar never flashes it.
			.hide()
			.prependTo("body");
		this.$sidebar = this.wrapper.find(".sidebar-items");

		this.wrapper.find(".sidebar-edge").on("click", () => this.toggle_width());

		this.wrapper.find(".overlay").on("click", () => {
			this.close();
		});
		this.wrapper.find(".sidebar-collapse-arrow").on("click", () => this.toggle_width());
		// A drawer covers the page it just opened, so close it. Rows that only toggle a group have
		// no href.
		this.wrapper.on("click", ".body-sidebar a.item-anchor[href]", () => {
			if (this.panel_can_close()) this.close();
		});
		this.setup_click_away();
		this.setup_user_menu();
	}

	setup_user_menu() {
		this.create_user_menu({
			parent: this.wrapper.find(".dropdown-navbar-user"),
			button: this.wrapper.find(".sidebar-user-button"),
		});
	}

	// The user menu, shared by the sidebar's user button and the dock's avatar.
	create_user_menu({ parent, button, side = "top", align = "start" }) {
		const $btn = button;

		new frappe.ui.Dropdown({
			trigger: parent,
			side,
			align,
			options: this.user_menu_options(),
			on_open: () => $btn.addClass("user-menu-active"),
			on_close: () => $btn.removeClass("user-menu-active"),
		});
	}

	// Also drawn as rows by the phone tab bar's You sheet (mobile_nav.js).
	user_menu_options() {
		const me = this;
		return [
			{
				group: "",
				options: [
					{
						name: "my-space",
						label: __("My Space"),
						icon: "user",
						href: "/desk/private",
						condition: () => !!frappe.boot.desk_settings.show_my_space,
					},
					{
						name: "settings",
						label: __("Settings"),
						icon: "settings",
						onclick: function () {
							// Not in the desk bundle, so it is loaded on click.
							frappe
								.require("user_settings_dialog.bundle.js")
								.then(() => frappe.ui.show_user_settings("profile"))
								.catch((e) => {
									console.error(
										"Sidebar: failed to load user_settings_dialog.bundle.js",
										e
									);
									frappe.ui.toast({
										message: __(
											"Could not open Settings. Please refresh the page."
										),
										type: "error",
									});
								});
						},
					},
					{
						name: "workspace-selector",
						label: __("Manage Dock"),
						icon: "monitor",
						// A module in no app has no dock to arrange.
						condition: () => !!me.get_sidebar_app(),
						onclick: function () {
							// Not in the desk bundle, so it is loaded on click.
							frappe
								.require("arrangement_editor.bundle.js")
								.then(() => new frappe.ui.DockManager())
								.catch((e) => {
									console.error(
										"Sidebar: failed to load arrangement_editor.bundle.js",
										e
									);
									frappe.ui.toast({
										message: __(
											"Could not open the dock manager. Please refresh the page."
										),
										type: "error",
									});
								});
						},
					},
					{
						name: "reload",
						label: __("Reload"),
						icon: "rotate-ccw",
						onclick: function () {
							frappe.ui.toolbar.clear_cache();
						},
					},
				],
			},
			{
				group: "",
				options: [
					{
						name: "logout",
						label: __("Logout"),
						icon: "log-out",
						onclick: function () {
							frappe.app.logout();
						},
					},
				],
			},
		];
	}

	highlight_active_item() {
		if (this.find_active_item()) {
			this.active_item.addClass("active-sidebar");
			this.expand_parent_section();
		}
	}

	expand_parent_section() {
		if (!this.active_item) return;
		let active_section;
		$(".section-item").each((index, element) => {
			if (element.contains(this.active_item.get(0))) {
				active_section = element.dataset.id;
			}
		});

		if (active_section) {
			let section = this.get_item(active_section);
			if (section) {
				if (this.sidebar_expanded && section.collapsed) {
					section.open();
				}
			}
		}
	}

	get_item(name) {
		for (let item of this.items) {
			if (item.item.label === name) {
				return item;
			}
		}
	}

	// Sets `active_item` to the item with the strongest `route_claim` on the current URL.
	find_active_item() {
		const path = strip_trailing_slash(decodeURIComponent(window.location.pathname));
		const params = Object.assign(
			{},
			Object.fromEntries(new URLSearchParams(window.location.search)),
			frappe.route_options || {}
		);

		let best = null;
		let best_claim = 0;
		$(".item-anchor[href]").each(function () {
			const claim = route_claim(
				this.getAttribute("href"),
				this.dataset.linkType,
				path,
				params
			);
			if (claim > best_claim) {
				best = $(this).parent();
				best_claim = claim;
			}
		});

		// Cleared either way, so an item never stays lit on a page it does not list.
		if (this.active_item) this.active_item.removeClass("active-sidebar");
		this.active_item = best;
		return !!best;
	}

	restore_expanded_state() {
		this.load_expanded_state();
		if (this.sidebar_items.length === 0) {
			this.sidebar_expanded = true;
		}

		this.apply_expanded_state();
	}

	// A drawer starts shut; on a desktop the viewer's last choice is kept in this browser.
	load_expanded_state() {
		this.sidebar_expanded = !this.panel_can_close() && !this.saved_collapsed_state();
	}

	// Storage can be missing or refuse, and then the panel opens whole.
	saved_collapsed_state() {
		try {
			return localStorage.getItem("desk-sidebar-collapsed") === "1";
		} catch {
			return false;
		}
	}

	save_collapsed_state(collapsed) {
		if (this.panel_can_close()) return;
		try {
			localStorage.setItem("desk-sidebar-collapsed", collapsed ? "1" : "0");
		} catch {
			// nothing to keep it in; it lasts until the next reload
		}
	}

	// The items list, not a lookup inside the wrapper: the phone's navigation sheet borrows it.
	empty() {
		this.$items_container.html("");
	}
	make_sidebar() {
		this.empty();
		this.create_sidebar(this.sidebar_items);

		// Scroll sidebar to selected page if it is not in viewport.
		this.wrapper.find(".selected").length &&
			!frappe.dom.is_element_in_viewport(this.wrapper.find(".selected")) &&
			this.wrapper.find(".selected")[0].scrollIntoView();

		this.highlight_active_item();
		this.restore_expanded_state();
	}
	create_sidebar(items) {
		this.empty();
		if (items && items.length > 0) {
			items.forEach((w) => {
				this.add_item(this.$items_container, w);
			});
		} else {
			let no_items_message = $(
				"<div class='flex' style='padding: 30px'> No Sidebar Items </div>"
			);
			this.$items_container.append(no_items_message);
		}
	}
	// Search, notifications and background tasks, as rows in a band under the header.
	add_standard_items(items) {
		if (this.standard_items_setup) return;
		this.standard_items = [];
		this.standard_items.push({
			label: __("Search"),
			icon: "search",
			standard: true,
			type: "Button",
			// page.js opens the search modal from this class.
			class: "navbar-modal-search-mobile",
			condition: () => !!frappe.boot.desk_settings.search_bar,
		});
		this.standard_items.push({
			label: __("Notification"),
			icon: "bell",
			standard: true,
			type: "Button",
			class: "sidebar-notification hidden",
			suffix: "<span class='notification-count es-badge hidden' data-variant='ghost' aria-live='polite'></span>",
			onClick: () => frappe.ui.sidebar_panels.toggle("notifications"),
		});
		this.standard_items.push({
			label: __("Background Tasks"),
			icon: "server",
			standard: true,
			type: "Button",
			class: "sidebar-background-tasks hidden",
			onClick: () => frappe.ui.sidebar_panels.toggle("background-tasks"),
		});
		this.$standard_items_band = this.wrapper.find(".standard-items-band");
		this.standard_items.forEach((w) => {
			if (w.condition && !w.condition()) return;
			this.add_item(this.$standard_items_band, w);
		});
		this.setup_notifications();
		this.setup_background_tasks();
		this.standard_items_setup = true;
	}
	setup_notifications() {
		if (frappe.boot.desk_settings.notifications && frappe.session.user !== "Guest") {
			this.notifications = new frappe.ui.Notifications();
		}
	}
	setup_background_tasks() {
		if (frappe.session.user !== "Guest") {
			this.background_tasks = new frappe.ui.BackgroundTasks();
		}
	}
	add_item(container, item) {
		this.items.push(
			this.make_sidebar_item({
				container: container,
				item: item,
			})
		);
	}
	make_sidebar_item(opts) {
		let class_name = `Type${frappe.utils.to_title_case(opts.item.type).replace(/ /g, "")}`;

		return new frappe.ui.sidebar_item[class_name](opts);
	}
	update_item(item, index) {}

	remove_item(item, index) {}

	// Close the drawer on a click anywhere but the sidebar, the dock or the page's own toggle.
	setup_click_away() {
		$(document)
			// Rebuilt on some navigations, so drop the old handler instead of stacking another.
			.off(".sidebar-click-away")
			.on("click.sidebar-click-away", (e) => {
				if (!this.sidebar_expanded || !this.panel_can_close()) return;
				// Panels mount beside the sidebar but still belong to it.
				if (
					$(e.target).closest(
						".body-sidebar, .dock, .sidebar-toggle-btn, .sidebar-panel, .sidebar-collapse-arrow"
					).length
				)
					return;
				this.close();
			});
	}

	toggle_width() {
		if (!this.sidebar_expanded) {
			this.open();
		} else {
			this.close();
		}
	}

	// Beside a pinned dock a collapsed sidebar hides instead of folding to the rail, so CSS alone
	// slides it shut.
	hides_when_collapsed() {
		if (frappe.is_mobile()) return false;
		// Until the dock knows the page, go by the saved preference, or a reload draws the rail
		// first.
		return this.dock?.resolved
			? this.dock.is_pinned
			: frappe.boot.desk_settings?.dock_mode !== "Floating";
	}

	// Redraws a collapsed sidebar whose form no longer fits. Nobody collapsed anything, so it does
	// not animate.
	refit_collapsed_sidebar() {
		if (!this.wrapper || this.sidebar_expanded) return;
		if (this.hides_when_collapsed() === this.wrapper.hasClass("sidebar-hidden")) return;

		this.wrapper.addClass("no-transition");
		this.apply_expanded_state();
		this.wrapper[0].offsetWidth; // apply the new width before transitions come back
		this.wrapper.removeClass("no-transition");
	}

	apply_expanded_state() {
		const hidden = !this.sidebar_expanded && this.hides_when_collapsed();
		const rail = !this.sidebar_expanded && !hidden;
		this.wrapper.toggleClass("sidebar-hidden", hidden);
		this.wrapper.find(".body-sidebar").prop("inert", hidden);

		if (!rail) {
			this.wrapper.addClass("expanded");
			this.wrapper.find(".avatar-name-email").show();
			this.wrapper.find(".onboarding-sidebar span").show();
			this.wrapper.find(".promotional-banner-title").show();
		} else {
			this.wrapper.removeClass("expanded");
			this.wrapper.find(".avatar-name-email").hide();
			this.wrapper.find(".onboarding-sidebar span").hide();
			this.wrapper.find(".promotional-banner-title").hide();
		}

		this.sidebar_header?.toggle_width(!rail);
		this.label_rail_rows();
		$("body").toggleClass("sidebar-collapsed", !this.sidebar_expanded);
		$(document).trigger("sidebar-expand", {
			sidebar_expand: !rail,
		});
	}

	// In the rail, each row's label becomes its tooltip and accessible name.
	label_rail_rows() {
		const collapsed = !this.wrapper.hasClass("expanded");
		const arrow = this.sidebar_expanded ? __("Collapse sidebar") : __("Expand sidebar");
		this.wrapper.find(".sidebar-collapse-arrow").attr({ title: arrow, "aria-label": arrow });

		this.wrapper.find(".body-sidebar .item-anchor").each((_, anchor) => {
			const label = $(anchor).find(".sidebar-item-label").first().text().trim();
			if (collapsed && label) {
				anchor.setAttribute("title", label);
				anchor.setAttribute("aria-label", label);
			} else {
				anchor.removeAttribute("title");
				anchor.removeAttribute("aria-label");
			}
		});
	}

	close() {
		this.sidebar_expanded = false;
		this.save_collapsed_state(true);

		this.apply_expanded_state();
		if (frappe.is_mobile()) frappe.app.sidebar.prevent_scroll();
	}
	open() {
		this.sidebar_expanded = true;
		this.save_collapsed_state(false);
		this.apply_expanded_state();
		this.highlight_active_item();
	}

	set_height() {
		$(".body-sidebar").css("height", window.innerHeight + "px");
		$(".overlay").css("height", window.innerHeight + "px");
		document.body.style.overflow = "hidden";
	}

	prevent_scroll() {
		let main_section = $(".main-section");
		if (this.sidebar_expanded) {
			main_section.css("overflow", "hidden");
		} else {
			main_section.css("overflow", "");
		}
	}

	// Pick the sidebar for the route (see shell_for_route). highlight_active_item lights the row.
	set_workspace_sidebar() {
		try {
			const route = frappe.get_route();
			const target = this.shell_for_current_route(route);

			if (target && target !== this.current_module) this.select_shell(target);
		} catch (e) {
			console.error(e);
		}

		this.highlight_active_item();
	}

	shell_for_current_route(route) {
		// `/desk` alone names nothing, so the user's default shell answers.
		if (!route.length) return this.default_shell();

		// A route the server's map does not know keeps the sidebar on screen.
		return this.shell_for_route(route) || this.current_module || this.default_shell();
	}

	// Worked out on the server (`home_shell` in sidebar.py).
	default_shell() {
		return frappe.boot.home_shell || Object.keys(frappe.boot.module_sidebars || {})[0] || null;
	}

	// The shell the URL names, if it can show this route. Otherwise the URL is corrected.
	shell_from_url(route) {
		const shell = frappe.router.current_shell;
		if (!shell) return null;

		return this.shell_can_show(shell, route) ? shell : null;
	}

	// A shell can show a route if it lists the entity, or belongs to the same app as the entity's
	// own shell. `listed_only` drops the second half.
	shell_can_show(shell, route, { listed_only = false } = {}) {
		if (!shell || !frappe.boot.module_sidebars?.[shell]) return false;

		const entity = this.entity_from_route(route);
		if (!entity) return false;

		const kind = this.link_type_from_route(route);
		if (this.get_modules_linking(entity, kind).includes(shell)) return true;
		if (listed_only) return false;

		const canonical = this.canonical_shell_for(route, entity);
		return !!canonical && !this.crosses_app(shell, canonical);
	}

	// The shell a URL for this route should name: the URL's own if it can show the route, then the
	// one on screen, then the server's map.
	shell_for_route(route) {
		// A private page's shell is its owner's, whatever module it is filed under.
		if (route[0] === "Workspaces" && route[1] === "private") {
			const name = route[2];
			const stated = frappe.router.current_shell;
			if (stated && this.shell_lists_workspace(stated, name)) return stated;

			const in_view = this.current_module;
			if (in_view && this.shell_lists_workspace(in_view, name)) return in_view;

			return frappe.boot.module_sidebars?.[frappe.ui.PRIVATE_SHELL]
				? frappe.ui.PRIVATE_SHELL
				: null;
		}

		// A workspace route is answered by the shell that stores it.
		if (route[0] === "Workspaces" && route.length >= 2) {
			return this.module_for_workspace(route[route.length - 1]);
		}

		const stated = this.shell_from_url(route);
		if (stated) return stated;

		// A jump was not made from the shell on screen, so sharing an app is not enough to stay.
		// Nor is a row in the Private shell, which is a shortcut and not where the entity belongs.
		const listed_only = frappe.router.is_jump;
		const on_screen =
			listed_only && this.current_module === frappe.ui.PRIVATE_SHELL
				? null
				: this.current_module;
		if (on_screen && this.shell_can_show(on_screen, route, { listed_only })) return on_screen;

		return this.canonical_shell_for(route);
	}

	// Where an entity opens, from the server's map. Keyed by kind, since names repeat across
	// kinds.
	canonical_shell_for(route, entity = null) {
		entity = entity || this.entity_from_route(route);
		if (!entity) return null;

		return frappe.boot.canonical_shell?.[this.link_type_from_route(route)]?.[entity] || null;
	}

	select_shell(module) {
		if (module && module !== this.current_module) {
			frappe.app.sidebar.setup(module);
		}
	}

	// Switch to a shell and open its landing page.
	open_module(module) {
		let sidebar = frappe.boot.module_sidebars[module];
		if (!sidebar) return;

		this.select_shell(module);
		this.open_landing(module);
	}

	// Open a shell's landing page. A landing outside the desk opens in a new tab with `noopener`.
	// Returns whether the desk navigated.
	open_landing(module, { replace = false } = {}) {
		const route = this.module_landing_route(module);
		if (!route) return false;

		if (!route.startsWith("/desk/")) {
			window.open(route, "_blank", "noopener");
			return false;
		}

		if (replace) frappe.route_flags.replace_route = true;
		frappe.set_route(route);
		return true;
	}

	// Open a workspace by name, in the shell that lists it.
	open_workspace(name) {
		if (!name) return;

		const shell = this.get_modules_linking(name, "Workspace")[0];
		if (shell) this.select_shell(shell);

		const route = frappe.ui.sidebar_item.get_route(
			{ type: "Link", link_type: "Workspace", link_to: name },
			false,
			shell
		);
		if (route) frappe.set_route(route);
	}

	// An app's dock entries, resolved for the rail. A module in no app yields none.
	collect_dock_entries(app) {
		const entries = ((app && app.dock) || [])
			.map((row) => this.dock_entry(row))
			.filter(Boolean);

		return this.apply_dock_arrangement(entries, app).filter(Boolean);
	}

	// Resolve a stored dock row into a label, icon, shell and route. A row that resolves to
	// nothing is dropped.
	dock_entry(row) {
		if (!row) return null;

		const page =
			row.link_type === "Workspace"
				? (frappe.boot.workspaces?.pages || []).find((p) => p.name === row.link_to)
				: null;
		if (row.link_type === "Workspace" && !page) return null;
		if (row.link_type === "URL" && !row.url) return null;

		const module =
			row.link_type === "Sidebar"
				? row.link_to
				: page
				? this.module_for_workspace(page.name) || page.module
				: null;
		const sidebar = module ? frappe.boot.module_sidebars[module] : null;
		if (module && !sidebar) return null;
		if (!row.link_type) return null;

		return {
			link_type: row.link_type || null,
			link_to: row.link_to || null,
			url: row.url || null,
			module,
			// The row's own label and icon win, then what it opens, then its shell.
			label: row.title || page?.title || sidebar?.label || row.link_to || row.url,
			icon: row.icon || page?.icon || frappe.get_module_icon(module),
			page,
		};
	}

	// The server has already merged the app's dock with the site's and the user's layers; only
	// hidden entries are dropped here.
	apply_dock_arrangement(entries, app) {
		const app_name = app && app.app_name;
		const arrangement = (frappe.boot.dock || {})[app_name];
		if (!arrangement) return entries;

		return arrangement.filter((row) => !row.hidden).map((row) => this.dock_entry(row));
	}

	open_dock_entry(entry) {
		if (!entry) return;

		// Select the shell first, so the sidebar is right when the route lands.
		if (entry.module) this.select_shell(entry.module);
		this.open();

		const route = this.dock_entry_route(entry);
		if (route) frappe.set_route(route);
	}

	// Never the label, so relabelling cannot detach a row. Matches `dock_key` on the server.
	dock_entry_key(entry) {
		return ["link_type", "link_to", "url"].map((f) => entry[f] || "").join("|");
	}

	// Where an app's icon leads: its declared route, else its first rail entry, else its first
	// navigable module.
	app_landing_route(app) {
		if (!app) return null;
		if (app.app_route) return app.app_route;

		const [entry] = this.collect_dock_entries(app);
		if (entry) return this.dock_entry_route(entry);

		return this.module_landing_route(this.first_navigable_module(app));
	}

	// One definition, so the icon and the button cannot disagree.
	dock_entry_route(entry) {
		if (!entry) return null;
		if (entry.link_type === "Sidebar") return this.module_landing_route(entry.module);
		return frappe.ui.sidebar_item.get_route(
			{
				type: "Link",
				link_type: entry.link_type,
				link_to: entry.link_to,
				url: entry.url,
			},
			false,
			entry.module
		);
	}

	// The app's navigable modules in order, from the permission-filtered payload.
	navigable_app_modules(app) {
		if (!app) return [];
		const app_name = app.app_name;
		return Object.values(frappe.boot.module_sidebars || {})
			.filter((sidebar) => sidebar.app === app_name)
			.map((sidebar) => sidebar.name);
	}

	first_navigable_module(app) {
		return this.navigable_app_modules(app)[0];
	}

	// A shell's home: the first navigable item in its sidebar.
	module_landing_route(module) {
		const sidebar = frappe.boot.module_sidebars[module];
		if (!sidebar) return null;

		for (const item of sidebar.items || []) {
			const route = frappe.ui.sidebar_item.get_route(item, false, module);
			if (route) return route;
		}
		return null;
	}

	// A workspace row is active only on that workspace, a shell row while its shell shows, a URL
	// row never.
	is_active_entry(entry) {
		if (!entry) return false;
		if (entry.link_type === "URL") return false;
		if (entry.link_type === "Workspace") {
			const route = frappe.get_route();
			return route[0] === "Workspaces" && route[route.length - 1] === entry.link_to;
		}
		return !!entry.module && entry.module === this.current_module;
	}
	// Debug helper: call `frappe.app.sidebar.explain()` from the console.
	explain(route = frappe.get_route()) {
		const info = {
			current_sidebar: this.current_module,
			route,
			shell_in_url: frappe.router.current_shell,
			canonical: this.canonical_shell_for(route),
			resolved: this.shell_for_route(route),
		};
		info.reason = !info.resolved
			? "the route names no entity, so nothing decides a shell"
			: info.resolved === info.shell_in_url
			? `the URL names "${info.shell_in_url}" and it can show this route`
			: info.resolved === this.current_module
			? `the sidebar on screen, "${this.current_module}", can show this route`
			: `nothing held, so the route opens where it belongs: "${info.canonical}"`;

		console.info("[sidebar] why:", info);
		return info;
	}

	// The kind of entity a route names; the inverse of sidebar_item.get_route(). Names repeat
	// across kinds.
	link_type_from_route(route) {
		const view = ENTITY_VIEW_ROUTES[route[0]];
		if (view && route.length > 1) return view;
		if (route[0] && frappe.boot.page_info?.[route[0]]) return "Page";
		return "DocType";
	}

	// Whether `shell`'s sidebar links to this workspace.
	shell_lists_workspace(shell, name) {
		if (!shell || !name) return false;

		return this.get_modules_linking(name, "Workspace").includes(shell);
	}

	module_for_workspace(name) {
		if (!name) return null;
		const entry = Object.values(frappe.boot.module_sidebars || {}).find((sidebar) =>
			(sidebar.workspaces || []).includes(name)
		);
		return entry ? entry.name : null;
	}

	entity_from_route(route) {
		// Before page_info: `dashboard-view` is itself a Page and would shadow the dashboard.
		if (ENTITY_VIEW_ROUTES[route[0]] && route.length > 1) return route[1];
		if (route[0] && frappe.boot.page_info?.[route[0]]) return this.page_route_entity(route);
		switch (route.length) {
			case 1:
				return route[0];
			case 3:
				return route[0] === "Workspaces" && route[1] === "private" ? route[2] : route[1];
			case 2:
				// For view routes such as ["List", "Customer"], the entity is the second element.
				return route[1];
			default:
				return route[1];
		}
	}

	// The longest page route the map knows, else the page. A sidebar item can link a page at a
	// route inside it (`linked_entities`), and that route is what decides the shell.
	page_route_entity(route) {
		const page_routes = frappe.boot.canonical_shell?.Page || {};
		for (let length = route.length; length > 1; length--) {
			const entity = route.slice(0, length).join("/");
			if (page_routes[entity]) return entity;
		}
		return route[0];
	}

	// Every module whose sidebar links `link_to`, across apps. Pass `link_type` when a name
	// repeats across kinds.
	get_modules_linking(link_to, link_type = null) {
		let modules = [];
		Object.entries(frappe.boot.module_sidebars || {}).forEach(([module, sidebar]) => {
			const lists = (sidebar.items || []).some(
				(item) =>
					linked_entities(item).includes(link_to) &&
					(!link_type || item.link_type === link_type)
			);
			if (lists) modules.push(module);
		});

		// The owning module goes first.
		const owner = this.module_for_entity(link_to);
		if (owner && modules.includes(owner)) {
			modules = [owner, ...modules.filter((m) => m !== owner)];
		}
		return modules;
	}

	// The module that owns an entity (`bootinfo.entity_module`), or undefined.
	module_for_entity(link_to) {
		const map = frappe.boot.entity_module || {};
		return link_to ? map[link_to] : undefined;
	}
};
