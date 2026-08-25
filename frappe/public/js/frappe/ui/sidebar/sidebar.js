import "./sidebar_item";
import "./workspace_dock";

// Route prefixes that name an entity of another kind rather than being one themselves:
// `/desk/query-report/Balance Sheet` is about the Report, not about "query-report". Both the
// entity and its link type are read off the prefix, which is why they live in one table --
// see link_type_from_route().
//
// `dashboard-view` is itself a Page, so it has to be consulted BEFORE frappe.boot.page_info or
// it shadows the dashboard it is showing. `query-report` is not a Page and never did.
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
	// Resolve a companion app to the host app it's pinned into (an `add_to_dock` row carrying
	// `app`, surfaced as `frappe.boot.app_rail_host`). A companion app has no shell of its own --
	// its workspaces live inside the host app's dock -- so its app context is the host's.
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
			if (frappe.route_options && frappe.route_options.sidebar) {
				frappe.app.sidebar.select_module(frappe.route_options.sidebar);
				frappe.route_options = null;
			} else {
				frappe.app.sidebar.set_workspace_sidebar();
			}
			// The sidebar's setup() rebuilds the header, but it's skipped when the sidebar didn't
			// change (e.g. navigating within the same workspace). Refresh the header here so it
			// always reflects the module resolved above.
			frappe.app.sidebar.refresh_header();
			// Keep the workspace dock in sync with the shown module and the active workspace.
			frappe.app.sidebar.refresh_dock();
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+/",
			action: () => me.toggle_width(),
			description: __("Toggle sidebar"),
		});
	}

	// Point the header at the module currently shown, even when the sidebar itself didn't change
	// and setup() wasn't re-run.
	//
	// One header for the life of the desk, refreshed rather than rebuilt. Its menu is bound to
	// the element it was given and `frappe.ui.create_menu` registers a document-level listener
	// per call, so building a header per navigation would strand the menu on a detached node and
	// leak a listener every time you moved.
	refresh_header() {
		if (!this.current_module) return;

		if (this.sidebar_header) {
			this.sidebar_header.refresh();
		} else {
			this.sidebar_header = new frappe.ui.SidebarHeader(this);
		}
	}

	// The app that owns the body sidebar currently on screen, as an app_data entry (or null). This
	// is the whole of "app context" in the desk: it answers the one question app context is still
	// asked -- what supplies the rail's items -- and nothing else. A module belonging to no app
	// (an unplaced or orphaned custom module) resolves to null, which is a complete answer: the
	// rail wears that module's own icon over an empty items region.
	//
	// Resolved from the shown module's own `app` (sidebars carry it on the boot payload),
	// so it follows the sidebar on screen rather than the route -- a sidebar may deliberately
	// curate a cross-app link, and the shell you are in should not change because you followed it.
	get_sidebar_app() {
		if (!this.current_module) return null;
		// A sidebar carries its app outright, so there is nothing left to reconcile
		// between the workspace's `app` and the payload's.
		const sidebar = frappe.boot.module_sidebars[this.current_module];
		const app_name = sidebar && sidebar.app;
		return app_name
			? frappe.boot.app_data.find((a) => a.app_name === this.rail_host_app(app_name))
			: null;
	}

	// The MODULE the shell on screen belongs to.
	//
	// `current_module` is a shell identity -- the key `frappe.boot.module_sidebars` is built on --
	// and the two are the same string unless somebody named a sidebar something other than its
	// module. Every surface that names a real `Module Def` (a workspace's module, a
	// `Custom Sidebar`) asks this one instead of reading the shell and hoping.
	current_module_def() {
		if (!this.current_module) return null;
		const sidebar = frappe.boot.module_sidebars[this.current_module];
		return (sidebar && sidebar.module) || this.current_module;
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
		// Re-resolve now that the routed doctype's meta is loaded. On a cold/direct load the router
		// `change` handler ran before the meta was available, so the entity's module -- and with it
		// the sidebar, the header and the rail -- couldn't be derived. This second pass fills it
		// in. All three are idempotent, so re-running is cheap.
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
					// The dock is an app's own modules, so a module in no app has no dock to
					// arrange -- its items region is empty by construction. Offering the picker
					// there would invite the user to curate nothing. Evaluated on every open
					// (frappe.ui.menu re-runs conditions in make()), so it tracks the shell you
					// are in rather than the one the menu was built in.
					condition: () => !!me.get_sidebar_app(),
					onClick: function () {
						// The editor is lazy (not in the desk bundle); pull it in on
						// click, then open the dock's manager.
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
	// The sidebar is mostly something you choose -- from the header switcher, or by going straight
	// to a workspace -- and it then stays put as you navigate. It moves on its own only when the
	// thing you navigated to cannot be reached from where you are, and `resolve_sidebar_for`
	// decides where it moves to.
	//
	// Everything is resolved from boot data rather than from the DOM or the URL, so it does not
	// depend on when the route and the page happen to render. The highlight on the active item is
	// separate and stays route-aware, in set_active_workspace_item().
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
				// Resolution never looks at which app the route belongs to. A sidebar may
				// deliberately link something from another app -- System Settings belongs to
				// `frappe` but is linked in erpnext's ERPNext Settings sidebar -- so filtering by
				// the entity's app would drop the very sidebar you are standing in.
				const entity = this.entity_from_route(route);

				if (this.cold_entry_needs_recheck(route, entity)) {
					// The pass before this one ran before the doctype's meta existed and could
					// only guess from the sidebars linking it. The module is readable now, so
					// resolve again -- with no sticky, so the guess cannot hold its own place.
					this.pending_cold_entry = null;
					const { sidebar: target } = this.resolve_sidebar_for(route, null);
					if (target && target !== this.current_module) {
						frappe.app.sidebar.setup(target);
					}
				} else {
					// One ladder, whether you navigated here or arrived cold. The only difference
					// is what counts as the shell you are in: the sidebar on screen while
					// navigating, the last one you picked when there is none.
					//
					// This used to be two ladders, and they disagreed. Navigating jumped straight
					// to the first sidebar linking the entity, skipping the step that prefers the
					// entity's OWN module -- so deep-linking to a document and navigating to it
					// could land you in different shells.
					const sticky = this.current_module || localStorage.getItem("selected_module");
					const { sidebar: target, provisional } = this.resolve_sidebar_for(
						route,
						sticky
					);

					// Remember a guess made without the meta, so the branch above re-resolves it
					// once the meta lands. Set on both paths: a doctype visited for the first time
					// this session has no meta yet however you reached it.
					this.pending_cold_entry = provisional ? route.join("/") : null;

					if (target && target !== this.current_module) {
						if (this.current_module) this.select_module(target);
						else frappe.app.sidebar.setup(target);
					}
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

	// Switch to a sidebar and navigate into it -- how the dock's items move you between an app's
	// shells. The argument is a shell identity, which is what the payload is keyed by and what a
	// dock entry carries.
	open_module(module) {
		let sidebar = frappe.boot.module_sidebars[module];
		if (!sidebar) return;

		this.select_module(module);

		let route = this.module_landing_route(module);
		if (route) frappe.set_route(route);
	}

	// ---------------------------------------------------------------------------------------------
	// The dock's entry set.
	// ---------------------------------------------------------------------------------------------

	// The ordered set of entries an app's dock offers, each resolved to what the rail renders it
	// as. The dock renders the whole set, highlighting the active one.
	//
	// The set is `app_data[].dock` -- one ordered typed list, already permission-filtered: the
	// app's own modules as `Sidebar` rows, then the workspaces an `add_to_dock` row put on this
	// app's fragment, including the ones companion apps pinned onto it. It replaces a separate
	// module list and workspace list that the rail had to reconcile, and that the pin fell
	// between.
	//
	// Callers name the app whose set they want; there is no ambient default. No app -- a module
	// belonging to none -- yields no entries, which is what leaves such a module's rail
	// empty rather than a rail of one.
	collect_dock_entries(app) {
		const entries = ((app && app.dock) || [])
			.map((row) => this.dock_entry(row))
			.filter(Boolean);

		return this.apply_dock_arrangement(entries);
	}

	// One typed row resolved to what the rail needs: a label, an icon, the sidebar it selects and
	// where clicking it goes. Both kinds answer out of a payload the boot already carries, so a
	// `Workspace` entry needs no machinery of its own.
	//
	// An entry that resolves to nothing is dropped: a module whose every item this user may not
	// see is absent from `module_sidebars`, and a workspace they may not open is absent from
	// `workspaces.pages`.
	dock_entry(row) {
		if (!row || !row.name) return null;

		if (row.type === "Sidebar") {
			const sidebar = frappe.boot.module_sidebars[row.name];
			if (!sidebar) return null;
			return {
				type: row.type,
				name: row.name,
				module: row.name,
				label: sidebar.label || row.name,
				icon: sidebar.header_icon,
			};
		}

		if (row.type === "Workspace") {
			const page = (frappe.boot.workspaces?.pages || []).find((p) => p.name === row.name);
			if (!page) return null;
			return {
				type: row.type,
				name: row.name,
				// the sidebar a pinned workspace selects is the one of the module that owns it,
				// which is what lands a person in the companion's shell while the host's rail
				// stays on screen
				module: this.module_for_workspace(row.name) || page.module,
				label: page.title || row.name,
				icon: page.icon,
				page,
			};
		}

		return null;
	}

	// Apply the dock arrangement in `frappe.boot.dock` -- each app's fragment with the site's
	// arrangement and this user's own already merged on top of it by the server: drop what it
	// hides, and order what it names. An arrangement is one flat cross-app list, so it is
	// applied *within* this app's set rather than replacing it -- as a replacement it would put
	// the same rail on every app. An arrangement naming none of this app's entries leaves the
	// app's own order alone rather than rendering an empty rail.
	//
	// Entries are typed pairs and the arrangement is keyed on both halves, so a `Workspace` and a
	// `Sidebar` of one name are two entries and never match each other. Both kinds are ordered,
	// hidden and rendered the same way -- a pin is an entry on the dock, not a fixture on it.
	//
	// The layers above the app only order and hide; they never add. An arrangement row naming
	// something outside this set resolves to nothing here, which is what stops a person pinning
	// an arbitrary workspace onto their own rail.
	apply_dock_arrangement(entries) {
		const arrangement = frappe.boot.dock || [];
		if (!arrangement.length) return entries;

		const hidden = new Set(
			arrangement.filter((p) => p.hidden).map((p) => this.dock_key(p.type, p.name))
		);
		const order = new Map(arrangement.map((p, idx) => [this.dock_key(p.type, p.name), idx]));
		const key = (e) => this.dock_key(e.type, e.name);

		// An arrangement that names nothing in this app says nothing about it -- every entry it
		// does name belongs to some other app's dock. Hiding, though, is honoured even when it
		// empties the rail: a site that hid an app's whole set meant to.
		if (!entries.some((e) => order.has(key(e)))) return entries;

		// Entries the arrangement never names keep their app order and trail the ones it did, so
		// installing an app still surfaces its modules on a dock that has already been arranged.
		// `MAX_SAFE_INTEGER` rather than `Infinity`: two unnamed entries would subtract to `NaN`,
		// and a comparator that returns `NaN` is only saved by sort stability.
		const position = (e) => order.get(key(e)) ?? Number.MAX_SAFE_INTEGER;
		return entries
			.filter((e) => !hidden.has(key(e)))
			.sort((a, b) => position(a) - position(b));
	}

	// Go where a dock entry points, and select the sidebar it belongs to. A module opens at its
	// own landing route; a workspace opens at itself, and the sidebar that comes with it is the
	// one of the module that owns it.
	open_dock_entry(entry) {
		if (!entry) return;

		if (entry.type === "Workspace") {
			this.select_module(entry.module);
			const route = frappe.ui.sidebar_item.get_route({
				type: "Link",
				link_type: "Workspace",
				link_to: entry.name,
			});
			if (route) frappe.set_route(route);
			return;
		}

		this.open_module(entry.module);
	}

	// What identifies a dock entry, client-side: the same pair, joined the same way, as
	// `dock_key` on the server. Both halves, because the kinds do not share a namespace.
	dock_key(type, name) {
		return `${type}::${name}`;
	}

	// Where an app's icon leads. `app_route` covers apps that declare one; otherwise land on
	// the first entry of its dock -- the same place clicking that entry would go.
	app_landing_route(app) {
		if (!app) return null;
		if (app.app_route) return app.app_route;

		const [entry] = this.collect_dock_entries(app);
		return entry ? this.module_landing_route(entry.module) : null;
	}

	// Where a shell leads: the first navigable item in the sidebar *this user* resolved. Named
	// for the module because that is what a shell is for all but the deliberately renamed few.
	//
	// The single definition of a module's home, used by `open_module` and by the desktop's app
	// icons -- so no two ways into a module can disagree about where it opens. It replaces a stored `home_workspace` pointer, and is better than
	// one in three ways that all come from resolving late: the boot payload is already
	// permission-filtered, so it can only name something this user can open; it is already
	// customized, so reordering a sidebar moves the landing page with it, at the site layer for
	// everyone and at the user's own for them; and a module that has no workspace at all still
	// has a home.
	module_landing_route(module) {
		const sidebar = frappe.boot.module_sidebars[module];
		if (!sidebar) return null;

		for (const item of sidebar.items || []) {
			const route = frappe.ui.sidebar_item.get_route(item);
			if (route) return route;
		}
		return null;
	}

	// Whether a dock entry is the one on screen -- not offered as a switch target, and highlighted
	// on the rail. A module entry is active while its sidebar is the one shown; a workspace entry
	// only while the route is that workspace, because several of an app's entries can share a
	// module and highlighting all of them would say nothing.
	is_active_entry(entry) {
		if (!entry) return false;
		if (entry.type === "Workspace") {
			const route = frappe.get_route();
			return route[0] === "Workspaces" && route[route.length - 1] === entry.name;
		}
		return entry.module === this.current_module;
	}

	// An entity resolves to a MODULE, and only to a module -- this is the one place it happens.
	// Module space is total: every module has a sidebar, authored or generated, so the answer is
	// always reachable. Workspace space is not, which is why the two resolvers that used to answer
	// "which workspace does this doctype live in" (Meta.load_workspaces and the breadcrumb's
	// set_workspace) both had a silent empty case, and why they were deleted rather than taught
	// about ownership. A surface that needs a workspace asks the resolved module for one via
	// module_landing_route(); it does not resolve the entity itself.
	//
	// Pick the sidebar to show on cold entry, returning the choice, why it was made, and whether
	// the answer is provisional (see below).
	//
	// One rule, stated twice: MEMBERSHIP HOLDS YOU, OWNERSHIP DECIDES WHEN NOTHING DOES. Every step
	// above the fallbacks asks whether a sidebar actually lists the entity; the claim breaks the tie
	// among the sidebars that do not hold you.
	//
	// Precedence:
	//   1. the last selected sidebar, if it links the entity. Continuity outranks everything below,
	//      the claim included: on a reload or a deep link you stay in the shell you were working in
	//      instead of being relocated. Gated on the link so it can only hold you somewhere the
	//      entity is actually reachable — an unrelated shell is never kept.
	//   2. an item flagged `is_default_module` names the module that owns the entity — the one
	//      authored signal, and the thing that decides when nothing above holds you.
	//   3. the entity's own module, WHILE its sidebar lists the entity. A module that can show the
	//      entity beats an unrelated sidebar that merely curates a link to it. A module that ships
	//      no navigation of its own is read through its declared heirs here, membership first, so
	//      the rule holds for it unchanged — see sidebar_from_module.
	//   4. only then the remaining sidebars that link the entity: the first, owner-first per
	//      get_modules_linking. A link is a weak signal — an entity can be curated into any number
	//      of foreign sidebars — so it decides only once no one above can show the entity.
	//   3b. the entity's own module anyway, when NOTHING links the entity at all. A demotion, not a
	//      rejection: the module is still the last principled answer, and gating step 3 on
	//      membership alone would drop a standalone doctype (linked nowhere, by definition) into
	//      the arbitrary fallbacks below.
	//   5. otherwise keep the last selected sidebar (the route belongs to no sidebar at all)
	//   6. the first available sidebar
	// User.default_workspace is intentionally NOT consulted here: it made the sidebar sticky to
	// one workspace regardless of route, which broke the illusion that each entity lives in its
	// own app shell.
	//
	// One cost was accepted deliberately when this order was chosen; it is not a bug report.
	//   - The claim drops from "the one authored signal that beats every heuristic below" to "the
	//     signal that decides when nothing holds you", so a per-user sticky can outrank an
	//     app-authored fact. Tolerable because step 1's gate only holds you where the entity is
	//     visibly present.
	//
	// Membership means "somebody chose to list this", which is why step 3 asks `is_computed`:
	// a computed sidebar lists at most COMPUTED_DOCTYPE_LIMIT doctypes (sidebar.py), so an entity
	// missing from one was never left out on purpose and must not be read as if it were.
	//
	// Only steps 3 and 3b need the routed doctype's meta, which is NOT loaded on the first pass of a
	// cold load (the router fires before the page's meta arrives). When the module can't be read yet
	// the results below it are flagged `provisional`: they are the best guess from link data alone,
	// and set_workspace_sidebar re-resolves once the meta lands. Without that second pass a cold
	// entry would permanently keep the step-4 answer and the module would never get a look in.
	// Steps 1-2 read boot data and localStorage only, so they are final on the first pass.
	resolve_initial_sidebar(route) {
		return this.resolve_sidebar_for(route, localStorage.getItem("selected_module"));
	}

	// The ladder itself, with step 1's "shell you are in" passed in rather than read.
	//
	// Three callers, and the only thing they disagree about is that one value:
	//   - arriving cold      -> the last sidebar explicitly selected (localStorage)
	//   - navigating         -> the sidebar on screen
	//   - the second pass    -> nothing. Continuity was already spent on the first pass, and the
	//                           whole point of re-resolving is to decide again on full
	//                           information. Passing the provisional answer back in would let
	//                           step 1 keep it and the second pass would never move anything.
	//
	// Everything below step 1 is identical for all three, which is the point: where a document
	// opens must not depend on how you got to it.
	resolve_sidebar_for(route, sticky) {
		const all = frappe.boot.module_sidebars || {};
		const exists = (name) => (name && all[name] ? name : null);

		const entity = this.entity_from_route(route);
		const persisted = exists(sticky);
		// resolved up front (rather than at step 4) because steps 1 and 3 are both membership
		// tests against it: "the sidebar links the entity" is the same question either way
		const candidates = this.get_modules_linking(entity);

		// 1. the last selected sidebar, when it can actually show the entity
		if (persisted && candidates.includes(persisted)) {
			return {
				sidebar: persisted,
				reason: `last selected sidebar "${persisted}" — route entity "${entity}" is linked in it, so the selection is kept over the entity's owner and its module`,
				provisional: false,
			};
		}

		// 2. the entity is explicitly owned by a module
		const owner = exists(this.module_for_entity(entity));
		if (owner) {
			return {
				sidebar: owner,
				reason: `"${entity}" is flagged is_default_module in "${owner}"`,
				provisional: false,
			};
		}

		// 3. the entity's module decides, but only while its sidebar can show the entity. The
		//    membership test lives here rather than inside sidebar_from_module() because that
		//    function is also cold_entry_needs_recheck's trigger: gating it would stop the second
		//    pass firing for exactly the entities whose module cannot show them, which are the ones
		//    that need it. Trigger and resolver stay distinct.
		//
		//    "Cannot show the entity" only means something when somebody chose what the sidebar
		//    shows. A computed sidebar lists what its module holds, capped at
		//    COMPUTED_DOCTYPE_LIMIT — so an entity missing from one has not been left out, it has
		//    just fallen past a display limit, and reading that as a decision hands the entity to
		//    whichever foreign sidebar happens to link it. A module always contains its own
		//    entities, so for a computed sidebar the module answers regardless.
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
		// provisional whenever it is unreadable — it may just be a doctype meta that hasn't loaded.
		// Only doctypes can be in that state: a Report, Page or Dashboard reads its module from
		// boot data, so it is never provisional and never waits for a second pass. Being over-eager
		// is free: the caller only acts on the flag once the module actually resolves, which never
		// happens for a route with nothing left to arrive (a workspace, an entity nobody may see).
		// 3b needs no flag of its own: an unreadable module makes sidebar_from_module() null, so 3b
		// cannot fire on a pass that could not read it.
		const provisional = !!entity && !this.get_module_for_entity(entity, route);

		// 4. the entity is linked in one or more sidebars — the last selected one is not among them
		//    (step 1 would have taken it) and neither is its own module (step 3 would have)
		if (candidates.length) {
			return {
				sidebar: candidates[0],
				reason: `route entity "${entity}" is not listed by its own module's sidebar; it is linked in: ${candidates.join(
					", "
				)}`,
				provisional,
			};
		}

		// 3b. nothing links the entity anywhere, so its own module answers after all — demoted below
		//     the links it lost to, but still ahead of the arbitrary fallbacks. This is where a
		//     standalone doctype lands: linked by no sidebar, it would otherwise fall through to a
		//     sticky or to whatever sidebar happens to be first.
		if (from_module) {
			return {
				sidebar: from_module,
				reason: `derived from "${entity}"'s module — no sidebar links the entity at all, so its own module answers even though it does not list it`,
				provisional: false,
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
	//
	// Deliberately broader than step 3's gate: it asks only whether the module is readable, never
	// whether that module's sidebar lists the entity. Narrowing it to reachable modules would stop
	// the second pass for precisely the entities whose module cannot show them -- the ones the
	// re-resolve exists for. Firing when the answer will not move is free: the caller compares the
	// re-resolved target against the current sidebar and does nothing when they match.
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

	// The kind of entity a route names, from the route alone -- the honest inverse of
	// sidebar_item.get_route(), which turns a link_type into a route.
	//
	// The type is not decoration: entity names are not unique ACROSS kinds. `Attendance` is a
	// Dashboard in "Shift and Attendance" and a DocType in "HR"; `Project`, `Selling` and `Stock`
	// name both a Dashboard and a doctype. A blind probe of the four maps is therefore wrong for
	// one route of any such pair, whichever order it picks.
	//
	// A report-builder report routes as its ref_doctype's list view (see frappe.utils.generate_route),
	// so it correctly reads as a DocType here -- only `query-report` routes name the Report itself.
	link_type_from_route(route) {
		const view = ENTITY_VIEW_ROUTES[route[0]];
		if (view && route.length > 1) return view;
		if (route[0] && frappe.boot.page_info?.[route[0]]) return "Page";
		return "DocType";
	}

	// The module an entity belongs to, or null -- for every kind of entity, not just doctypes.
	//
	// A DocType's module comes from its meta, which is why it is the only kind that can be
	// unreadable on a cold first pass. Report, Page and Dashboard modules ride in on the boot maps
	// DeskViews already ships (`allowed_reports`, `page_info`, `dashboards`), which are present
	// from the first byte and permission-filtered per user -- so ownership stays per-user, which a
	// fresh site-wide `frappe.get_all("Report")` map would have quietly broken.
	//
	// Dashboards are a list rather than a name-keyed map (search_utils' get_dashboards iterates
	// it), so this scans; it is ~17 rows, read once per cold entry.
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

	// The entity's own module, when that module has a sidebar to land in. Under 1:1 this is a
	// direct hit: the payload is keyed by module name, so the module indexes straight into it. The
	// old version had to fall back to scanning every sidebar for one carrying the module, because a
	// module's sidebar could be titled anything (module "Accounts" -> workspace "Accounting").
	// That scan is what 1:1 eliminates.
	//
	// A module that ships no navigation at all (`Core`, `Custom`, `Desk` are declared
	// code_only_modules and are absent from the payload) answers through its heirs instead: the
	// app that split its navigation out declares where the navigation went, and the desk picks
	// among the heirs by the same membership rule everything else uses --
	//
	//   the first heir whose sidebar LISTS the entity, else the first heir that EXISTS here.
	//
	// A module-level declaration is enough because of that first line: `Core` fans out to five
	// heirs and never has to say which of them owns `User`, since frappe already curated `User`
	// into `Users`. Both answers then fall out of gates that already exist, which is why this adds
	// no step to the stack: an heir that lists the entity is in `candidates`, so step 3's
	// membership gate passes and it answers there -- ahead of the step 4 alphabet, which is what
	// handed `User` to erpnext's `Setup`. The default heir is not in `candidates`, so step 3 fails,
	// step 4 still lets a foreign link win, and otherwise 3b returns it as the last principled
	// answer before the fallbacks.
	//
	// "Exists here" is the per-user half: the payload is permission-filtered, so a user who cannot
	// see `System` falls to the next heir. Two users can correctly land in different shells.
	//
	// Still null when nothing answers -- an undeclared code-only module, or heirs this user has
	// none of.
	//
	// `linking` is the caller's already-computed candidate list. resolve_sidebar_for_route works
	// it out before step 1 and every step below uses it, so recomputing it here walked every
	// module's every item a second time on each route change. Optional, because
	// cold_entry_needs_recheck calls this for the trigger alone and has no list to lend.
	sidebar_from_module(entity, route, linking = null) {
		const module = this.get_module_for_entity(entity, route);
		if (!module) return null;
		// A module names its own shell for all but the deliberately renamed few; the payload is
		// keyed by shell, so the answer this returns is a shell either way.
		const own = frappe.utils.sidebar_for_module(module);
		if (own) return own.name;

		const heirs = (frappe.boot.code_only_module_heirs?.[module] || [])
			.map((heir) => frappe.utils.sidebar_for_module(heir)?.name)
			.filter(Boolean);
		const links = linking || this.get_modules_linking(entity);

		return heirs.find((heir) => links.includes(heir)) || heirs[0] || null;
	}

	// Whether a sidebar was built from what its module holds rather than shipped by an app. What
	// it is for: an entity missing from a shipped sidebar was left out on purpose, while one
	// missing from a computed sidebar may simply not have fitted. Only the first of those is a
	// statement about where the entity belongs.
	is_computed(shell) {
		return !!frappe.boot.module_sidebars?.[shell]?.computed;
	}

	// The sidebar a workspace belongs to, from the payload's `workspaces` list. A direct workspace
	// route names a workspace, and selection is shell-shaped.
	//
	// `workspaces` is a module's list, so every shell under one module carries the same one and
	// the first of them answers -- a workspace route selects a module's own shell, never its
	// second. Naming the second is what a dock row is for.
	module_for_workspace(name) {
		if (!name) return null;
		const entry = Object.values(frappe.boot.module_sidebars || {}).find((sidebar) =>
			(sidebar.workspaces || []).includes(name)
		);
		return entry ? entry.name : null;
	}

	entity_from_route(route) {
		// A view-container route names an entity of another kind, so it is answered before
		// page_info: `dashboard-view` IS a Page, and would otherwise shadow the dashboard it shows,
		// making every dashboard route resolve as the page "dashboard-view". Nothing links that
		// page, so dashboards fell straight through to the fallbacks.
		if (ENTITY_VIEW_ROUTES[route[0]] && route.length > 1) return route[1];
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

		// If one of them owns the entity (its item is flagged is_default_module), surface it
		// first so callers taking the top candidate land in the module the entity belongs to.
		const owner = this.module_for_entity(link_to);
		if (owner && modules.includes(owner)) {
			modules = [owner, ...modules.filter((m) => m !== owner)];
		}
		return modules;
	}

	// The module an entity belongs to, or undefined. An entity can appear in several sidebars;
	// the item flagged `is_default_module` marks its owner. Built server-side
	// (`bootinfo.entity_module`) from the permission-filtered payload, so it can only ever name
	// something the user may see.
	module_for_entity(link_to) {
		const map = frappe.boot.entity_module || {};
		return link_to ? map[link_to] : undefined;
	}
};
