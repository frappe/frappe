import "./sidebar_item";
import "./dock";

// The query parameter that carries the shell. Named `sidebar` because that is what the desk
// already read here before anything wrote it.
const SHELL_PARAM = "sidebar";

// Route prefixes that name an entity of another kind rather than being one themselves:
// `/desk/query-report/Balance Sheet` is about the Report, not about "query-report". Both the
// entity and its link type are read from the prefix, which is why they live in one table.
// See link_type_from_route().
//
// `dashboard-view` is itself a Page, so it must be checked BEFORE frappe.boot.page_info or it
// shadows the dashboard it is showing. `query-report` is not a Page and never was.
const ENTITY_VIEW_ROUTES = {
	"query-report": "Report",
	"dashboard-view": "Dashboard",
};

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
		// The notification and background-task panels live directly on the body sidebar (there
		// is no wrapper element), so scope to it.
		this.$standard_items_sections = this.wrapper.find(".body-sidebar");
		this.$sidebar = this.wrapper.find(".body-sidebar");
		this.items = [];
		this.cards = [];
		// Route whose cold-entry sidebar was resolved without the doctype's meta, so it still
		// needs a re-resolve against the entity's module. See resolve_initial_sidebar.
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
	// Resolve a companion app to the host app whose rail it mounts on (`Dock.mount_on`, exposed
	// as `frappe.boot.app_rail_host`). A companion app has no rail of its own, since its entries
	// live on the host's, so its app context is the host's.
	// Non-companion apps, and unknown or null names, pass through unchanged.
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
		// One keyspace: the exact-case module name. This used to be a pair, a display-cased
		// `sidebar_title` and a lowercased `workspace_title`, which forced every lookup to pick
		// a casing and got them wrong in opposite directions.
		this.current_module = current_module;

		this.prepare();
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
			// One path, because the URL's shell is an input to resolution now rather than a
			// short-circuit around it (`shell_from_url`). The branch this replaces called
			// `select_module` and then cleared `frappe.route_options` wholesale, throwing away
			// every other parameter in the URL -- so a link carrying both a shell and list
			// filters arrived with the filters silently gone.
			frappe.app.sidebar.set_workspace_sidebar();
			// The sidebar's setup() rebuilds the header, but it's skipped when the sidebar didn't
			// change (e.g. navigating within the same workspace). Refresh the header here so it
			// always reflects the module resolved above.
			frappe.app.sidebar.refresh_header();
			// Keep the dock in sync with the shown module and the active workspace.
			frappe.app.sidebar.refresh_dock();
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+/",
			action: () => me.toggle_width(),
			description: __("Toggle sidebar"),
		});
	}

	// Point the header at the module currently shown, even when the sidebar did not change and
	// setup() was not re-run.
	//
	// There is one header for the life of the desk, refreshed rather than rebuilt. Its menu is
	// bound to the element it was given, and `frappe.ui.create_menu` registers a document-level
	// listener per call, so building a header per navigation would strand the menu on a detached
	// node and leak a listener on every navigation.
	refresh_header() {
		if (!this.current_module) return;

		if (this.sidebar_header) {
			this.sidebar_header.refresh();
		} else {
			this.sidebar_header = new frappe.ui.SidebarHeader(this);
		}
	}

	// The app that owns the body sidebar on screen, as an app_data entry, or null. This is all
	// that app context means in the desk: it says what supplies the rail's items and nothing
	// else. A module belonging to no app, such as an unplaced or orphaned custom module,
	// resolves to null, which is a valid answer: the rail shows that module's own icon over an
	// empty items region.
	//
	// It is resolved from the shown module's own `app`, which sidebars carry on the boot payload,
	// so it follows the sidebar on screen rather than the route. A sidebar may curate a
	// cross-app link on purpose, and following that link should not change the shell you are in.
	get_sidebar_app() {
		if (!this.current_module) return null;
		// A sidebar carries its own app, so there is nothing to reconcile between the
		// workspace's `app` and the payload's.
		const sidebar = frappe.boot.module_sidebars[this.current_module];
		const app_name = sidebar && sidebar.app;
		return app_name
			? frappe.boot.app_data.find((a) => a.app_name === this.rail_host_app(app_name))
			: null;
	}

	// The module the shell on screen belongs to.
	//
	// `current_module` is a shell identity, the key `frappe.boot.module_sidebars` is built on.
	// The two are the same string unless a sidebar was named something other than its module.
	// Every surface that needs a real `Module Def`, such as a workspace's module or a
	// `Custom Sidebar`, uses this instead of reading the shell directly.
	current_module_def() {
		if (!this.current_module) return null;
		const sidebar = frappe.boot.module_sidebars[this.current_module];
		return (sidebar && sidebar.module) || this.current_module;
	}

	// Whether there is a rail to draw at all.
	//
	// The trigger is zero resolved entries, not a missing record. Having a record is the
	// authoring opt-in; rendering tests the payload. That covers both an app that ships no dock
	// and a user permitted none of a full dock's entries, who would otherwise get an empty rail
	// and no switcher, leaving them no navigation at all.
	//
	// A dock-less app gets no rail rather than an empty stripe. The user button moves back to
	// the sidebar, which is the pre-dock layout and still exists, and the sidebar header carries
	// a switcher instead. The trade-off is that the layout shifts when moving between a docked
	// app and a dock-less one.
	dock_enabled() {
		return this.collect_dock_entries(this.get_sidebar_app()).length > 0;
	}

	// Render or re-render the dock to match the current app context. It is created
	// lazily on first refresh and stays hidden unless the page allows it (see page_allows_dock).
	refresh_dock() {
		if (!this.dock) {
			this.dock = new frappe.ui.Dock(this);
		}
		this.dock.refresh();
	}

	// Fired on page change and form refresh. Handles visibility, then runs the same resolver as
	// the router so every navigation event picks a sidebar. set_workspace_sidebar is idempotent,
	// so re-running it here does nothing unless the route needs a different sidebar.
	refresh() {
		this.apply_page_visibility();
		if (!this.page_allows_sidebar() && !this.page_allows_dock()) return;
		// Re-resolve now that the routed doctype's meta is loaded. On a cold or direct load the
		// router `change` handler ran before the meta was available, so the entity's module could
		// not be derived, and neither could the sidebar, the header or the rail. This second pass
		// fills them in. All three are idempotent, so re-running is cheap.
		this.set_workspace_sidebar();
		this.refresh_header();
		this.refresh_dock();
	}

	// -------------------------------------------------------------------------------------------
	// Visibility. Both shells, the body sidebar and the dock, are hidden by default
	// (see make_dom and Dock.make) and are shown only once the page on screen says it
	// allows them. Defaulting to hidden means a page that suppresses them, such as the desktop
	// or apps screen and the setup wizard, never flashes them first, and a page that has not
	// rendered yet, whose options are unknown, shows nothing rather than guessing.
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

	// The dock is displayed unless the page opts out with `hide_dock`. That and
	// `hide_sidebar` are both standard frappe.ui.Page options, and a page picks either shell on
	// its own: the print format builder keeps the dock while hiding the body sidebar, and the
	// desktop or apps screen sets both.
	page_allows_dock() {
		const page = this.current_page();
		return !!page && !page.hide_dock;
	}

	// Resolve both shells against the current page's options. This is the only place that turns
	// either of them on. container.toggle_sidebar drives it per page, so every page change
	// re-evaluates them.
	apply_page_visibility() {
		if (!this.wrapper) return;
		let allowed = this.page_allows_sidebar();
		this.wrapper.toggle(allowed);
		// A hidden panel cannot be peeking, and it leaves without a mouseleave to say so.
		if (!allowed) this.end_peek();
		this.refresh_dock();
	}

	// Explicit override for callers that want the body sidebar hidden or shown regardless of the
	// page. The dock keeps following the page's options.
	toggle(hide) {
		if (!this.wrapper) return;
		this.wrapper.toggle(!hide);
		if (hide) this.end_peek();
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
			// Hiding it before it enters the document means a page that hides the sidebar never
			// flashes it first.
			.hide()
			.prependTo("body");
		this.$sidebar = this.wrapper.find(".sidebar-items");

		this.wrapper.find(".body-sidebar .sidebar-resize-handle").on("click", () => {
			this.toggle_width();
		});

		this.wrapper.find(".overlay").on("click", () => {
			this.close();
		});
		// Any row that goes somewhere takes the panel down behind it: the panel is an overlay over
		// the page it just navigated, so leaving it up would cover the thing that was asked for.
		// Rows that only toggle a group carry no href and are left alone, since expanding a group
		// is a request to see more of this list rather than to leave it.
		this.wrapper.on("click", ".body-sidebar a.item-anchor[href]", () => this.close());
		this.setup_click_away();
		this.setup_user_menu();
	}

	setup_user_menu() {
		this.create_user_menu({
			parent: this.wrapper.find(".dropdown-navbar-user"),
			button: this.wrapper.find(".sidebar-user-button"),
		});
	}

	// Build the user dropdown (settings, the dock manager, reload, logout) on a trigger
	// element. Shared by the sidebar's user button and the dock's avatar so both open
	// the same menu. What a site adds in Navbar Settings is not here; that hangs off the sidebar
	// header's menu, see SidebarHeader.navbar_items. `button` is the element that gets the
	// active-state class while the menu is open.
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
						// The Settings dialog is not in the desk bundle, so load it on
						// click and then open it.
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
					// The dock holds an app's own modules, so a module in no app has no dock
					// to arrange and its items region is always empty. Offering the picker
					// there would ask the user to curate nothing. This is evaluated on every
					// open, because frappe.ui.menu re-runs conditions in make(), so it tracks
					// the shell you are in rather than the one the menu was built in.
					condition: () => !!me.get_sidebar_app(),
					onClick: function () {
						// The editor is not in the desk bundle, so load it on click and
						// then open the dock's manager.
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
					onClick: function () {
						frappe.ui.toolbar.clear_cache();
					},
				},
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

			// A root or empty href strips to "", and "" prefix-matches every route, so such an
			// item was highlighted on every page. A URL item is where this came from: it is the
			// one kind whose href is arbitrary rather than a route this desk generated, and an
			// item pointing at "/" claimed the highlight from whichever item the route really
			// belonged to.
			if (!clean_href) return;

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
		}
	}
	// Search, notifications and background tasks, as full-width rows in their own band.
	//
	// Search is here because without a rail it has nowhere else. The rail carried four things
	// besides navigation, and three of them survive its removal: notifications and the user
	// button return to the sidebar, and the apps door is covered by the switcher's "All apps".
	// Search is not. The desk's own full-search button is dead markup, so a dock-less app has no
	// search affordance otherwise.
	//
	// These are full-width rows rather than an icon strip, so the band uses the sidebar's own
	// vocabulary instead of the rail's ghost-icon treatment in a 220px panel, and search stays
	// legible. Nothing new is built for it: each row is the same icon-plus-label item every
	// sidebar link is.
	//
	// The band sits directly under the header, above the module's own items, behind a divider,
	// rather than after the user button where the generic add-item helper put these two. The
	// whole band is hidden when the rail is present (`body.dock-active` hides it),
	// which is what a docked app's sidebar wants: all three off, including background tasks,
	// which it used to show while hiding the bell next to it.
	//
	// The trade-off is that search has two homes depending on whether the app has a rail. That
	// was preferred over stripping the rail's shortcuts, which would have changed every docked
	// app to fix a dock-less one.
	add_standard_items(items) {
		if (this.standard_items_setup) return;
		this.standard_items = [];
		this.standard_items.push({
			label: __("Search"),
			icon: "search",
			standard: true,
			type: "Button",
			// AwesomeBar's delegated click handler in page.js opens the shared search modal from
			// this class, the same modal the rail's own shortcut opens.
			class: "navbar-modal-search-mobile",
			condition: () => !!frappe.boot.desk_settings.search_bar,
		});
		this.standard_items.push({
			label: __("Notification"),
			icon: "bell",
			standard: true,
			type: "Button",
			class: "sidebar-notification hidden",
			suffix: "<span class='notification-count hidden' aria-live='polite'></span>",
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

	// Close the panel when the click lands anywhere else. It reserves no space in the layout any
	// more, so everything it covers is still there underneath and a click on it is a click on the
	// page, not on the sidebar.
	//
	// Three things are not "elsewhere". The panel itself, plainly. The rail, because that is what
	// opens the panel and a row there asks to keep it open on a different module -- without this
	// the panel would close on the same click that opened it, since the handler runs after. And the
	// page header's own toggle, for the same reason.
	setup_click_away() {
		$(document)
			// The panel is rebuilt on some navigations; drop the previous instance's handler rather
			// than stacking another on the document.
			.off(".sidebar-click-away")
			.on("click.sidebar-click-away", (e) => {
				if (!this.sidebar_expanded) return;
				// A sidebar panel -- notifications, background tasks -- is mounted beside the
				// panel rather than inside it, but a click in one is still a click on the
				// sidebar's own furniture.
				if (
					$(e.target).closest(".body-sidebar, .dock, .sidebar-toggle-btn, .sidebar-panel")
						.length
				)
					return;
				this.close();
			});
	}

	// Whether the panel is floating out over the page right now, as opposed to docked or gone.
	is_peeking() {
		return !!this.wrapper && this.wrapper.hasClass("peeking");
	}

	// Whether the panel is on screen at full width, whichever way it got there. A peeked panel is
	// as wide and as legible as a pinned one, so anything sizing itself to the panel -- the header
	// and its padding -- follows this rather than `sidebar_expanded`, which is only about docking.
	panel_is_open() {
		return this.sidebar_expanded || this.is_peeking();
	}

	// Float the collapsed panel out, or let it go. Nothing peeks while the sidebar is already open,
	// while the page hides it, on mobile (where the panel is a full drawer with its own overlay), or
	// while a sidebar panel is open, since those stand in the panel's spot and sliding it out behind
	// one would only shuffle things around. Retracting is never refused, so the panel cannot be left
	// hanging out.
	set_peek(peeking) {
		if (!this.wrapper) return;

		if (peeking) {
			if (this.sidebar_expanded || frappe.is_mobile()) return;
			if (!this.wrapper.is(":visible")) return;
			// Notifications and background tasks moved off dropdowns inside the panel and onto
			// SidebarPanel, which keeps the open one on its registry rather than in the DOM here.
			if (frappe.ui.sidebar_panels?.open_panel) return;
		}

		this.wrapper.toggleClass("peeking", peeking);
		// Gates the rail's expand affordances, which the peeked panel covers (see dock.scss).
		$("body").toggleClass("sidebar-peeking", peeking);
		// The header lays itself out for a panel that is on screen or one that is not, and the
		// panel just changed which of those it is.
		this.sidebar_header?.toggle_width(this.panel_is_open());
	}

	// Retract the peek now, rather than waiting for the pointer to leave. For whatever takes the
	// panel's place on screen, and for the sidebar opening for real.
	end_peek() {
		clearTimeout(this.peek_timer);
		this.set_peek(false);
	}

	toggle_width() {
		if (!this.sidebar_expanded) {
			this.open();
		} else {
			this.close();
		}
	}

	expand_sidebar() {
		if (this.sidebar_expanded) {
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

		localStorage.setItem("sidebar-expanded", this.sidebar_expanded);
		this.sidebar_header.toggle_width(this.panel_is_open());
		// A sidebar that is open for real has nothing left to peek at, and the peeked panel and the
		// pinned one are the same element.
		if (this.sidebar_expanded) this.end_peek();
		// While collapsed, the body sidebar is hidden and only the dock (rail) shows.
		// This gates the rail's edge handle that reopens the sidebar (see dock.scss).
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

	prevent_scroll() {
		let main_section = $(".main-section");
		if (this.sidebar_expanded) {
			main_section.css("overflow", "hidden");
		} else {
			main_section.css("overflow", "");
		}
	}

	// Pick the sidebar for the route we just landed on.
	//
	// The sidebar is usually something the user chooses, from the header switcher or by going
	// straight to a workspace, and it then stays put during navigation. It moves on its own only
	// when the thing navigated to cannot be reached from where you are, and `resolve_sidebar_for`
	// decides where it moves to.
	//
	// Everything is resolved from boot data rather than from the DOM or the URL, so it does not
	// depend on when the route and the page render. The highlight on the active item is separate
	// and stays route-aware, in set_active_workspace_item().
	set_workspace_sidebar() {
		try {
			const route = frappe.get_route();

			if (route[0] === "Workspaces" && route.length >= 2) {
				// An explicit workspace route means the user picked this workspace, so make it
				// the sticky selection. The route names a workspace, so map it to its module
				// before selecting.
				const name = route[route.length - 1];
				const module = this.module_for_workspace(name);
				// Not pinned: a workspace route names its own shell, so the parameter would
				// repeat what the path already says. Leaving here is what writes it -- the shell
				// is then on screen, which pins it for the next navigation.
				if (module) this.select_module(module);
			} else {
				// Resolution never looks at which app the route belongs to. A sidebar may link
				// something from another app on purpose: System Settings belongs to `frappe` but
				// is linked in erpnext's ERPNext Settings sidebar. Filtering by the entity's app
				// would drop the sidebar you are standing in.
				const entity = this.entity_from_route(route);

				if (this.cold_entry_needs_recheck(route, entity)) {
					// The previous pass ran before the doctype's meta existed and could only
					// guess from the sidebars linking it. The module is readable now, so resolve
					// again with no sticky, so the guess cannot keep its own place.
					this.pending_cold_entry = null;
					const { sidebar: target } = this.resolve_sidebar_for(route, null);
					if (target && target !== this.current_module) {
						frappe.app.sidebar.setup(target);
					}
					// Not pinned: this pass resolves with no sticky at all, so whatever it picks
					// is what an unaided resolution gives and the URL need not say it.
				} else {
					// One ladder, whether the user navigated here or arrived cold. The only
					// difference is what counts as the shell you are in: the sidebar on screen
					// while navigating, or the last one picked when there is none.
					//
					// This used to be two ladders, and they disagreed. Navigating jumped straight
					// to the first sidebar linking the entity and skipped the step that prefers
					// the entity's own module, so deep-linking to a document and navigating to it
					// could land in different shells.
					// The shell can be stated three ways, strongest first: the URL names it, it
					// is the one on screen, or it is the last one picked. The first two are
					// pinned -- somebody chose this shell for this navigation -- so they hold
					// across a link into another module. The third is only a memory of an older
					// choice and still has to prove it can show the entity.
					const from_url = this.shell_from_url();
					const on_screen = this.current_module;
					const sticky =
						from_url || on_screen || localStorage.getItem("selected_module");
					const {
						sidebar: target,
						provisional,
						held_by_pin,
					} = this.resolve_sidebar_for(route, sticky, !!(from_url || on_screen));

					// Remember a guess made without the meta, so the branch above re-resolves it
					// once the meta arrives. Set on both paths: a doctype visited for the first
					// time this session has no meta yet, however it was reached.
					this.pending_cold_entry = provisional ? route.join("/") : null;

					if (target && target !== this.current_module) {
						if (this.current_module) this.select_module(target);
						else frappe.app.sidebar.setup(target);
					}

					// Written back only when the pin is what held the shell, so the address bar
					// stays clean everywhere else. Writing it on every navigation put a
					// `sidebar=` on every desk URL, including ones where resolution would have
					// reached the same shell unaided -- noise in every shared link, and it broke
					// the round trip `cypress/integration/routing.js` checks, where a list URL
					// must come back byte-for-byte as it went in.
					//
					// Skipped while provisional: the answer is still a guess and the second pass
					// is about to correct it.
					if (held_by_pin && !provisional) this.pin_shell_in_url(target);
				}
			}
		} catch (e) {
			console.error(e);
		}

		this.set_active_workspace_item();
	}

	// The shell the URL names, or null. Read straight off `location.search` rather than from
	// `frappe.route_options`, which the router merges without ever clearing, so a shell from an
	// earlier navigation could still be sitting in it.
	//
	// It is also deleted from `route_options` here, because everything else that reads that
	// object treats an unrecognised key as a list filter -- so a shell left in it would be
	// applied as `sidebar = <shell>` against whatever doctype was opened.
	shell_from_url() {
		let named = null;
		try {
			named = new URLSearchParams(window.location.search).get(SHELL_PARAM);
		} catch (e) {
			return null;
		}
		if (frappe.route_options) delete frappe.route_options[SHELL_PARAM];

		const all = frappe.boot.module_sidebars || {};
		// A shell missing from the payload was renamed, uninstalled, or belongs to somebody with
		// different permissions. Falling through to resolution beats rendering nothing.
		return named && all[named] ? named : null;
	}

	// Put the resolved shell in the URL, so a reload or a shared link reproduces it.
	//
	// `replaceState`, not `pushState`: the shell is a property of where you already are, and a
	// history entry would make Back undo the shell rather than the navigation.
	pin_shell_in_url(shell) {
		if (!shell) return;
		try {
			const url = new URL(window.location.href);
			if (url.searchParams.get(SHELL_PARAM) === shell) return;
			url.searchParams.set(SHELL_PARAM, shell);
			history.replaceState(history.state, "", url.pathname + url.search + url.hash);
		} catch (e) {
			// A URL the browser will not parse is not worth failing navigation over.
		}
	}

	// Switch to a workspace's sidebar and remember it so the choice survives navigation and
	// reload.
	select_module(module) {
		if (module && module !== this.current_module) {
			frappe.app.sidebar.setup(module);
		}
		if (module) localStorage.setItem("selected_module", module);
	}

	// Switch to a sidebar and navigate into it. This is how the dock's items move between an
	// app's shells. The argument is a shell identity, which is what the payload is keyed by and
	// what a dock entry carries.
	open_module(module) {
		let sidebar = frappe.boot.module_sidebars[module];
		if (!sidebar) return;

		this.select_module(module);

		let route = this.module_landing_route(module);
		if (route) frappe.set_route(route);
	}

	// Navigate to a workspace by name, and show it inside a shell that lists it.
	//
	// The argument is a workspace, not a shell, which is why this is not `open_module`. Global
	// search offers every workspace the user is permitted, including ones no dock row names, so
	// this is the way back to a workspace that is otherwise unreachable.
	//
	// Where `open_module` lands on the shell's first item, this lands on the workspace that was
	// asked for. Selecting the shell is presentation: the sidebar should show where the workspace
	// lives, and `get_modules_linking` puts the owning shell first, so a workspace listed in
	// several lands in the one that claims it. A workspace no shell lists keeps whatever shell is
	// current rather than clearing it, since an empty sidebar helps nobody.
	open_workspace(name) {
		if (!name) return;

		const shell = this.get_modules_linking(name)[0];
		if (shell) this.select_module(shell);

		const route = frappe.ui.sidebar_item.get_route({
			type: "Link",
			link_type: "Workspace",
			link_to: name,
		});
		if (route) frappe.set_route(route);
	}

	// ---------------------------------------------------------------------------------------------
	// The dock's entry set.
	// ---------------------------------------------------------------------------------------------

	// The ordered set of entries an app's dock offers, each resolved to what the rail renders.
	// The dock renders the whole set and highlights the active one.
	//
	// The set is `app_data[].dock`, the rows of the `Dock` record the app ships, already
	// permission-filtered. An app that ships none offers nothing, which makes it dock-less, and a
	// module its record never names is off this rail whatever any layer says.
	//
	// Callers name the app whose set they want; there is no default. A module belonging to no app
	// yields no entries, which leaves such a module's rail empty rather than a rail of one.
	collect_dock_entries(app) {
		const entries = ((app && app.dock) || [])
			.map((row) => this.dock_entry(row))
			.filter(Boolean);

		return this.apply_dock_arrangement(entries, app).filter(Boolean);
	}

	// Resolve one stored row into what the rail needs: a label, an icon, the shell it selects and
	// where clicking it goes. Every kind is answered from a payload the boot already carries, so
	// a pinned workspace and a URL need no extra machinery.
	//
	// Clicking a row does two things: it opens a page and it swaps the shell, and `link_type`
	// says how this row answers both. A `Sidebar` row is the shell itself, so it has no page and
	// opens the shell's own landing route. A `Workspace` row derives its shell from the module
	// that owns the page, which is what lands a user in a companion's shell while the host's rail
	// stays on screen. A `URL` row has no shell and derives none.
	//
	// An entry that resolves to nothing is dropped: a module whose items this user cannot see is
	// absent from `module_sidebars`, and a workspace they cannot open is absent from
	// `workspaces.pages`.
	dock_entry(row) {
		if (!row) return null;

		const page =
			row.link_type === "Workspace"
				? (frappe.boot.workspaces?.pages || []).find((p) => p.name === row.link_to)
				: null;
		if (row.link_type === "Workspace" && !page) return null;
		if (row.link_type === "URL" && !row.url) return null;

		// The shell the row is, or the one that owns the page it opens.
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
			// The row's own label and icon win, then whatever it opens, then the shell it
			// selects. A blank at an upper layer means inherit, which the server resolves, so a
			// blank here is an entry nobody has labelled.
			label: row.title || page?.title || sidebar?.label || row.link_to || row.url,
			icon: row.icon || page?.icon || sidebar?.header_icon,
			page,
		};
	}

	// The rail this app's dock resolves to for this user, already merged by the server: its own
	// dock, then the site's arrangement, then this user's own. The client only drops hidden
	// entries. The payload keeps a hidden entry so the manager's list can render it, which is the
	// one place the dock differs from a sidebar.
	//
	// There is no client-side arrangement left to apply. A saved layer is the rail, so ordering
	// and the trailing-entry fallback were removed with the class they served: an entry the app
	// ships later does not appear on a rail someone has already arranged, it appears in Manage
	// Dock as something to add.
	//
	// `frappe.boot.dock` is keyed by app, because a dock layer is per app. An app with no layers
	// is absent from it and falls back to the entry set, which is its own dock unarranged.
	apply_dock_arrangement(entries, app) {
		const app_name = app && app.app_name;
		const arrangement = (frappe.boot.dock || {})[app_name];
		if (!arrangement) return entries;

		return arrangement.filter((row) => !row.hidden).map((row) => this.dock_entry(row));
	}

	// Go where a dock entry points and select the shell it selects, in that order, because a
	// click does both. A row with a page opens that page; a row with only a shell opens that
	// shell's landing route.
	open_dock_entry(entry) {
		if (!entry) return;

		// A shell entry names a sidebar, not a page. Clicking it swaps the panel to that shell and
		// opens the panel; where to go from there is the user's to pick from the rows it now shows.
		// It used to route to the shell's landing page as well, which is to say it opened the
		// sidebar's first link on their behalf -- the rail's own row for a module and the first row
		// of that module's sidebar are not the same destination, and only one of them was asked
		// for. The switcher menu still lands on it (see `open_module`), because picking a module
		// out of a menu is a request to go there.
		if (entry.link_type === "Sidebar") {
			this.select_module(entry.module);
			this.open();
			return;
		}

		// A pinned row is a destination of its own, so it still travels. Select the shell first, so
		// the sidebar is correct when the route lands. A URL row selects nothing, because it has no
		// shell.
		if (entry.module) this.select_module(entry.module);
		this.open();
		const route = frappe.ui.sidebar_item.get_route({
			type: "Link",
			link_type: entry.link_type,
			link_to: entry.link_to,
			url: entry.url,
		});
		if (route) frappe.set_route(route);
	}

	// What identifies a dock entry on the client: the whole destination, joined the same way as
	// `dock_key` on the server. Never the label, so re-labelling cannot detach a row from itself.
	dock_key(entry) {
		return ["link_type", "link_to", "url"].map((f) => entry[f] || "").join("|");
	}

	// Where an app's icon leads, in three steps:
	//
	//   1. The route it declares. An app may have a front door outside its rail, or outside the
	//      desk entirely, and declaring it is the only way to have one.
	//   2. Its first visible rail entry, resolved late here, so reordering the rail moves the
	//      landing with it: at the site layer for everyone, and at a user's own layer for them.
	//   3. Its first navigable module. This is the floor: an app that resolves to no visible
	//      entry, because it ships no dock or because this user can reach none of it, must still
	//      land somewhere, or the apps screen has an icon with nowhere to go.
	//
	// There used to be a fourth step on the server: an arbitrary workspace picked by
	// `sequence_id`. It was a guess, and a worse one under this model, because that workspace may
	// sit in a module the app's `Dock` record never names, so the icon would land somewhere the
	// rail does not show. It has been removed.
	app_landing_route(app) {
		if (!app) return null;
		if (app.app_route) return app.app_route;

		const [entry] = this.collect_dock_entries(app);
		if (entry) return this.dock_entry_route(entry);

		return this.module_landing_route(this.first_navigable_module(app));
	}

	// Where a rail entry goes, which is where clicking it takes you: its page if it opens one,
	// otherwise the shell's landing route. One definition, so the icon and the button cannot
	// disagree.
	dock_entry_route(entry) {
		if (!entry) return null;
		if (entry.link_type === "Sidebar") return this.module_landing_route(entry.module);
		return frappe.ui.sidebar_item.get_route({
			type: "Link",
			link_type: entry.link_type,
			link_to: entry.link_to,
			url: entry.url,
		});
	}

	// The last step above, and the switcher's own list: the app's modules this user can navigate
	// to, in the app's order. Read from `module_sidebars`, which is already permission-filtered,
	// since a module whose items are all blocked is absent from it. So the icon and the
	// switcher's first row read the same list and agree.
	app_modules(app) {
		if (!app) return [];
		const app_name = app.app_name;
		return Object.values(frappe.boot.module_sidebars || {})
			.filter((sidebar) => sidebar.app === app_name)
			.map((sidebar) => sidebar.name);
	}

	first_navigable_module(app) {
		return this.app_modules(app)[0];
	}

	// Where a shell leads: the first navigable item in the sidebar this user resolved. Named for
	// the module, because a shell is its module unless the sidebar was renamed.
	//
	// This is the single definition of a module's home, used by `open_module` and by the
	// desktop's app icons, so two ways into a module cannot disagree about where it opens. It
	// replaces a stored `home_workspace` pointer and improves on it in three ways, all from
	// resolving late: the boot payload is already permission-filtered, so it can only name
	// something this user can open; it is already customized, so reordering a sidebar moves the
	// landing page with it, at the site layer for everyone and at the user's own layer for them;
	// and a module with no workspace at all still has a home.
	module_landing_route(module) {
		const sidebar = frappe.boot.module_sidebars[module];
		if (!sidebar) return null;

		for (const item of sidebar.items || []) {
			const route = frappe.ui.sidebar_item.get_route(item);
			if (route) return route;
		}
		return null;
	}

	// Whether a dock entry is the one on screen. Such an entry is highlighted on the rail and not
	// offered as a switch target.
	//
	// A row that opens a workspace is active only while the route is that workspace, because
	// several of an app's entries can share a shell and highlighting all of them would say
	// nothing. A row that names a shell is active while that shell is shown. A URL row is never
	// active, because it leaves the desk.
	is_active_entry(entry) {
		if (!entry) return false;
		if (entry.link_type === "URL") return false;
		if (entry.link_type === "Workspace") {
			const route = frappe.get_route();
			return route[0] === "Workspaces" && route[route.length - 1] === entry.link_to;
		}
		return !!entry.module && entry.module === this.current_module;
	}

	// An entity resolves to a module, and only to a module. This is the one place that happens.
	// Every module has a sidebar, authored or generated, so a module always has an answer.
	// Workspaces do not, which is why the two resolvers that used to answer which workspace a
	// doctype lives in (Meta.load_workspaces and the breadcrumb's set_workspace) both had a
	// silent empty case, and why they were deleted rather than taught about ownership. A surface
	// that needs a workspace asks the resolved module for one via module_landing_route(); it does
	// not resolve the entity itself.
	//
	// Pick the sidebar to show on cold entry, returning the choice, why it was made, and whether
	// the answer is provisional (see below).
	//
	// The rule is: membership holds you, ownership decides when nothing does. Every step above
	// the fallbacks asks whether a sidebar actually lists the entity, and the ownership claim
	// breaks the tie among the sidebars that do not list it.
	//
	// Precedence:
	//   1. The last selected sidebar, if it links the entity. Continuity outranks everything
	//      below, including the ownership claim: on a reload or a deep link you stay in the shell
	//      you were working in instead of being moved. It is gated on the link so it can only
	//      hold you where the entity is reachable; an unrelated shell is never kept.
	//   2. An item flagged `is_default_module` names the module that owns the entity. This is the
	//      one authored signal, and it decides when nothing above holds you.
	//   3. The entity's own module, but only while its sidebar lists the entity. A module that
	//      can show the entity beats an unrelated sidebar that only curates a link to it. A module
	//      that ships no navigation of its own is read through its declared heirs here, membership
	//      first, so the rule is unchanged for it. See sidebar_from_module.
	//   4. Then the remaining sidebars that link the entity: the first one, owner-first per
	//      get_modules_linking. A link is a weak signal, since an entity can be curated into any
	//      number of other sidebars, so it decides only once nothing above can show the entity.
	//   3b. The entity's own module anyway, when nothing links the entity at all. This is a
	//      demotion rather than a rejection: the module is still the last principled answer, and
	//      gating step 3 on membership alone would drop a standalone doctype, which by definition
	//      is linked nowhere, into the arbitrary fallbacks below.
	//   5. Otherwise keep the last selected sidebar, when the route belongs to no sidebar at all.
	//   6. The first available sidebar.
	// User.default_workspace is deliberately not consulted here: it made the sidebar stick to one
	// workspace regardless of route, which broke the sense that each entity lives in its own app
	// shell.
	//
	// One trade-off was accepted when this order was chosen, and it is not a bug: the ownership
	// claim drops from the signal that beats every heuristic below to the signal that decides when
	// nothing holds you, so a per-user sticky can outrank an app-authored fact. That is acceptable
	// because step 1's gate only holds you where the entity is visibly present.
	//
	// Membership means someone chose to list the entity, which is why step 3 checks `is_computed`:
	// a computed sidebar lists at most COMPUTED_DOCTYPE_LIMIT doctypes (sidebar.py), so an entity
	// missing from one was not left out on purpose and must not be read that way.
	//
	// Only steps 3 and 3b need the routed doctype's meta, which is not loaded on the first pass of
	// a cold load, because the router fires before the page's meta arrives. When the module cannot
	// be read yet, the results below it are flagged `provisional`: they are the best guess from
	// link data alone, and set_workspace_sidebar re-resolves once the meta arrives. Without that
	// second pass a cold entry would keep the step-4 answer permanently and the module would never
	// be considered. Steps 1 and 2 read only boot data and localStorage, so they are final on the
	// first pass.
	resolve_initial_sidebar(route) {
		return this.resolve_sidebar_for(route, localStorage.getItem("selected_module"));
	}

	// The steps themselves, with step 1's "shell you are in" passed in rather than read here.
	//
	// Three callers, differing only in that one value:
	//   - arriving cold   -> the last sidebar explicitly selected (localStorage)
	//   - navigating      -> the sidebar on screen
	//   - the second pass -> nothing. Continuity was already applied on the first pass, and the
	//                        point of re-resolving is to decide again on full information.
	//                        Passing the provisional answer back in would let step 1 keep it and
	//                        the second pass would never move anything.
	//
	// Everything below step 1 is the same for all three, which is the point: where a document
	// opens must not depend on how you got there.
	resolve_sidebar_for(route, sticky, pinned = false) {
		const all = frappe.boot.module_sidebars || {};
		const exists = (name) => (name && all[name] ? name : null);

		const entity = this.entity_from_route(route);
		const persisted = exists(sticky);
		// Resolved up front rather than at step 4, because steps 1 and 3 are both membership
		// tests against it: whether the sidebar links the entity is the same question either way.
		const candidates = this.get_modules_linking(entity);

		// 1. The shell you are in, or the last one selected when it can show the entity.
		//
		// `pinned` says the shell is a stated fact rather than a leftover: the URL names it, or
		// it is on screen and you got here by following a link out of it. A stated shell holds
		// whatever the route is, which is what stops a link into another module moving the shell
		// underneath you. An unpinned sticky is only a memory, so it still has to prove it can
		// show the entity.
		if (persisted && (pinned || candidates.includes(persisted))) {
			return {
				sidebar: persisted,
				// True only when the pin is what held it -- the shell does not list the entity,
				// so without the pin this would have resolved elsewhere. That is exactly when
				// the shell carries information the URL does not already imply, and it is the
				// only case worth writing to the address bar.
				held_by_pin: !candidates.includes(persisted),
				reason: `last selected sidebar "${persisted}" — route entity "${entity}" is linked in it, so the selection is kept over the entity's owner and its module`,
				provisional: false,
			};
		}

		// 2. The entity is explicitly owned by a module.
		const owner = exists(this.module_for_entity(entity));
		if (owner) {
			return {
				sidebar: owner,
				reason: `"${entity}" is flagged is_default_module in "${owner}"`,
				provisional: false,
			};
		}

		// 3. The entity's module decides, but only while its sidebar can show the entity. The
		//    membership test lives here rather than inside sidebar_from_module(), because that
		//    function also triggers cold_entry_needs_recheck: gating it would stop the second
		//    pass for exactly the entities whose module cannot show them, which are the ones
		//    that need it. The trigger and the resolver stay separate.
		//
		//    "Cannot show the entity" only means something when someone chose what the sidebar
		//    shows. A computed sidebar lists what its module holds, capped at
		//    COMPUTED_DOCTYPE_LIMIT, so an entity missing from one was not left out, it just fell
		//    past a display limit. Reading that as a decision would hand the entity to whichever
		//    other sidebar happens to link it. A module always contains its own entities, so for
		//    a computed sidebar the module answers regardless.
		const from_module = this.sidebar_from_module(entity, route, candidates);
		if (from_module && (candidates.includes(from_module) || this.is_computed(from_module))) {
			return {
				sidebar: from_module,
				reason: candidates.includes(from_module)
					? `derived from "${entity}"'s module — the shell the entity belongs to, and it lists the entity`
					: `derived from "${entity}"'s module — its sidebar is computed, so not listing the entity is a display limit rather than a decision`,
				provisional: false,
			};
		}

		// Step 4 and the fallbacks below can be reached with the module unread, so mark them
		// provisional whenever it is unreadable, since it may only be a doctype meta that has not
		// loaded. Only doctypes can be in that state: a Report, Page or Dashboard reads its module
		// from boot data, so it is never provisional and never waits for a second pass. Marking
		// too eagerly is free, because the caller only acts on the flag once the module resolves,
		// which never happens for a route with nothing left to load, such as a workspace or an
		// entity nobody may see. 3b needs no flag: an unreadable module makes
		// sidebar_from_module() null, so 3b cannot fire on a pass that could not read it.
		const provisional = !!entity && !this.get_module_for_entity(entity, route);

		// 4. The entity is linked in one or more sidebars. The last selected one is not among
		//    them, since step 1 would have taken it, and neither is its own module, since step 3
		//    would have.
		if (candidates.length) {
			return {
				sidebar: candidates[0],
				reason: `route entity "${entity}" is not listed by its own module's sidebar; it is linked in: ${candidates.join(
					", "
				)}`,
				provisional,
			};
		}

		// 3b. Nothing links the entity anywhere, so its own module answers after all. It is
		//     demoted below the links it lost to but still ahead of the arbitrary fallbacks. This
		//     is where a standalone doctype lands: linked by no sidebar, it would otherwise fall
		//     through to a sticky or to whatever sidebar happens to be first.
		if (from_module) {
			return {
				sidebar: from_module,
				reason: `derived from "${entity}"'s module — no sidebar links the entity at all, so its own module answers even though it does not list it`,
				provisional: false,
			};
		}

		// 5. Nothing ties the route to a sidebar, so keep the last selection.
		if (persisted) {
			return {
				sidebar: persisted,
				reason: `last selected sidebar "${persisted}" — route "${entity}" belongs to no sidebar, so the selection is kept`,
				provisional,
			};
		}

		// 6. The first available sidebar.
		// `Object.keys`, not `first.module`: the payload is keyed by shell identity, and every
		// other step returns a key into it. A shell renamed away from its module would make
		// `first.module` a string this map does not hold, so the last resort resolved to nothing.
		const first = Object.keys(all)[0];
		return {
			sidebar: first,
			reason: `fallback to the first available sidebar (route entity "${entity}" matched none)`,
			provisional,
		};
	}

	// True when a cold entry for `route` was resolved before the routed doctype's meta was
	// available, so it could not consult the module, and the module is readable now. This is the
	// trigger for the second resolution pass; see resolve_initial_sidebar.
	//
	// It is broader than step 3's gate on purpose: it asks only whether the module is readable,
	// never whether that module's sidebar lists the entity. Narrowing it to reachable modules
	// would stop the second pass for exactly the entities whose module cannot show them, which
	// are the ones the re-resolve exists for. Firing when the answer will not change is free: the
	// caller compares the re-resolved target against the current sidebar and does nothing when
	// they match.
	cold_entry_needs_recheck(route, entity) {
		return (
			this.pending_cold_entry === route.join("/") &&
			!!this.sidebar_from_module(entity, route)
		);
	}

	// Debug helper: explain why the current sidebar is shown.
	// Call from the console as `frappe.app.sidebar.explain()`.
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

	// The kind of entity a route names, from the route alone. This is the inverse of
	// sidebar_item.get_route(), which turns a link_type into a route.
	//
	// The type matters, because entity names are not unique across kinds. `Attendance` is a
	// Dashboard in "Shift and Attendance" and a DocType in "HR"; `Project`, `Selling` and `Stock`
	// each name both a Dashboard and a doctype. Probing the four maps blindly would be wrong for
	// one route of any such pair, whichever order it used.
	//
	// A report-builder report routes as its ref_doctype's list view (see
	// frappe.utils.generate_route), so it correctly reads as a DocType here. Only `query-report`
	// routes name the Report itself.
	link_type_from_route(route) {
		const view = ENTITY_VIEW_ROUTES[route[0]];
		if (view && route.length > 1) return view;
		if (route[0] && frappe.boot.page_info?.[route[0]]) return "Page";
		return "DocType";
	}

	// The module an entity belongs to, or null, for every kind of entity rather than just
	// doctypes.
	//
	// A DocType's module comes from its meta, which is why it is the only kind that can be
	// unreadable on a cold first pass. Report, Page and Dashboard modules come from the boot maps
	// DeskViews already ships (`allowed_reports`, `page_info`, `dashboards`), which are present
	// from the first byte and permission-filtered per user, so ownership stays per-user. A
	// site-wide `frappe.get_all("Report")` map would have broken that.
	//
	// Dashboards are a list rather than a name-keyed map, since search_utils' get_dashboards
	// iterates it, so this scans. It is about 17 rows, read once per cold entry.
	get_module_for_entity(entity, route) {
		if (!entity) return null;
		switch (this.link_type_from_route(route)) {
			case "Report":
				return frappe.boot.allowed_reports?.[entity]?.module || null;
			case "Page":
				return frappe.boot.page_info?.[entity]?.module || null;
			case "Dashboard":
				return (
					(frappe.boot.dashboards || []).find((d) => d.name === entity)?.module || null
				);
			default:
				return frappe.get_meta(entity)?.module || null;
		}
	}

	// The entity's own module, when that module has a sidebar to land in. With one sidebar per
	// module this is a direct lookup: the payload is keyed by module name. The old version had to
	// fall back to scanning every sidebar for one carrying the module, because a module's sidebar
	// could be titled anything (module "Accounts" mapped to workspace "Accounting"). That scan is
	// no longer needed.
	//
	// A module that ships no navigation at all answers through its heirs instead. `Core`, `Custom`
	// and `Desk` are declared code_only_modules and are absent from the payload. The app that
	// split a module's navigation out declares where it went, and the desk picks among the heirs
	// by the same membership rule everything else uses:
	//
	//   the first heir whose sidebar lists the entity, otherwise the first heir that exists here.
	//
	// A module-level declaration is enough because of that first rule: `Core` fans out to five
	// heirs and never has to say which of them owns `User`, since frappe already curated `User`
	// into `Users`. Both answers come from gates that already exist, so this adds no step: an heir
	// that lists the entity is in `candidates`, so step 3's membership gate passes and it answers
	// there, ahead of step 4's alphabetical order, which is what handed `User` to erpnext's
	// `Setup`. The default heir is not in `candidates`, so step 3 fails, step 4 still lets a
	// foreign link win, and otherwise 3b returns it as the last principled answer before the
	// fallbacks.
	//
	// "Exists here" is the per-user part: the payload is permission-filtered, so a user who cannot
	// see `System` falls to the next heir. Two users can correctly land in different shells.
	//
	// It still returns null when nothing answers: an undeclared code-only module, or heirs this
	// user has none of.
	//
	// `linking` is the caller's already-computed candidate list. resolve_sidebar_for_route builds
	// it before step 1 and every step below uses it, so recomputing it here walked every module's
	// items a second time on each route change. It is optional, because cold_entry_needs_recheck
	// calls this for the trigger alone and has no list to pass.
	sidebar_from_module(entity, route, linking = null) {
		const module = this.get_module_for_entity(entity, route);
		if (!module) return null;
		// A module names its own shell unless the sidebar was renamed, and the payload is keyed
		// by shell, so this returns a shell either way.
		const own = frappe.utils.sidebar_for_module(module);
		if (own) return own.name;

		const heirs = (frappe.boot.code_only_module_heirs?.[module] || [])
			.map((heir) => frappe.utils.sidebar_for_module(heir)?.name)
			.filter(Boolean);
		const links = linking || this.get_modules_linking(entity);

		return heirs.find((heir) => links.includes(heir)) || heirs[0] || null;
	}

	// Whether a sidebar was built from what its module holds rather than shipped by an app. This
	// matters because an entity missing from a shipped sidebar was left out on purpose, while one
	// missing from a computed sidebar may only have fallen past a display limit. Only the first
	// says anything about where the entity belongs.
	is_computed(shell) {
		return !!frappe.boot.module_sidebars?.[shell]?.computed;
	}

	// The sidebar a workspace belongs to, from the payload's `workspaces` list. A direct workspace
	// route names a workspace, and selection works on shells.
	//
	// `workspaces` is a module's list, so every shell under one module carries the same list and
	// the first one answers. A workspace route selects a module's own shell, never a second one;
	// naming a second shell is what a dock row is for.
	module_for_workspace(name) {
		if (!name) return null;
		const entry = Object.values(frappe.boot.module_sidebars || {}).find((sidebar) =>
			(sidebar.workspaces || []).includes(name)
		);
		return entry ? entry.name : null;
	}

	entity_from_route(route) {
		// A view-container route names an entity of another kind, so it is checked before
		// page_info. `dashboard-view` is itself a Page and would otherwise shadow the dashboard
		// it shows, making every dashboard route resolve as the page "dashboard-view". Nothing
		// links that page, so dashboards fell through to the fallbacks.
		if (ENTITY_VIEW_ROUTES[route[0]] && route.length > 1) return route[1];
		if (route[0] && frappe.boot.page_info?.[route[0]]) return route[0];
		switch (route.length) {
			case 1:
				return route[0];
			case 3:
				return route[0] === "Workspaces" && route[1] === "private" ? route[2] : route[1];
			case 2:
				// For view-type routes such as ["List", "Customer"] or
				// ["query-report", "Balance Sheet"], the entity is the second element.
				return route[1];
			default:
				return route[1];
		}
	}

	// Every module whose sidebar contains `link_to`. It ignores which app a link belongs to on
	// purpose (see set_workspace_sidebar), so curated cross-app links resolve correctly.
	get_modules_linking(link_to) {
		let modules = [];
		Object.entries(frappe.boot.module_sidebars || {}).forEach(([module, sidebar]) => {
			if ((sidebar.items || []).some((item) => item.link_to === link_to)) {
				modules.push(module);
			}
		});

		// If one of them owns the entity, meaning its item is flagged is_default_module, put it
		// first so callers taking the top candidate land in the module the entity belongs to.
		const owner = this.module_for_entity(link_to);
		if (owner && modules.includes(owner)) {
			modules = [owner, ...modules.filter((m) => m !== owner)];
		}
		return modules;
	}

	// The module an entity belongs to, or undefined. An entity can appear in several sidebars, and
	// the item flagged `is_default_module` marks its owner. The server builds this as
	// `bootinfo.entity_module` from the permission-filtered payload, so it can only name something
	// the user may see.
	module_for_entity(link_to) {
		const map = frappe.boot.entity_module || {};
		return link_to ? map[link_to] : undefined;
	}
};
