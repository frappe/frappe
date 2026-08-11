import "./sidebar_item";
import "./workspace_dock";
frappe.ui.Sidebar = class Sidebar {
	constructor() {
		if (!frappe.boot.setup_complete) {
			// no sidebar if setup is not complete
			return;
		}
		this.make_dom();
		// states
		this.all_sidebar_items = frappe.boot.module_sidebars;
		this.$items = [];
		this.fields_for_dialog = [];
		this.sidebar_items = [];
		this.$items_container = this.wrapper.find(".sidebar-items");
		// the notification/background-task panels and their trigger buttons live directly on the
		// body sidebar now (there's no wrapper element), so scope both to it
		this.$standard_items_sections = this.wrapper.find(".body-sidebar");
		this.$sidebar = this.wrapper.find(".body-sidebar");
		this.items = [];
		this.cards = [];
		// Route whose cold-entry sidebar was resolved without the doctype's meta, and so still
		// owes a re-resolve against the entity's module. See resolve_initial_sidebar.
		this.pending_cold_entry = null;
		this.setup_events();
		this.standard_items_setup = false;
	}

	prepare() {
		try {
			this.add_standard_items();
			this.sidebar_data = frappe.boot.module_sidebars[this.current_module];
			this.sidebar_items = this.sidebar_data.items;
			this.all_sidebar_items = frappe.boot.module_sidebars;
			this.find_nested_items();
		} catch (e) {
			console.log(e);
		}
	}
	// Resolve the app context from the current route and store it on `frappe.current_app` (plus
	// the header's subtitle/logo). Driven by the router (called from the `route change` handler),
	// so the app is decided by where you navigated to -- not as a side-effect of rendering the
	// header. On a workspace route the app comes from that workspace; on any other route the app
	// context persists (you stay "in" the app whose sidebar is active).
	//
	// The app is read from the workspace's own `app` field (with the sidebar payload's `app` as a
	// backup), rather than by scanning `app_data.workspaces` for a match. That scan misses
	// app-less/custom workspaces on a direct page load, which left `frappe.current_app` stale and
	// made the workspace selector flaky across refreshes.
	set_current_app() {
		if (frappe.boot.app_name_style === "Default") return;

		const route = frappe.get_route();
		if (route[0] === "Workspaces") {
			// a workspace route names its workspace -> the app comes from the workspace itself.
			// `app` is the mount point for every kind of workspace: standard ones inherit it from
			// their module, custom and private ones are mounted explicitly. Only a workspace that
			// has never been mounted resolves to no app.
			const name = route[route.length - 1];
			const workspace = frappe.workspaces[frappe.router.slug(name)];
			const module = this.module_for_workspace(name);
			const sidebar = module && frappe.boot.module_sidebars[module];
			const app_name = (workspace && workspace.app) || (sidebar && sidebar.app);
			const app =
				app_name &&
				frappe.boot.app_data.find((a) => a.app_name === this.rail_host_app(app_name));
			if (app) {
				frappe.current_app = app;
				this.header_subtitle = app.app_title;
				this.app_logo_url = app.app_logo_url;
			} else {
				// unmounted workspace -> clear the app context so the header/selector don't keep
				// showing the app you came from
				frappe.current_app = null;
				this.header_subtitle = frappe.session.user;
			}
			return;
		}

		// any other route -> derive the app from the routed entity (its module's app), the same
		// way the shell/sidebar is resolved. This is what makes a cold reload onto a
		// doctype/report figure out the app. If it can't be resolved (meta not loaded yet), keep
		// the current app context rather than clearing it.
		const app_name = this.app_from_route(this.entity_from_route(route));
		const app =
			app_name &&
			frappe.boot.app_data.find((a) => a.app_name === this.rail_host_app(app_name));
		if (app) {
			frappe.current_app = app;
			this.header_subtitle = app.app_title;
			this.app_logo_url = app.app_logo_url;
		}
	}

	// The app a route is heading into: the app that owns the routed doctype, resolved via its
	// module (meta.module -> module_app). Returns undefined when the entity isn't a doctype or its
	// meta isn't loaded yet, in which case the caller keeps the current app context.
	app_from_route(entity) {
		const meta = entity && frappe.get_meta(entity);
		if (!meta?.module) return undefined;
		return frappe.boot.module_app[frappe.scrub(meta.module)];
	}

	// Resolve a companion app to the host app it's pinned into (via the `add_to_workspace_dock` hook,
	// surfaced as `frappe.boot.app_rail_host`). A companion app has no shell of its own -- its
	// workspaces live inside the host app's rail -- so its app context (dock + header) is the host's.
	// Non-companion apps (and unknown/null names) pass through unchanged.
	rail_host_app(app_name) {
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
		this.promotional_banners = [];
		this.get_crm_banner(module);
		this.get_helpdesk_banner(module);

		this.render_promotional_banners();
	}

	get_crm_banner(module) {
		if (module != "CRM") return;

		const icon =
			$(`<svg width="16" height="16" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M0 11.2C0 7.27963 0 5.31945 0.762954 3.82207C1.43407 2.50493 2.50493 1.43407 3.82207 0.762954C5.31945 0 7.27963 0 11.2 0H16.8C20.7204 0 22.6806 0 24.1779 0.762954C25.4951 1.43407 26.5659 2.50493 27.237 3.82207C28 5.31945 28 7.27963 28 11.2V16.8C28 20.7204 28 22.6806 27.237 24.1779C26.5659 25.4951 25.4951 26.5659 24.1779 27.237C22.6806 28 20.7204 28 16.8 28H11.2C7.27963 28 5.31945 28 3.82207 27.237C2.50493 26.5659 1.43407 25.4951 0.762954 24.1779C0 22.6806 0 20.7204 0 16.8V11.2Z" fill="#DB4EE0"/>
<path d="M5.02441 6.58252V9.09486H20.4627V10.9791L15.0135 16.3806V19.3201H12.9676V16.3806C12.9676 16.3806 9.78529 13.1774 8.62962 12.0469H5.03698L10.0156 17.0087C10.3045 17.2851 10.4678 17.6745 10.4678 18.0765V21.041L17.5259 21.0661V18.0765C17.5259 17.6745 17.6892 17.2851 17.9781 17.0087L22.9751 12.0343V6.58252H5.02441Z" fill="#F1FCFF"/>
</svg>
`);

		// if CRM is installed on the site, link to the route configured via add_to_apps_screen
		const installed_app = (frappe.boot.apps_data.apps || []).find((app) => app.name === "crm");
		if (installed_app && installed_app.route) {
			const title = __("Switch to CRM");
			const message = __("Open Frappe CRM");
			this.promotional_banners.push({
				title,
				message,
				link: installed_app.route,
				icon,
				is_internal: true,
			});
			return;
		}

		const title = __("Switch to Frappe CRM");
		const message = __(
			"Sales without complexity, lock-in and per-user costs. Try it for free!"
		);
		const link =
			"https://frappe.io/crm?utm_source=crm-sidebar&utm_medium=sidebar&utm_campaign=frappe-ad";

		this.promotional_banners.push({ title, message, link, icon });
	}

	get_helpdesk_banner(module) {
		if (module != "Support") return;

		const icon =
			$(`<svg width="16" height="16" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M0 11.2C0 7.27963 0 5.31945 0.762954 3.82207C1.43407 2.50493 2.50493 1.43407 3.82207 0.762954C5.31945 0 7.27963 0 11.2 0H16.8C20.7204 0 22.6806 0 24.1779 0.762954C25.4951 1.43407 26.5659 2.50493 27.237 3.82207C28 5.31945 28 7.27963 28 11.2V16.8C28 20.7204 28 22.6806 27.237 24.1779C26.5659 25.4951 25.4951 26.5659 24.1779 27.237C22.6806 28 20.7204 28 16.8 28H11.2C7.27963 28 5.31945 28 3.82207 27.237C2.50493 26.5659 1.43407 25.4951 0.762954 24.1779C0 22.6806 0 20.7204 0 16.8V11.2Z" fill="#7D42FB"/>
<path d="M22.7237 12.1723V6.65771H5.26367V9.17005H20.2239V11.5568C19.2189 11.8457 18.4904 12.7753 18.4904 13.8681C18.4904 14.961 19.2189 15.878 20.2239 16.1669V18.5536H7.77601V11.9964H5.26367V21.066H22.7362V15.5514L21.2414 14.4836V13.2526L22.7362 12.1849L22.7237 12.1723Z" fill="#EDF7FF"/>
</svg>
`);

		// if Helpdesk is installed on the site, link to the route configured via add_to_apps_screen
		const installed_app = (frappe.boot.apps_data.apps || []).find(
			(app) => app.name === "helpdesk"
		);
		if (installed_app && installed_app.route) {
			const title = __("Switch to Helpdesk");
			const message = __("Open Frappe Helpdesk");
			this.promotional_banners.push({
				title,
				message,
				link: installed_app.route,
				icon,
				is_internal: true,
			});
			return;
		}

		const title = __("Switch to Helpdesk");
		const message = __(
			"Support without complexity, lock-in and per-user costs. Try it for free!"
		);
		const link =
			"https://frappe.io/helpdesk?utm_source=support-sidebar&utm_medium=sidebar&utm_campaign=frappe-ad";

		this.promotional_banners.push({ title, message, link, icon });
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

			// Set href via .attr() rather than template interpolation: banner.link can be
			// a server-derived route (apps_data), so interpolating it risks attribute
			// breakout / javascript: injection.
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
						// send sorted min requirements to increase chance of cache hit
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

	find_nested_items() {
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
		// One keyspace: the exact-case module name. This used to be a pair -- a display-cased
		// `sidebar_title` and a lowercased `workspace_title` -- which is what forced every
		// lookup to pick a casing and got them wrong in opposite directions.
		this.current_module = current_module;

		this.prepare();
		this.$sidebar.attr("data-title", this.current_module);
		this.sidebar_header = new frappe.ui.SidebarHeader(this);
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
			// Resolve the app context from the route first, so `frappe.current_app` is correct
			// before the sidebar/header renders below.
			frappe.app.sidebar.set_current_app();
			if (frappe.route_options && frappe.route_options.sidebar) {
				frappe.app.sidebar.select_module(frappe.route_options.sidebar);
				frappe.route_options = null;
			} else {
				frappe.app.sidebar.set_workspace_sidebar();
			}
			// The sidebar's setup() rebuilds the header, but it's skipped when the sidebar didn't
			// change (e.g. navigating within the same workspace). Refresh the header here so it
			// always reflects the app context resolved above.
			frappe.app.sidebar.refresh_header();
			// Keep the workspace dock in sync with the app context and the active workspace.
			frappe.app.sidebar.refresh_dock();
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+/",
			action: () => me.toggle_width(),
			description: __("Toggle sidebar"),
		});
	}

	// Re-render the header so it reflects the current app context (set by set_current_app) even
	// when the sidebar itself didn't change and setup() -- which builds the header -- wasn't
	// re-run. SidebarHeader.make() removes the existing header first, so this is safe to repeat.
	refresh_header() {
		if (this.current_module) {
			this.sidebar_header = new frappe.ui.SidebarHeader(this);
		}
	}

	// The app that owns the body sidebar currently on screen, as an app_data entry (or null). The
	// dock belongs to whichever app's sidebar is shown, so it follows this rather than the
	// route-derived `frappe.current_app` (the two can diverge -- e.g. a sidebar that curates a
	// cross-app link keeps its own app while the route entity belongs to another). Resolved from the
	// shown workspace's `app` (module sidebars carry it on the boot payload). A workspace that
	// isn't mounted to any app resolves to null.
	get_sidebar_app() {
		if (!this.current_module) return null;
		// A module sidebar carries its app outright, so there is nothing left to reconcile
		// between the workspace's `app` and the payload's.
		const sidebar = frappe.boot.module_sidebars[this.current_module];
		const app_name = sidebar && sidebar.app;
		return app_name
			? frappe.boot.app_data.find((a) => a.app_name === this.rail_host_app(app_name))
			: null;
	}

	// The workspace dock is always on. Apps can no longer opt out; only page-level opt-outs
	// (page_allows_dock, e.g. the desktop/apps screen) still suppress it.
	workspace_dock_enabled() {
		return true;
	}

	// (Re)render the workspace dock to match the current app context. Created lazily on first
	// refresh; the dock stays hidden unless the page allows it (see page_allows_dock).
	refresh_dock() {
		if (!this.workspace_dock) {
			this.workspace_dock = new frappe.ui.WorkspaceDock(this);
		}
		this.workspace_dock.refresh();
	}

	// Fired on page-change / form-refresh. Handles visibility, then runs the
	// same resolver as the router so every navigation event picks a sidebar.
	// set_workspace_sidebar is idempotent, so re-running it here is a no-op
	// unless the route actually warrants a different sidebar.
	refresh() {
		this.apply_page_visibility();
		if (!this.page_allows_sidebar() && !this.page_allows_dock()) return;
		// Re-resolve the app context now that the routed doctype's meta is loaded. On a cold/direct
		// load the router `change` handler ran before the meta was available, so set_current_app()
		// couldn't derive the app (leaving current_app -- and thus the dock -- unresolved). This
		// second pass fills it in. All three are idempotent, so re-running is cheap.
		this.set_current_app();
		this.set_workspace_sidebar();
		this.refresh_header();
		this.refresh_dock();
	}

	// -------------------------------------------------------------------------------------------
	// Visibility. Both shells -- the body sidebar and the workspace dock -- are hidden by default
	// (see make_dom and WorkspaceDock.make) and are only displayed once the page on screen says it
	// allows them. Defaulting to hidden means a page that suppresses them (the desktop/apps screen,
	// the setup wizard) never flashes them first, and a page that has not rendered yet -- so
	// nothing is known about its options -- shows nothing rather than guessing.
	// -------------------------------------------------------------------------------------------

	// The frappe.ui.Page on screen, or undefined before one has rendered.
	current_page() {
		return frappe.container && frappe.container.page && frappe.container.page.page;
	}

	// The body sidebar is displayed unless the page opts out via the standard `hide_sidebar` option.
	page_allows_sidebar() {
		const page = this.current_page();
		return !!page && !page.hide_sidebar;
	}

	// The dock is displayed unless the page opts out with `hide_workspace_dock` -- both that and
	// `hide_sidebar` are standard frappe.ui.Page options, and a page picks either shell on its
	// own: the print format builder keeps the dock while hiding the body sidebar, the
	// desktop/apps screen sets both.
	page_allows_dock() {
		const page = this.current_page();
		return !!page && !page.hide_workspace_dock;
	}

	// Resolve both shells against the current page's options. This is the one place that turns
	// either of them on; it's driven per page by container.toggle_sidebar, so every page change
	// re-evaluates them.
	apply_page_visibility() {
		if (!this.wrapper) return;
		this.wrapper.toggle(this.page_allows_sidebar());
		this.refresh_dock();
	}

	// Explicit override for callers that want the body sidebar hidden/shown irrespective of the
	// page. The dock keeps following the page's options.
	toggle(hide) {
		if (!this.wrapper) return;
		this.wrapper.toggle(!hide);
		this.refresh_dock();
	}
	make_dom() {
		this.load_sidebar_state();
		this.wrapper = $(
			frappe.render_template("sidebar", {
				expanded: this.sidebar_expanded,
				avatar: frappe.avatar(frappe.session.user, "avatar-medium-2"),
				navbar_settings: frappe.boot.navbar_settings,
			})
		)
			// Starts hidden; only a page that allows it turns it on (see apply_page_visibility).
			// Hiding before it enters the document means a page that hides the sidebar never
			// flashes it first.
			.hide()
			.prependTo("body");
		this.$sidebar = this.wrapper.find(".sidebar-items");

		this.wrapper.find(".body-sidebar .sidebar-resize-handle").on("click", () => {
			this.toggle_width();
		});

		this.wrapper.find(".body-sidebar .collapse-sidebar-link").on("click", () => {
			this.toggle_width();
		});

		this.wrapper.find(".overlay").on("click", () => {
			this.close();
		});
		this.setup_user_menu();
	}

	setup_user_menu() {
		this.create_user_menu({
			parent: this.wrapper.find(".dropdown-navbar-user"),
			button: this.wrapper.find(".sidebar-user-button"),
		});
	}

	// Build the user dropdown (profile, workspaces, theme, logout, ...) on a given trigger element.
	// Shared by the sidebar's user button and the workspace dock's avatar so both open the same menu.
	// `button` is the element that gets the active-state class while the menu is open.
	create_user_menu({ parent, button }) {
		const me = this;
		const $btn = button;
		const $container = parent;

		frappe.ui.create_menu({
			parent: $container,
			open_on_top: true,
			menu_items: [
				{
					name: "settings",
					label: __("Settings"),
					icon: "settings",
					onClick: function () {
						// The Settings dialog is lazy (not in the desk bundle); pull it
						// in on click, then open it.
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
					onClick: function () {
						new frappe.ui.DockManager();
					},
				},
				{
					name: "reload",
					label: __("Reload"),
					icon: "rotate-ccw",
					onClick: function () {
						frappe.ui.toolbar.clear_cache();
					},
				},
				...frappe.boot.navbar_settings.settings_dropdown
					.filter((item) => !item.hidden)
					.map((item) => {
						const mapped = {
							name: item.name,
							label: item.item_label,
							icon: item.icon,
							condition: item.condition,
						};
						if (item.item_type === "Route") {
							mapped.url = item.route;
						} else if (item.item_type === "Action") {
							mapped.onClick = () => frappe.utils.eval(item.action);
						}
						return mapped;
					}),
				{ is_divider: true },
				{
					name: "logout",
					label: __("Logout"),
					icon: "log-out",
					onClick: function () {
						frappe.app.logout();
					},
				},
			],
			onShow: function () {
				$btn.addClass("user-menu-active");
			},
			onHide: function () {
				$btn.removeClass("user-menu-active");
			},
			onItemClick: function () {
				$btn.removeClass("user-menu-active");
			},
		});
	}

	set_active_workspace_item() {
		if (this.is_route_in_sidebar()) {
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

	is_route_in_sidebar() {
		let match = false;
		const that = this;
		let exact_match = null;
		let path_match = null;

		const route_params = Object.assign(
			{},
			Object.fromEntries(new URLSearchParams(window.location.search)),
			frappe.route_options || {}
		);

		$(".item-anchor").each(function () {
			const raw = $(this).attr("href") || "";
			const [href_path, href_query] = raw.split("?");
			const href = decodeURIComponent(href_path.split("#")[0]);

			const path = decodeURIComponent(window.location.pathname);

			// ensure no trailing slash mismatch
			const clean_href = href.replace(/\/$/, "");
			const clean_path = path.replace(/\/$/, "");

			const isActive = clean_path === clean_href || clean_path.startsWith(clean_href + "/");
			if (!href || !isActive) return;

			if (href_query) {
				let filter_match = true;
				new URLSearchParams(href_query).forEach((value, key) => {
					if (String(route_params[key]) !== String(value)) filter_match = false;
				});
				if (filter_match) exact_match = $(this).parent();
			} else {
				path_match = $(this).parent();
			}
		});

		const best = exact_match || path_match;
		if (best) {
			match = true;
			if (that.active_item) that.active_item.removeClass("active-sidebar");
			that.active_item = best;
		}
		return match;
	}

	set_sidebar_state() {
		this.load_sidebar_state();
		if (this.sidebar_items.length === 0) {
			this.sidebar_expanded = true;
		}

		this.expand_sidebar();
	}

	load_sidebar_state() {
		this.sidebar_expanded = true;
		if (localStorage.getItem("sidebar-expanded") !== null) {
			this.sidebar_expanded = JSON.parse(localStorage.getItem("sidebar-expanded"));
		}

		if (frappe.is_mobile()) {
			this.sidebar_expanded = false;
		}
	}

	empty() {
		if (this.wrapper.find(".sidebar-items")[0]) {
			this.wrapper.find(".sidebar-items").html("");
		}
	}
	make_sidebar() {
		this.empty();
		this.wrapper.find(".collapse-sidebar-link").removeClass("hidden");
		this.create_sidebar(this.sidebar_items);

		// Scroll sidebar to selected page if it is not in viewport.
		this.wrapper.find(".selected").length &&
			!frappe.dom.is_element_in_viewport(this.wrapper.find(".selected")) &&
			this.wrapper.find(".selected")[0].scrollIntoView();

		this.set_active_workspace_item();
		this.set_sidebar_state();
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
			this.wrapper.find(".sidebar-items").append(no_items_message);
			this.wrapper.find(".collapse-sidebar-link").addClass("hidden");
		}
		this.handle_outside_click();
	}
	add_standard_items(items) {
		if (this.standard_items_setup) return;
		this.standard_items = [];
		this.standard_items.push({
			label: __("Notification"),
			icon: "bell",
			standard: true,
			type: "Button",
			class: "sidebar-notification hidden",
			suffix: "<span class='notification-count hidden' aria-live='polite'></span>",
			onClick: () => {
				const $dropdown = this.wrapper.find(".dropdown-notifications");
				$dropdown.toggleClass("hidden");
				if (!$dropdown.hasClass("hidden")) {
					$dropdown.trigger("show.bs.dropdown");
				}
				this.wrapper.find(".dropdown-background-tasks").addClass("hidden");
				if (frappe.is_mobile()) {
					this.wrapper.removeClass("expanded");
				}
			},
		});
		this.standard_items.push({
			label: __("Background Tasks"),
			icon: "server",
			standard: true,
			type: "Button",
			class: "sidebar-background-tasks hidden",
			onClick: () => {
				this.wrapper.find(".dropdown-notifications").addClass("hidden");
				this.wrapper.find(".dropdown-background-tasks").toggleClass("hidden");
				if (frappe.is_mobile()) {
					this.wrapper.removeClass("expanded");
				}
			},
		});
		this.standard_items.forEach((w) => {
			this.add_item(this.$standard_items_sections, w);
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
			this.background_tasks = new frappe.ui.BackgroundTasks({ full_height: true });
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

	toggle_width() {
		if (!this.sidebar_expanded) {
			this.open();
		} else {
			this.close();
		}
	}

	expand_sidebar() {
		const is_rtl = frappe.utils.is_rtl();
		if (this.sidebar_expanded) {
			this.wrapper.addClass("expanded");
			$('[data-toggle="tooltip"]').tooltip("dispose");
			this.wrapper.find(".avatar-name-email").show();
			this.wrapper.find(".onboarding-sidebar span").show();
			this.wrapper.find(".promotional-banner-title").show();
		} else {
			this.wrapper.removeClass("expanded");
			$('[data-toggle="tooltip"]').tooltip({
				boundary: "window",
				container: "body",
				trigger: "hover",
			});
			this.wrapper.find(".avatar-name-email").hide();
			this.wrapper.find(".onboarding-sidebar span").hide();
			this.wrapper.find(".promotional-banner-title").hide();
		}

		localStorage.setItem("sidebar-expanded", this.sidebar_expanded);
		const chevron_icon = this.sidebar_expanded
			? is_rtl
				? "chevron-right"
				: "chevron-left"
			: is_rtl
			? "chevron-left"
			: "chevron-right";
		this.wrapper
			.find(".body-sidebar .collapse-sidebar-link")
			.find("use")
			.attr("href", `#icon-${chevron_icon}`);
		this.sidebar_header.toggle_width(this.sidebar_expanded);
		// while collapsed the body sidebar is hidden and only the workspace dock (rail) shows; this
		// gates the rail's edge handle that reopens the sidebar (see workspace_dock.scss)
		$("body").toggleClass("sidebar-collapsed", !this.sidebar_expanded);
		$(document).trigger("sidebar-expand", {
			sidebar_expand: this.sidebar_expanded,
		});
	}

	close() {
		this.sidebar_expanded = false;

		this.expand_sidebar();
		if (frappe.is_mobile()) frappe.app.sidebar.prevent_scroll();
	}
	open() {
		this.sidebar_expanded = true;
		this.expand_sidebar();
		this.set_active_workspace_item();
	}

	set_height() {
		$(".body-sidebar").css("height", window.innerHeight + "px");
		$(".overlay").css("height", window.innerHeight + "px");
		document.body.style.overflow = "hidden";
	}

	handle_outside_click() {
		document.addEventListener("click", (e) => {
			if (this.sidebar_header.drop_down_expanded) {
				if (!e.composedPath().includes(this.sidebar_header.app_switcher_dropdown)) {
					this.sidebar_header.toggle_dropdown_menu();
				}
			}
		});
	}

	prevent_scroll() {
		let main_section = $(".main-section");
		if (this.sidebar_expanded) {
			main_section.css("overflow", "hidden");
		} else {
			main_section.css("overflow", "");
		}
	}

	// The sidebar is mostly selection-driven: it's chosen via the header switcher (or a direct
	// workspace route) and then stays put as you navigate. Two things move it automatically:
	//   - navigating to an entity that lives in some module's sidebar but NOT the current one
	//     follows it to the module that owns it. Ownership comes from get_modules_linking() --
	//     the module whose item is flagged default_workspace wins, else the first that contains it.
	//   - navigating to an entity that no sidebar links at all (e.g. a custom/standalone doctype)
	//     falls back to its own module via sidebar_from_module().
	// Resolving from data (not the DOM/location) keeps it independent of route/render timing, and it
	// takes priority over the cold-entry fallback. The active-item highlight stays route-aware via
	// set_active_workspace_item().
	set_workspace_sidebar() {
		try {
			const route = frappe.get_route();

			if (route[0] === "Workspaces" && route.length >= 2) {
				// explicit workspace route -> user picked this workspace; make it the sticky selection
				// a workspace route names a workspace, so map it to its module before selecting
				const name = route[route.length - 1];
				const module = this.module_for_workspace(name);
				if (module) this.select_module(module);
			} else {
				// Find every sidebar that contains the routed entity. While NAVIGATING, ownership
				// resolution does NOT consult the route's app: a sidebar may deliberately curate a
				// cross-app link (e.g. System Settings, owned by `frappe`, linked in the
				// erpnext-owned ERPNext Settings sidebar), and filtering by the doctype's app would
				// drop the very sidebar you're on. If the entity isn't already in the current
				// sidebar, follow it to the one that owns it: get_workspace_sidebars() puts the
				// default_workspace owner first, else the first sidebar that contains it.
				// Cold entry is deliberately NOT app-blind -- there is no "sidebar you're on" to
				// preserve, so resolve_initial_sidebar leads with the entity's module instead.
				const entity = this.entity_from_route(route);
				const candidates = this.get_modules_linking(entity);
				const in_current = candidates.includes(this.current_module);

				if (this.cold_entry_needs_recheck(route, entity)) {
					// The cold entry below ran before this doctype's meta existed and could only
					// guess from the sidebars linking it. The module is readable now, so resolve
					// again and land in the workspace that actually owns the entity.
					this.pending_cold_entry = null;
					const target = this.initial_sidebar(route);
					if (target && target !== this.current_module) {
						frappe.app.sidebar.setup(target);
					}
				} else if (this.current_module && candidates.length && !in_current) {
					this.select_module(candidates[0]);
				} else if (this.current_module && !candidates.length) {
					// the entity isn't linked in any sidebar -> fall back to its module's
					// autogenerated sidebar, so navigating to a custom/standalone doctype lands in
					// its own module shell instead of staying on the current one.
					const module_sidebar = this.sidebar_from_module(entity);
					if (module_sidebar && module_sidebar !== this.current_module) {
						this.select_module(module_sidebar);
					}
				} else if (!this.current_module) {
					// cold entry / deep link -> resolve once. When the routed doctype's meta hasn't
					// loaded yet the answer is provisional; remember the route so the branch above
					// can re-resolve it against the module on the next pass.
					const { sidebar: target, provisional } = this.resolve_initial_sidebar(route);
					this.pending_cold_entry = provisional ? route.join("/") : null;
					if (target) frappe.app.sidebar.setup(target);
				}
			}
		} catch (e) {
			console.error(e);
		}

		this.set_active_workspace_item();
	}

	// Switch to a workspace's sidebar and remember it so the choice survives navigation/reload.
	select_module(module) {
		if (module && module !== this.current_module) {
			frappe.app.sidebar.setup(module);
		}
		if (module) localStorage.setItem("selected_module", module);
	}

	// Route of the first navigable item in a workspace's sidebar (or null if it has none).
	get_first_sidebar_route(module) {
		let sidebar = frappe.boot.module_sidebars[module];
		if (!sidebar) return null;

		for (let item of sidebar.items || []) {
			let route = frappe.ui.sidebar_item.get_route(item);
			if (route) return route;
		}
		return null;
	}

	// Switch to a module's sidebar and navigate into it. Shared by the dock, the header
	// switcher and global search.
	//
	// This is where "a module's workspace is its home page" lives: the module opens on its
	// `home_workspace` if it has one, and otherwise on the first navigable item in its sidebar.
	open_module(module) {
		let sidebar = frappe.boot.module_sidebars[module];
		if (!sidebar) return;

		this.select_module(module);

		if (sidebar.home_workspace) {
			frappe.set_route(frappe.router.slug(sidebar.home_workspace));
			return;
		}

		let route = this.get_first_sidebar_route(module);
		if (route) frappe.set_route(route);
	}

	// ---------------------------------------------------------------------------------------------
	// Workspace selector set -- the single source of truth for both the header dropdown and the
	// workspace dock, so the two always offer the same workspaces.
	// ---------------------------------------------------------------------------------------------

	// The ordered set of modules the dock and the header dropdown offer, as module-sidebar
	// payload entries. The dock renders the whole set (highlighting the active one); the
	// dropdown drops the active one since you cannot switch to it.
	//
	// The set is the app's own modules -- `app_data[].modules`, already permission-filtered
	// and in `modules.txt` order -- resolved through `module_sidebars`. A module missing from
	// that payload is one whose every item the user may not see, so it is correctly absent.
	//
	// This replaces the old workspace-shaped set and its module fallback, which only applied
	// to apps shipping zero workspaces. That gate is exactly why the dock listed modules so
	// rarely; now it is the only model.
	//
	// `app` defaults to the route's current app (used by the header dropdown); the dock passes
	// the shown sidebar's app so it lists that app's modules.
	collect_dock_modules(app = frappe.current_app) {
		let modules = ((app && app.modules) || [])
			.map((module) => frappe.boot.module_sidebars[module])
			.filter(Boolean);

		return this.apply_dock_preferences(modules);
	}

	// Apply the user's dock curation (`User.dock_modules`): drop what they hid, and order what
	// they arranged. Curation is one flat cross-app list, so it is applied *within* this app's
	// set rather than replacing it -- as a replacement it would put the same rail on every app.
	// A curation naming none of this app's modules leaves the app's own order alone rather than
	// rendering an empty rail.
	apply_dock_preferences(modules) {
		const preferences = frappe.boot.user_dock_modules || [];
		if (!preferences.length) return modules;

		const hidden = new Set(preferences.filter((p) => p.hidden).map((p) => p.module));
		const order = new Map(preferences.map((p, idx) => [p.module, idx]));

		const visible = modules.filter((m) => !hidden.has(m.module));
		if (!visible.some((m) => order.has(m.module))) return modules;

		// Modules the user never arranged keep their app order and trail the ones they did, so
		// an app adding a module still surfaces it for someone who has already curated.
		return visible.sort(
			(a, b) => (order.get(a.module) ?? Infinity) - (order.get(b.module) ?? Infinity)
		);
	}

	// Where an app's icon leads. `app_route` covers apps that declare one; otherwise land on
	// the first entry of its module dock -- the same place clicking that entry would go.
	app_landing_route(app) {
		if (!app) return null;
		if (app.app_route) return app.app_route;

		const [module] = this.collect_dock_modules(app);
		return module ? this.module_landing_route(module.module) : null;
	}

	// Where a module leads: its home workspace, else the first navigable item in its sidebar --
	// the same rule `open_module` navigates by, as a path rather than a route so it can be an
	// `href`. Shared by the app icons, the standalone module tiles on the desktop and the
	// header's workspace switcher, so the three cannot disagree about where a module opens.
	module_landing_route(module) {
		const sidebar = frappe.boot.module_sidebars[module];
		if (!sidebar) return null;

		return sidebar.home_workspace
			? `/desk/${frappe.router.slug(sidebar.home_workspace)}`
			: this.get_first_sidebar_route(module);
	}

	// Menu items for the header dropdown: every dock module except the active one.
	get_workspace_selector_items() {
		return this.collect_dock_modules()
			.filter((sidebar) => !this.is_active_module(sidebar))
			.map((sidebar) => this.module_to_item(sidebar))
			.filter(Boolean);
	}

	// The module currently shown -- not offered as a switch target, and highlighted on the dock.
	// A direct comparison now that both sides are exact-case module names; this used to go
	// through `router.slug`, a third keyspace.
	is_active_module(sidebar) {
		if (!sidebar) return false;
		return sidebar.module === this.current_module;
	}

	module_to_item(sidebar) {
		if (!sidebar) return null;
		return {
			name: sidebar.module,
			label: sidebar.label || sidebar.module,
			url: this.module_landing_route(sidebar.module),
			icon: sidebar.header_icon,
			onClick: () => this.select_module(sidebar.module),
		};
	}

	initial_sidebar(route) {
		return this.resolve_initial_sidebar(route).sidebar;
	}

	// Pick the sidebar to show on cold entry, returning the choice, why it was made, and whether
	// the answer is provisional (see below).
	// Precedence:
	//   1. an item flagged `default_workspace` names the entity's owning workspace outright — the
	//      one authored signal that beats every heuristic below
	//   2. the last selected sidebar, if it links the entity. Continuity outranks the module: on a
	//      reload or a deep link you stay in the shell you were working in instead of being
	//      relocated to the entity's home module. Gated on the link so it can only hold you
	//      somewhere the entity is actually reachable — an unrelated shell is never kept.
	//   3. the entity's own module — the module's autogenerated sidebar, else the sidebar belonging
	//      to that module. With no prior selection worth honouring, a deep link lands in the shell
	//      the entity actually lives in, rather than in whichever unrelated workspace links it.
	//   4. only then the remaining sidebars that link the entity: the first that contains it. A link
	//      is a weak signal — an entity can be curated into any number of foreign sidebars — so it
	//      decides nothing until the module has had its say.
	//   5. otherwise keep the last selected sidebar (the route belongs to no sidebar at all)
	//   6. the first available sidebar
	// User.default_workspace is intentionally NOT consulted here: it made the sidebar sticky to
	// one workspace regardless of route, which broke the illusion that each entity lives in its
	// own app shell.
	//
	// Only step 3 needs the routed doctype's meta, which is NOT loaded on the first pass of a cold
	// load (the router fires before the page's meta arrives). When the module can't be read yet the
	// results below it are flagged `provisional`: they are the best guess from link data alone, and
	// set_workspace_sidebar re-resolves once the meta lands. Without that second pass a cold entry
	// would permanently keep the step-4 answer and the module would never get a look in. Steps 1-2
	// read boot data only, so they are final on the first pass.
	resolve_initial_sidebar(route) {
		const all = frappe.boot.module_sidebars || {};
		const exists = (name) => (name && all[name] ? name : null);

		const entity = this.entity_from_route(route);
		const persisted = exists(localStorage.getItem("selected_module"));
		// resolved up front (rather than at step 4) because step 2 tests the last selection against it
		const candidates = this.get_modules_linking(entity);

		// 1. the entity is explicitly owned by a workspace
		const owner = exists(this.module_for_entity(entity));
		if (owner) {
			return {
				sidebar: owner,
				reason: `"${entity}" is flagged default_workspace in "${owner}"`,
				provisional: false,
			};
		}

		// 2. the last selected sidebar, when it can actually show the entity
		if (persisted && candidates.includes(persisted)) {
			return {
				sidebar: persisted,
				reason: `last selected sidebar "${persisted}" — route entity "${entity}" is linked in it, so the selection is kept over the entity's module`,
				provisional: false,
			};
		}

		// 3. the entity's module decides, before any remaining link-based match
		const module_sidebar = this.sidebar_from_module(entity);
		if (module_sidebar) {
			return {
				sidebar: module_sidebar,
				reason: `derived from "${entity}"'s module — the shell the entity belongs to`,
				provisional: false,
			};
		}

		// Everything past here is decided without the module, so mark it provisional whenever the
		// module is unreadable — it may just be a meta that hasn't loaded. Being over-eager is free:
		// the caller only acts on the flag once the module actually resolves, which never happens
		// for routes that have no meta to wait for (a workspace, a report).
		const provisional = !!entity && !frappe.get_meta(entity)?.module;

		// 4. the entity is linked in one or more sidebars — the last selected one is not among them,
		//    step 2 would have taken it
		if (candidates.length) {
			return {
				sidebar: candidates[0],
				reason: `route entity "${entity}" has no owning module sidebar; it is linked in: ${candidates.join(
					", "
				)}`,
				provisional,
			};
		}

		// 5. nothing ties the route to a sidebar -> keep the last selection
		if (persisted) {
			return {
				sidebar: persisted,
				reason: `last selected sidebar "${persisted}" — route "${entity}" belongs to no sidebar, so the selection is kept`,
				provisional,
			};
		}

		// 6. first available
		const first = Object.values(all)[0];
		return {
			sidebar: first && first.module,
			reason: `fallback to the first available sidebar (route entity "${entity}" matched none)`,
			provisional,
		};
	}

	// True when a cold entry for `route` was resolved before the routed doctype's meta was
	// available -- so it could not consult the module -- and the module is readable now. This is
	// the trigger for the second resolution pass; see resolve_initial_sidebar.
	cold_entry_needs_recheck(route, entity) {
		return this.pending_cold_entry === route.join("/") && !!this.sidebar_from_module(entity);
	}

	// Debug helper: explain why the current sidebar is shown.
	// Call from the console as `frappe.app.sidebar.explain_sidebar()`.
	explain(route = frappe.get_route()) {
		const { sidebar: resolved, reason } = this.resolve_initial_sidebar(route);
		const current = this.current_module;
		const was_manually_selected = current && resolved && current !== resolved;

		const info = {
			current_sidebar: current,
			route,
			reason: was_manually_selected
				? `shown because it was explicitly selected ("${current}"). On a cold reload it would instead resolve to "${resolved}" — ${reason}`
				: reason,
			resolved_on_reload: resolved,
		};
		console.info("[sidebar] why:", info);
		return info;
	}

	// The module an entity belongs to, or null. Under 1:1 this is a direct hit: the payload is
	// keyed by module name, so an entity's `meta.module` indexes straight into it. The old
	// version had to fall back to scanning every sidebar for one carrying the module, because a
	// module's sidebar could be titled anything (module "Accounts" -> workspace "Accounting").
	// That scan is what 1:1 eliminates.
	sidebar_from_module(entity) {
		const meta = entity && frappe.get_meta(entity);
		if (!meta?.module) return null;
		return frappe.boot.module_sidebars?.[meta.module] ? meta.module : null;
	}

	// The module that owns a workspace, from the module payload's `workspaces` list. A direct
	// workspace route names a workspace, but selection is module-shaped now.
	module_for_workspace(name) {
		if (!name) return null;
		const entry = Object.values(frappe.boot.module_sidebars || {}).find((sidebar) =>
			(sidebar.workspaces || []).includes(name)
		);
		return entry ? entry.module : null;
	}

	entity_from_route(route) {
		if (route[0] && frappe.boot.page_info?.[route[0]]) return route[0];
		switch (route.length) {
			case 1:
				return route[0];
			case 3:
				return route[0] === "Workspaces" && route[1] === "private" ? route[2] : route[1];
			case 2:
				// view-type routes like ["List", "Customer"] or
				// ["query-report", "Balance Sheet"] -> entity is the second element
				return route[1];
			default:
				return route[1];
		}
	}

	// Every module whose sidebar contains `link_to`. App-blind on purpose (see
	// set_workspace_sidebar) so curated cross-app links resolve correctly.
	get_modules_linking(link_to) {
		let modules = [];
		Object.entries(frappe.boot.module_sidebars || {}).forEach(([module, sidebar]) => {
			if ((sidebar.items || []).some((item) => item.link_to === link_to)) {
				modules.push(module);
			}
		});

		// If one of them owns the entity (its item is flagged default_workspace), surface it
		// first so callers taking the top candidate land in the module the entity belongs to.
		const owner = this.module_for_entity(link_to);
		if (owner && modules.includes(owner)) {
			modules = [owner, ...modules.filter((m) => m !== owner)];
		}
		return modules;
	}

	// The module an entity belongs to, or undefined. An entity can appear in several sidebars;
	// the item flagged `default_workspace` marks its owner. Built server-side
	// (`bootinfo.entity_module`) from the permission-filtered payload, so it can only ever name
	// something the user may see.
	module_for_entity(link_to) {
		const map = frappe.boot.entity_module || {};
		return link_to ? map[link_to] : undefined;
	}
};
