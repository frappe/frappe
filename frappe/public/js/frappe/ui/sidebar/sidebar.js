import "./sidebar_item";
import "./dock";

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

// How strongly a sidebar item's href claims the page at `path`. 0 means it does not.
//
// An item claims its own URL, and the URLs under it: `/desk/selling/item` claims
// `/desk/selling/item/ITEM-0001`, since a document is part of the list it came from.
//
// A workspace claims only its own URL. Its href is also the root of the shell, so everything
// in the shell sits under it: `/desk/selling` is a prefix of `/desk/selling/dashboard` and of
// every other page in Selling. Letting it claim what is under it lit the workspace up on every
// page the sidebar holds no item for. `/desk/accounts/invoicing` did the same to Accounts.
//
// Between two claims, the longer href wins, because it names the page more precisely. An
// item whose filters match the URL's beats one with no filters, which is how two items for one
// doctype with different filters tell themselves apart. An item whose filters do not match
// claims nothing.
function route_claim(raw_href, link_type, path, params) {
	const [href_path, query] = (raw_href || "").split("?");
	const href = strip_trailing_slash(decodeURIComponent(href_path.split("#")[0]));

	// A root or empty href strips to "", and "" is a prefix of every route. A `URL` item is
	// where this came from: its href is whatever its author wrote, and one pointing at "/"
	// claimed every page.
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

	// Filters outrank length, and an exact match outranks a prefix of the same length (it
	// cannot tie with one, but the order says which question comes first).
	return (filtered ? 1e6 : 0) + href.length * 2 + (exact ? 1 : 0);
}

function strip_trailing_slash(path) {
	return path.replace(/\/$/, "");
}

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
			// One path for every navigation. The branch this replaces read the shell out of the
			// URL, called `select_module`, and then cleared `frappe.route_options` wholesale,
			// throwing away every other parameter in the URL -- so a link carrying both a shell
			// and list filters arrived with the filters silently gone.
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
	// bound to the element it was given, so building a header per navigation would strand the
	// menu on a detached node. The rows themselves need no refreshing: the dropdown reads them
	// from a function it calls on every open.
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

	// The app a shell belongs to, as the rail names it, or null. `get_sidebar_app` answers the
	// same question for the shell on screen and returns the app_data entry the rail renders from;
	// this answers it for any shell and returns just the name, which is all a comparison needs.
	//
	// A shell belonging to no app answers null, and null is never equal to an app, so an unplaced
	// or orphaned module neither holds a shell nor moves one.
	app_for_sidebar(shell) {
		const sidebar = shell && frappe.boot.module_sidebars?.[shell];
		const app_name = sidebar && sidebar.app;
		return app_name ? this.rail_host_app(app_name) : null;
	}

	// Whether moving to `entity_shell` leaves the app `shell` belongs to.
	//
	// This is the one thing the shell on screen does not survive (see `shell_can_show`). App
	// context in the desk means only what supplies the rail, so a shell kept across an app
	// boundary is a rail whose logo and rows belong to an app the page is not in: reaching Job
	// Applicant from a Journal Entry left erpnext's rail on screen over an hrms document.
	//
	// It asks about the entity's own shell and nothing else. That shell comes from the boot map
	// the server resolved rather than from a doctype's meta, so it is known on the first pass and
	// there is nothing to re-check once the meta loads.
	crosses_app(shell, entity_shell) {
		if (!entity_shell || entity_shell === shell) return false;
		const here = this.app_for_sidebar(shell);
		const there = this.app_for_sidebar(entity_shell);
		return !!here && !!there && here !== there;
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
	//
	// The opt-out is about room, and it means what it says again. It was written when the panel sat
	// in the flow of the page and took 220px from it, so a page that wanted the width said so and
	// got it; that is the panel once more, on every screen where the rail is an overlay rather than
	// a column, so a page like POS or shop floor gets its full width back.
	//
	// The one place it still cannot be taken at face value is a drawer. Below md the panel is
	// opened from the navbar, and a page that removed it from the document would leave that trigger
	// opening nothing -- so there `hide_sidebar` keeps the weaker meaning it can afford: closed on
	// arrival (see apply_page_visibility) rather than taken away.
	page_allows_sidebar() {
		const page = this.current_page();
		if (!page) return false;
		return !page.hide_sidebar || this.panel_can_close();
	}

	// Whether the panel is allowed to close at all.
	//
	// On a desktop it is not. The panel is the desk's navigation -- the rail above it is an overlay
	// that is off screen until it is called for (see dock.js) -- so what `close` does there is fold
	// it to its icon rail, which keeps every destination a click away and its edge to bring it back.
	//
	// Below 768px there is no rail at all (`display: none`, dock.scss) and the panel is a drawer
	// over the page, which has to be able to shut. That is the same 768 the rail is drawn at, and
	// `frappe.is_mobile` already holds it and already clears its answer on resize, so it is read
	// from there rather than stated again.
	//
	// It is this same question that decides where the panel starts (see load_sidebar_state).
	panel_can_close() {
		return frappe.is_mobile();
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
		const page = this.current_page();

		const allowed = this.page_allows_sidebar();
		// A page that asked for no sidebar and kept it anyway -- a drawer, which has to stay in the
		// document for the navbar to open it -- gets it out of the way instead: closed on arrival,
		// however it was left.
		if (allowed && page && page.hide_sidebar && this.sidebar_expanded) this.close();

		this.wrapper.toggle(allowed);
		this.refresh_dock();
	}

	// Explicit override for callers that want the body sidebar hidden or shown regardless of the
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
				avatar: frappe.avatar(frappe.session.user, "avatar-medium"),
				navbar_settings: frappe.boot.navbar_settings,
			})
		)
			// Starts hidden; only a page that allows it turns it on (see apply_page_visibility).
			// Hiding it before it enters the document means a page that hides the sidebar never
			// flashes it first.
			.hide()
			.prependTo("body");
		this.$sidebar = this.wrapper.find(".sidebar-items");

		this.wrapper.find(".sidebar-edge").on("click", () => this.toggle_width());

		this.wrapper.find(".overlay").on("click", () => {
			this.close();
		});
		this.wrapper.find(".sidebar-collapse-arrow").on("click", () => this.toggle_width());
		// Any row that goes somewhere takes the panel down behind it: the panel is an overlay over
		// the page it just navigated, so leaving it up would cover the thing that was asked for.
		// Rows that only toggle a group carry no href and are left alone, since expanding a group
		// is a request to see more of this list rather than to leave it.
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

	// Build the user dropdown (settings, the dock manager, reload, logout) on a trigger
	// element. Shared by the sidebar's user button and the dock's avatar so both open
	// the same menu. What a site adds in Navbar Settings is not here; that hangs off the sidebar
	// header's menu, see SidebarHeader.navbar_items. `button` is the element that gets the
	// active-state class while the menu is open.
	create_user_menu({ parent, button }) {
		const me = this;
		const $btn = button;
		const $container = parent;

		new frappe.ui.Dropdown({
			trigger: $container,
			// The button sits at the foot of the sidebar, so the menu goes up from it.
			side: "top",
			options: [
				{
					group: "",
					options: [
						{
							name: "settings",
							label: __("Settings"),
							icon: "settings",
							onclick: function () {
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
							// The dock holds an app's own modules, so a module in no app has no
							// dock to arrange and its items region is always empty. Offering the
							// picker there would ask the user to curate nothing. This is evaluated
							// on every open, because the menu re-reads conditions each time it
							// comes up, so it tracks the shell you are in rather than the one the
							// menu was built in.
							condition: () => !!me.get_sidebar_app(),
							onclick: function () {
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
							onclick: function () {
								frappe.ui.toolbar.clear_cache();
							},
						},
					],
				},
				// Logout is a section of its own, which is the rule the divider row here used to
				// draw by hand.
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
			],
			on_open: () => $btn.addClass("user-menu-active"),
			on_close: () => $btn.removeClass("user-menu-active"),
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

	// Find the item the current URL belongs to and make it `active_item`, or null when none does.
	// Returns whether any did.
	//
	// Every item is scored by `route_claim` and the strongest claim wins. The URL is read once
	// rather than per item, since it is the same for all of them.
	is_route_in_sidebar() {
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

		// The item lit for the last route is cleared either way. Kept when nothing claims the new
		// route, it would point at a page you have left: ToDo stayed lit after opening something
		// the sidebar does not list.
		if (this.active_item) this.active_item.removeClass("active-sidebar");
		this.active_item = best;
		return !!best;
	}

	set_sidebar_state() {
		this.load_sidebar_state();
		if (this.sidebar_items.length === 0) {
			this.sidebar_expanded = true;
		}

		this.expand_sidebar();
	}

	// Where the panel starts.
	//
	// Below md it is a drawer, and a drawer starts shut. On a desktop the panel is always on
	// screen, either whole or as its icon rail, and which of the two is the viewer's own choice,
	// kept in this browser (see remember_collapsed) so it survives a reload and a change of module.
	//
	// This used to have to wait. The answer was read off the rail -- a docked app opened with the
	// rail alone and the panel at nothing -- and the rail is only knowable once the module has
	// resolved and a page is on screen to allow it, so a cold load into a document had to draw the
	// panel closed, settle later, and open it if it turned out there was no rail. `panel_can_close`
	// asks the window's width now, which is answerable at any moment, so there is nothing left to
	// settle and nothing that has to be drawn in a state it will not keep.
	load_sidebar_state() {
		this.sidebar_expanded = !this.panel_can_close() && !this.remembered_collapsed();
	}

	// The rail is a per-viewer convenience, so it lives in the browser and nowhere else. Storage
	// can be missing or refuse (a private window, blocked site data), and then the panel simply
	// opens whole, which is the state it would have been in anyway.
	remembered_collapsed() {
		try {
			return localStorage.getItem("desk-sidebar-collapsed") === "1";
		} catch {
			return false;
		}
	}

	remember_collapsed(collapsed) {
		if (this.panel_can_close()) return;
		try {
			localStorage.setItem("desk-sidebar-collapsed", collapsed ? "1" : "0");
		} catch {
			// nothing to keep it in; it lasts until the next reload
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
	// These are here because the dock no longer carries them. It used to hold four things besides
	// navigation, and all four moved: notifications, background tasks and the user button to the
	// sidebar, and the apps door to the switcher's "All apps". Search had nowhere else to go --
	// the desk's own full-search button is dead markup -- so it moved here too, and this is the
	// only search affordance the desk has.
	//
	// These are full-width rows rather than an icon strip, so the band uses the sidebar's own
	// vocabulary instead of the dock's ghost-icon treatment in a 220px panel, and search stays
	// legible. Nothing new is built for it: each row is the same icon-plus-label item every
	// sidebar link is.
	//
	// The band sits directly under the header, above the module's own items, behind a divider,
	// rather than after the user button where the generic add-item helper put these two.
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
				if (!this.sidebar_expanded || !this.panel_can_close()) return;
				// A sidebar panel -- notifications, background tasks -- is mounted beside the
				// panel rather than inside it, but a click in one is still a click on the
				// sidebar's own furniture.
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

		this.sidebar_header.toggle_width(this.sidebar_expanded);
		this.label_rail();
		$("body").toggleClass("sidebar-collapsed", !this.sidebar_expanded);
		$(document).trigger("sidebar-expand", {
			sidebar_expand: this.sidebar_expanded,
		});
	}

	// Words the rail has hidden, said another way. Each row's label becomes its tooltip and its
	// accessible name while only the glyph shows, the way the reference's SidebarItem gives a
	// collapsed row a tooltip; and the arrow says what pressing it will do.
	label_rail() {
		const collapsed = !this.sidebar_expanded;
		const arrow = collapsed ? __("Expand sidebar") : __("Collapse sidebar");
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
		this.remember_collapsed(true);

		this.expand_sidebar();
		if (frappe.is_mobile()) frappe.app.sidebar.prevent_scroll();
	}
	open() {
		this.sidebar_expanded = true;
		this.remember_collapsed(false);
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
	// One rule, `shell_for_route`, and the URL carries its answer, so there is nothing to remember
	// between routes and nothing to resolve twice. What replaced the ladder that used to live here
	// is the server: `bootinfo.canonical_shell` says where each entity opens, worked out once for
	// this user, so the desk no longer has to guess from link data while a doctype's meta loads
	// and then correct itself when it arrives.
	//
	// The highlight on the active item is separate and stays route-aware, in
	// set_active_workspace_item().
	set_workspace_sidebar() {
		try {
			const route = frappe.get_route();
			const target = this.shell_for_current_route(route);

			if (target && target !== this.current_module) this.select_module(target);
		} catch (e) {
			console.error(e);
		}

		this.set_active_workspace_item();
	}

	// The shell this route should show, including the route that names nothing at all.
	shell_for_current_route(route) {
		// `/desk` itself, which names nothing. The user's own default workspace answers, and its
		// shell is what shows.
		//
		// The ladder this replaces refused to read `User.default_workspace`, because there it
		// would have outranked entity routes too and pinned the sidebar to one workspace whatever
		// you opened. Asking it for the empty route alone has none of that. It is also the only
		// thing left that the sticky in `localStorage` was doing: every other route now carries
		// its shell in the URL, so a reload restores it without anything being remembered.
		if (!route.length) return this.default_shell();

		// The server's map gives every entity the user can read a shell, so `shell_for_route`
		// answers for every real route. What is left is a route naming nothing the map knows,
		// such as a mistyped slug. Stay in the sidebar already on screen rather than showing none.
		// `shell_for_route` itself still says null, so the URL is not given a shell it never had.
		return this.shell_for_route(route) || this.current_module || this.default_shell();
	}

	// Where the desk lands when the route names nothing.
	//
	// The server works this out with the map (`home_shell` in sidebar.py): the user's default
	// workspace, else the shell holding most of what they can reach. The first shell is only for
	// a boot that predates it.
	default_shell() {
		return frappe.boot.home_shell || Object.keys(frappe.boot.module_sidebars || {})[0] || null;
	}

	// The shell the URL names, when it names one this route can be shown in.
	//
	// A shell in the URL is a statement: somebody was standing in that sidebar when the link was
	// made, and following the link should not move them out of it. It is honoured on two
	// conditions, which are the two ways a shell can legitimately show an entity:
	//
	//   the shell lists the entity, which is somebody having put it there on purpose, or
	//   the shell belongs to the same app as the entity's own, which is how the desk already
	//   behaves while you navigate inside one app (see crosses_app).
	//
	// The first is what the whole segment exists for. Clicking `Customer` in the Accounts sidebar
	// should leave you in Accounts, and on this site 190 of 605 doctype links in a sidebar point
	// at an entity whose own shell is a different one. Without this test every one of those would
	// throw you out of the sidebar you just clicked in.
	//
	// Anything else is a URL naming a shell that cannot show what it points at: a stale name
	// after a doctype moved module, a hand-edited link, a shell this user cannot see. The ladder
	// answers those instead, and the URL is corrected rather than obeyed.
	shell_from_url(route) {
		const shell = frappe.router.current_shell;
		if (!shell) return null;

		return this.shell_can_show(shell, route) ? shell : null;
	}

	// Whether `shell` may be the one a URL for `route` names.
	//
	// Two ways, and they are the two ways a shell can legitimately show an entity:
	//
	//   the shell lists the entity, which is somebody having put it there on purpose, or
	//   the shell belongs to the same app as the entity's own, which is how the desk already
	//   behaves while you navigate inside one app (see crosses_app).
	//
	// The first is what the whole thing exists for. Clicking `Customer` in the Accounts sidebar
	// should leave you in Accounts, and on a site with erpnext 190 of 605 doctype links in a
	// sidebar point at an entity whose own shell is a different one. Without the listing test
	// every one of those would throw you out of the sidebar you clicked them in.
	//
	// Everything else fails: a shell this user does not have, a stale name after a doctype moved
	// module, a hand-edited link. Those are corrected rather than obeyed.
	shell_can_show(shell, route) {
		if (!shell || !frappe.boot.module_sidebars?.[shell]) return false;

		const entity = this.entity_from_route(route);
		if (!entity) return false;

		const kind = this.link_type_from_route(route);
		if (this.get_modules_linking(entity, kind).includes(shell)) return true;

		const canonical = this.canonical_shell_for(route, entity);
		return !!canonical && !this.crosses_app(shell, canonical);
	}

	// The shell a URL for this route should name. Three answers, strongest first:
	//
	//   1. the shell the URL already names, when it can show the route. A URL is a statement, and
	//      it has to outrank the sidebar on screen or the back button would rewrite history:
	//      going back to `/desk/accounts/customer` while standing somewhere else would replace
	//      that entry with wherever you happen to be.
	//   2. the shell on screen, when it can show the route. This is what makes the sidebar
	//      survive a navigation: you are in Accounts, you click something Accounts lists, and the
	//      URL that gets written says Accounts.
	//   3. where the route opens on its own, from the map the server resolved.
	//
	// One rule, and both directions use it: building a URL asks what to write, and arriving at
	// one asks whether what is written can stay.
	shell_for_route(route) {
		// A workspace route names a workspace rather than an entity, and which shell holds one is
		// stored on the shell rather than resolved, so it is answered before the three below.
		if (route[0] === "Workspaces" && route.length >= 2) {
			return this.module_for_workspace(route[route.length - 1]);
		}

		const stated = this.shell_from_url(route);
		if (stated) return stated;

		const on_screen = this.current_module;
		if (on_screen && this.shell_can_show(on_screen, route)) return on_screen;

		return this.canonical_shell_for(route);
	}

	// Where an entity opens when nothing states a shell, read straight out of the map the server
	// resolved. It is the ladder's answer without the ladder, so it needs no meta and is final on
	// the first pass.
	//
	// Keyed by kind before name, because entity names are not unique across kinds: `Attendance`
	// is a DocType one shell lists and a Dashboard another lists, so the route has to say which
	// it means.
	canonical_shell_for(route, entity = null) {
		entity = entity || this.entity_from_route(route);
		if (!entity) return null;

		return frappe.boot.canonical_shell?.[this.link_type_from_route(route)]?.[entity] || null;
	}

	// Switch to a shell.
	//
	// It used to remember the choice in `localStorage` so it survived navigation and reload. The
	// URL carries the shell now, which does both better: it survives being shared, it is the same
	// on every device, and two tabs can sit in different shells.
	select_module(module) {
		if (module && module !== this.current_module) {
			frappe.app.sidebar.setup(module);
		}
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

		const shell = this.get_modules_linking(name, "Workspace")[0];
		if (shell) this.select_module(shell);

		const route = frappe.ui.sidebar_item.get_route(
			{ type: "Link", link_type: "Workspace", link_to: name },
			false,
			shell
		);
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

		// Select the shell first, so the sidebar is right when the route lands, then go where the
		// entry points -- which for a row naming a shell is that shell's landing page, the first
		// item in its sidebar (see dock_entry_route).
		//
		// A shell row used to be the exception: it swapped the sidebar and travelled nowhere, on
		// the grounds that the dock's row for a module and the first row of that module's sidebar
		// are not the same destination, and only one of them had been asked for. That held while
		// the dock was a permanent column beside the panel -- you picked a module on the left and
		// then picked a page out of the panel that had just changed next to it.
		//
		// It does not hold now. The dock is an overlay that covers the panel and dismisses itself
		// on the click, so swapping the panel and staying put left you on the page you were already
		// on, with a sidebar you had not asked to read and nothing on screen to say the click had
		// done anything. Going somewhere is the only outcome the gesture can now have.
		if (entry.module) this.select_module(entry.module);
		this.open();

		const route = this.dock_entry_route(entry);
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
			const route = frappe.ui.sidebar_item.get_route(item, false, module);
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
	// Debug helper: explain why this sidebar is shown.
	// Call from the console as `frappe.app.sidebar.explain()`.
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
	// `link_type` narrows the match to one kind of entity. Names are not unique across kinds --
	// `Attendance`, `Project`, `Selling` and `Stock` each name a Dashboard and a DocType on an
	// erpnext and hrms site -- so a caller that knows which one it means has to say, or a shell
	// listing the Dashboard answers for the DocType. The server map is keyed by kind for the same
	// reason (`build_canonical_shells`). Left out, any kind matches, which is what a caller holding
	// only a name gets.
	get_modules_linking(link_to, link_type = null) {
		let modules = [];
		Object.entries(frappe.boot.module_sidebars || {}).forEach(([module, sidebar]) => {
			const lists = (sidebar.items || []).some(
				(item) => item.link_to === link_to && (!link_type || item.link_type === link_type)
			);
			if (lists) modules.push(module);
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
