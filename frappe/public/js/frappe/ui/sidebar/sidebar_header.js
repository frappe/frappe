// Where the rail starts being drawn: `media-breakpoint-up(md)` in dock.scss, in the one place JS
// has to know the same number. Below it there is no rail, and the panel's header is the only
// header on screen.
const RAIL_BREAKPOINT = "(min-width: 768px)";

frappe.ui.SidebarHeader = class SidebarHeader {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.sidebar_wrapper = $(".body-sidebar");
		this.make();
		// A resize can move the menu between the two headers, so follow the query rather than
		// reading it once. `change` fires only when it flips, not on every pixel.
		this.rail_query = window.matchMedia(RAIL_BREAKPOINT);
		this.rail_query.addEventListener("change", () => this.setup_menu());
		this.setup_menu();
	}

	// The module on screen changed, so the header names a different one. The node stays put and
	// only its text is rewritten: the dropdown binds to the element it is given, so a header
	// rebuilt on every navigation would leave its menu pointing at a detached node.
	// `Sidebar.refresh_header` keeps one header for the life of the desk, and this is all it has
	// to change between modules.
	refresh() {
		this.title = this.get_display_title();
		this.set_header_icon();
		this.$header_title.text(__(this.title));
		// The mark is replaced along with the title. Before the header drew one, set_header_icon's
		// result was only ever read by the onboarding widget and a stale icon here could not be
		// seen. Which mark it is depends on whether there is a rail (see get_header_logo), and
		// that can change from one module to the next, so it is re-resolved here too.
		this.$header_logo.html(this.get_header_logo());
		// Whether the app on screen has a rail changes from one module to the next, and with it
		// which header the menu belongs to.
		this.setup_menu();
	}

	// What the header's own menu offers.
	//
	// On a docked app it opens from the rail's header (see menu_on_rail) and offers what concerns
	// the sidebar in front of you, over the way out to the apps screen. Switching between sidebars
	// belongs to the rail while there is one, and arranging the rail belongs to the user menu, so
	// both switcher rows are absent.
	//
	// On a dock-less app there is no rail to switch with, so the header carries the switcher. Two
	// nested rows and nothing more:
	//
	//     Modules  >   the app's navigable modules
	//     Apps     >   every app on the desktop screen, then All apps
	//     ---------
	//     Edit Sidebar
	//     ---------
	//     whatever Navbar Settings holds
	//     Help     >   this page's help links, then the site's help items
	//
	// Nesting both axes keeps it short: the menu stays four rows tall whether the app has two
	// modules or twenty-two. Nothing new was added to the menu component for it, since nesting
	// and sections both existed.
	//
	// The rules between the three blocks are the sections' own: `frappe.ui.Dropdown` draws one
	// between neighbouring groups and drops a group whose rows are all hidden, rule included, so
	// nothing here has to count what is left before placing a divider.
	menu_items() {
		return [
			{ group: "", options: this.switcher_items() },
			{
				group: "",
				options: [
					{
						name: "edit-sidebar",
						label: __("Edit Sidebar"),
						icon: "pencil",
						// Re-run on every open, so it tracks the sidebar you are looking at
						// rather than the one the menu was built in, which is why the header
						// keeps one menu instead of one per module.
						condition: () => !!this.sidebar.current_module,
						// The editor is not in the desk bundle, so load it on click and then
						// open this module's sidebar in it.
						onclick: () =>
							frappe
								.require("arrangement_editor.bundle.js")
								.then(() => new frappe.ui.SidebarManager())
								.catch((e) => {
									console.error(
										"SidebarHeader: failed to load arrangement_editor.bundle.js",
										e
									);
									frappe.ui.toast({
										message: __(
											"Could not open the sidebar editor. Please refresh the page."
										),
										type: "error",
									});
								}),
					},
				],
			},
			{ group: "", options: this.system_items() },
		];
	}

	// Where a Navbar Settings row or a help link points, as menu-row fields.
	//
	// Both kinds are rows the site authored, and either may name a page inside the site or a page
	// outside it. An in-site path stays a plain link: the panel's rows are real anchors, and the
	// desk's own click handler turns a desk path into a route without a reload. Anything on
	// another origin opens in a new tab, which is where these rows have always sent you, and
	// leaves the desk where it was.
	link_fields(url) {
		const external = /^(?:[a-z][a-z0-9+.-]*:)?\/\//i.test(url);
		return external ? { href: url, target: "_blank" } : { href: url };
	}

	// Everything Navbar Settings contributes: its settings rows flat in the menu, and its help
	// rows nested under one "Help" row, the shape the old header dropdown had. The whole block,
	// and the rule above it, is absent when a site has neither.
	//
	// The help row is read afresh on every open because part of it is the help links for the page
	// you are on, and those change with every navigation.
	system_items() {
		const navbar = this.navbar_items();
		// Two sections, either of which may be empty; the row is worth offering only if something
		// is under it.
		const help = this.get_help_siblings();
		if (help.some((section) => section.options.length)) {
			navbar.push({
				name: "help",
				label: __("Help"),
				icon: "info",
				submenu: help,
			});
		}
		return navbar;
	}

	// The rows a site put on its own menu, read from `Navbar Settings.settings_dropdown`: the
	// standard items an app ships through the `standard_navbar_items` hook, plus anything a user
	// added by hand. This is where they used to sit, before the header lost its dropdown; for a
	// while after that they hung off the user menu at the foot of the sidebar instead.
	//
	// An item is a route or an action, the two kinds Navbar Settings offers. Its `condition` is a
	// stored expression rather than a function, so it is wrapped in one the menu can call: the
	// menu re-reads conditions on every open, and an item that only applies to some sites stays
	// hidden on the rest.
	navbar_items() {
		return (frappe.boot.navbar_settings?.settings_dropdown || [])
			.filter((item) => !item.hidden)
			.map((item) => {
				const row = {
					name: item.name,
					label: __(item.item_label),
					icon: item.icon,
				};
				if (item.condition) {
					row.condition = () => frappe.utils.eval(item.condition);
				}
				if (item.item_type === "Route") {
					Object.assign(row, this.link_fields(item.route));
				} else if (item.item_type === "Action") {
					row.onclick = () => frappe.utils.eval(item.action);
				}
				return row;
			});
	}

	// The switcher, present only where there is no rail to do the switching.
	//
	// Rows name the axis, not the current location: "Modules", not "Stock". A row naming where
	// you are reads as a status line, and a menu row is something you press.
	switcher_items() {
		const sidebar = this.sidebar;
		// The rail switches on a docked app, so the menu carries no switcher there. The one row it
		// keeps is the way out to the apps screen, because on a docked app this menu opens from the
		// rail's header -- which was that link before the menu moved onto it.
		if (sidebar.dock_enabled()) return [this.all_apps_item()];

		const items = [];
		const modules = sidebar.app_modules(sidebar.get_sidebar_app());

		// Absent when the app has one module, following the rail's own refusal to draw a rail of
		// one: an item permanently active with no alternatives is a switcher that cannot switch.
		// Helpdesk, Insights, Drive, Wiki and Newsletter each ship exactly one module, so for most
		// dock-less apps this switcher is an app switcher.
		if (modules.length > 1) {
			items.push({
				name: "switch-module",
				label: __("Modules"),
				icon: "layout-grid",
				submenu: modules.map((shell) => ({
					name: `module-${shell}`,
					label: __(frappe.boot.module_sidebars[shell]?.label || shell),
					icon: frappe.boot.module_sidebars[shell]?.header_icon,
					onclick: () => sidebar.open_module(shell),
				})),
			});
		}

		items.push({
			name: "switch-app",
			label: __("Apps"),
			icon: "layout-dashboard",
			// Every app on the desktop screen, docked ones included. Excluding them would strand
			// a user on a dock-less app with no route to ERPNext. Two sections, so the way out to
			// the apps screen sits under a rule of the panel's own drawing.
			submenu: [
				{
					group: "",
					options: (frappe.boot.app_data || [])
						.filter((app) => app.on_apps_screen)
						.sort((a, b) => (a.sequence_id ?? 100) - (b.sequence_id ?? 100))
						.map((app) => ({
							name: `app-${app.app_name}`,
							label: __(app.app_title || app.app_name),
							// An app's mark is its own logo, which no icon name stands in for.
							image: Array.isArray(app.app_logo_url)
								? app.app_logo_url[0]
								: app.app_logo_url,
							onclick: () => {
								const route = sidebar.app_landing_route(app) || "/desk";
								route.startsWith("http")
									? window.open(route, "_blank")
									: frappe.set_route(route);
							},
						})),
				},
				{
					group: "",
					options: [this.all_apps_item()],
				},
			],
		});

		return items;
	}

	// The apps screen, which is where both shells' headers have always pointed.
	all_apps_item() {
		return {
			name: "all-apps",
			label: __("All apps"),
			icon: "grid-2x2",
			href: "/desk",
		};
	}

	// Which header opens the menu: the rail's while there is a rail, the panel's otherwise.
	//
	// A docked app's menu belongs to the rail. The rail is the app-level shell there and the panel
	// under it is one sidebar's worth of rows, so one menu with a trigger on each of them offered
	// the same rows twice, one directly above the other.
	//
	// Below md no rail is drawn at all (dock.scss), so the panel's header takes the menu back the
	// same way it keeps the user button and the standard items band. `dock_enabled` alone is not
	// enough for the same reason: a page may keep the panel and suppress the rail, and this is the
	// pair Dock.refresh tests before drawing one.
	menu_on_rail() {
		return (
			this.sidebar.dock_enabled() &&
			this.sidebar.page_allows_dock() &&
			this.rail_query.matches
		);
	}

	// Put the menu on the panel's header, or take it off, to match menu_on_rail(). The rail hangs
	// its own copy on its header (see Dock.setup_header_menu); this owns the panel's, and creating
	// and destroying it is what keeps a header that opens nothing from opening something.
	setup_menu() {
		const on_panel = !this.menu_on_rail();
		if (on_panel === !!this.menu) return;
		if (on_panel) {
			this.menu = this.attach_menu(this.wrapper);
		} else {
			this.menu.destroy();
			this.menu = null;
			// destroy() takes the listeners off but leaves the menu-button attributes it set, and
			// a row that no longer opens anything must not still say it does.
			this.wrapper.removeAttr("aria-haspopup aria-expanded");
		}
	}

	// Hang this header's menu on an element. The rail's header calls it for a copy of its own.
	//
	// Each element gets its own dropdown, created once and never rebuilt: it binds to the node it
	// is given, and takes its rows from a function it calls on every open, so one dropdown per
	// element covers every module the desk goes on to show.
	attach_menu(wrapper) {
		const $wrapper = $(wrapper);
		const menu = new frappe.ui.Dropdown({
			trigger: $wrapper,
			options: () => this.menu_items(),
			on_open: () => this.toggle_active($wrapper, true),
			on_close: () => this.toggle_active($wrapper, false),
		});
		return menu;
	}

	// The header shows the open state while its menu is up. The rail's header is always on screen
	// and simply toggles; the panel's is only there when the panel is, and a highlight left on a
	// header that has gone would be waiting on it when it came back.
	toggle_active(wrapper, active) {
		// Either header opens from its whole row, and it is the header that shows the open state,
		// so resolve up to it: `closest` returns the header itself when that is what was passed.
		const $wrapper = $(wrapper).closest(".shell-header").length
			? $(wrapper).closest(".shell-header")
			: $(wrapper);
		$wrapper.toggleClass("active-sidebar", active);
		if ($wrapper.closest(".body-sidebar").length && !this.sidebar.sidebar_expanded) {
			$wrapper.removeClass("active-sidebar");
		}
	}
	// What goes under the header's "Help" row: the help links registered for the page you are on,
	// then the site's own help items from `Navbar Settings.help_dropdown`.
	//
	// The two are sections rather than a list with a divider row in it. The panel rules between
	// them, and drops the rule along with whichever section is empty -- so a page that carries
	// links on a site that carries none no longer ends the menu in a rule, which the divider row
	// had to be trimmed by hand to avoid.
	get_help_siblings() {
		const site_items = (frappe.boot.navbar_settings?.help_dropdown || [])
			.filter((element) => !element.hidden)
			.filter((element) => !element.action?.includes("frappe.ui.toolbar.show_shortcuts"))
			.filter((element) => !element.condition || frappe.utils.eval(element.condition))
			.map((element) => {
				const row = { name: element.name, label: __(element.item_label) };
				if (element.item_type === "Route") {
					Object.assign(row, this.link_fields(element.route));
				}
				if (element.item_type === "Action") {
					row.onclick = () => frappe.utils.eval(element.action);
				}
				return row;
			});

		return [
			{ group: "", options: this.get_custom_help_links() },
			{ group: "", options: site_items },
		];
	}

	get_custom_help_links() {
		let route = frappe.get_route_str();
		let breadcrumbs = route.split("/");

		let links = [];
		for (let i = 0; i < breadcrumbs.length; i++) {
			let r = route.split("/", i + 1);
			let key = r.join("/");
			let help_links = frappe.help.help_links[key] || [];
			links = $.merge(links, help_links);
		}
		// Registered links are `{ label, url }` pairs, and every one of them points outside the
		// site, at the docs.
		return links.map((link) => ({
			label: __(link.label),
			...this.link_fields(link.url),
		}));
	}

	make() {
		$(".sidebar-header").remove();
		this.title = this.get_display_title();
		this.set_header_icon();
		$(
			frappe.render_template("sidebar_header", {
				workspace_title: this.title,
				header_icon: this.get_header_logo(),
			})
		).prependTo(this.sidebar_wrapper);
		this.wrapper = $(".sidebar-header");
		this.$header_title = this.wrapper.find(".header-title");
		this.$header_logo = this.wrapper.find(".header-logo");
		this.$drop_icon = this.wrapper.find(".drop-icon");
		this.toggle_width(this.sidebar.sidebar_expanded);
	}
	// The header names the module whose sidebar is on screen, because the sidebar belongs to a
	// module. It used to show the owning app's title and fall back to the module only when there
	// was no app, which meant every module in an app shared one header: "Frappe Framework"
	// whether you were in Core, Website or Integrations.
	//
	// The app is still identifiable from the logo and the dock, so the header names the module.
	// `label` is the Sidebar's title, which an app or a customization may override, falling back
	// to the module name.
	get_display_title() {
		return (
			this.sidebar.sidebar_data?.label ||
			this.sidebar.current_module ||
			this.sidebar.get_sidebar_app()?.app_title
		);
	}
	// The module's own icon, used by the onboarding widget: an authored `header_icon`, otherwise a
	// letter icon from its title, the same pair the rail uses. There is no app-logo fallback,
	// because an app's logo was never this module's icon and the one used was whichever app
	// happened to be installed first.
	set_header_icon() {
		const sidebar = this.sidebar.sidebar_data;
		this.header_icon = sidebar?.header_icon
			? frappe.utils.icon(sidebar.header_icon, "md")
			: frappe.utils.desktop_icon(this.title || "", "gray", "sm");
	}

	// The mark the header draws.
	//
	// On a docked app the rail carries the app's logo one column to the left, so the header is
	// free to mark the module its title names, and two logos side by side would say the same
	// thing twice.
	//
	// A dock-less app has no rail, so nothing on screen says which app you are in -- the header
	// title names the module, and the title bar names the page. There the header takes the mark
	// the rail would have carried, which is the app's own logo. The module keeps the title, so
	// between the two the header still says both.
	//
	// `header_icon` is left alone either way: it is the module's icon, and the onboarding widget
	// reads it as one.
	get_header_logo() {
		if (this.sidebar.dock_enabled()) return this.header_icon;
		const app = frappe.utils.app_logo(this.sidebar.get_sidebar_app());
		return app ? app.icon : this.header_icon;
	}

	setup_hover() {
		$(".sidebar-header").on("mouseover", function (event) {
			if ($(this).parent().hasClass("active-sidebar")) return;
			$(this).addClass("hover");
		});

		$(".sidebar-header").on("mouseleave", function () {
			$(this).removeClass("hover");
		});
	}

	// Bind or drop the header's hover, following whether the panel is on screen. The padding this
	// used to set from here is the stylesheet's now: it was there to pull the title flush while the
	// collapsed sidebar was a narrow strip, and a collapsed sidebar has not been on screen at all
	// since the rail took that job.
	toggle_width(expand) {
		if (!expand) {
			$(this.wrapper[0]).off("mouseleave");
			$(this.wrapper[0]).off("mouseover");
		} else {
			this.setup_hover();
		}
	}
};
