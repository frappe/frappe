frappe.ui.SidebarHeader = class SidebarHeader {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.sidebar_wrapper = $(".body-sidebar");
		this.make();
		this.setup_menu();
	}

	// The module on screen changed, so the header names a different one. The node stays put and
	// only its text is rewritten: `frappe.ui.create_menu` binds to the element it is given and
	// registers a document-level listener per call, so a header rebuilt on every navigation would
	// leave its menu pointing at a detached node and add a listener each time.
	// `Sidebar.refresh_header` keeps one header for the life of the desk, and this is all it has
	// to change between modules.
	refresh() {
		this.title = this.get_display_title();
		this.set_header_icon();
		this.$header_title.text(__(this.title));
		this.refresh_menu();
	}

	// The menu's rows are replaced rather than the menu rebuilt.
	//
	// `frappe.ui.menu` re-runs each row's `condition` on every open, but the list is the array it
	// was given at construction, so the switcher's rows, and the modules and apps nested under
	// them, would be whichever app was on screen when the desk booted. Rebuilding the menu would
	// bind a second click handler to the same header and register another document-level
	// listener, which is what keeping one header for the life of the desk avoids. Replacing the
	// array does neither.
	refresh_menu() {
		if (this.menu) this.menu.menu_items = this.menu_items();
	}

	// What the header's own menu offers.
	//
	// On a docked app it offers only what concerns the sidebar in front of you. Switching between
	// sidebars belongs to the rail while there is one, and arranging the rail belongs to the user
	// menu, so the menu is one item long and both switcher rows are absent. A docked app's header
	// is unchanged.
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
	// modules or twenty-two. Nothing new was added to the menu primitive for it, since nesting,
	// dividers and group headings all existed.
	menu_items() {
		const switching = this.switcher_items();
		const system = this.system_items();
		return [
			...switching,
			...(switching.length ? [{ is_divider: true }] : []),
			{
				name: "edit-sidebar",
				label: __("Edit Sidebar"),
				icon: "pencil",
				// Re-run on every open, so it tracks the sidebar you are looking at rather than
				// the one the menu was built in, which is why the header keeps one menu instead
				// of one per module.
				condition: () => !!this.sidebar.current_module,
				// The editor is not in the desk bundle, so load it on click and then open
				// this module's sidebar in it.
				onClick: () =>
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
			...(system.length ? [{ is_divider: true }, ...system] : []),
		];
	}

	// Everything Navbar Settings contributes: its settings rows flat in the menu, and its help
	// rows nested under one "Help" row, the shape the old header dropdown had. The whole block
	// is absent, divider included, when a site has neither.
	//
	// The help row is rebuilt with the rest of the menu because part of it is the help links for
	// the page you are on, and `Sidebar.refresh_header` runs on every navigation.
	system_items() {
		const navbar = this.navbar_items();
		const help = this.get_help_siblings();
		if (help.length) {
			navbar.push({
				name: "help",
				label: __("Help"),
				icon: "info",
				items: help,
			});
		}
		return navbar;
	}

	// The rows a site put on its own menu, read from `Navbar Settings.settings_dropdown`: the
	// standard items an app ships through the `standard_navbar_items` hook, plus anything a user
	// added by hand. This is where they used to sit, before the header lost its dropdown; for a
	// while after that they hung off the user menu at the foot of the sidebar instead.
	//
	// An item is a route or an action, the two kinds Navbar Settings offers. Its `condition` is
	// passed through untouched, so `frappe.ui.menu` re-runs it on every open and an item that
	// only applies to some sites stays hidden on the rest.
	navbar_items() {
		return (frappe.boot.navbar_settings?.settings_dropdown || [])
			.filter((item) => !item.hidden)
			.map((item) => {
				const row = {
					name: item.name,
					label: __(item.item_label),
					icon: item.icon,
					condition: item.condition,
				};
				if (item.item_type === "Route") {
					row.url = item.route;
				} else if (item.item_type === "Action") {
					row.onClick = () => frappe.utils.eval(item.action);
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
		if (sidebar.dock_enabled()) return [];

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
				items: modules.map((shell) => ({
					name: `module-${shell}`,
					label: frappe.boot.module_sidebars[shell]?.label || shell,
					icon: frappe.boot.module_sidebars[shell]?.header_icon,
					onClick: () => sidebar.open_module(shell),
				})),
			});
		}

		items.push({
			name: "switch-app",
			label: __("Apps"),
			icon: "layout-dashboard",
			// Every app on the desktop screen, docked ones included. Excluding them would strand
			// a user on a dock-less app with no route to ERPNext.
			items: [
				...(frappe.boot.app_data || [])
					.filter((app) => app.on_apps_screen)
					.sort((a, b) => (a.sequence_id ?? 100) - (b.sequence_id ?? 100))
					.map((app) => ({
						name: `app-${app.app_name}`,
						label: app.app_title || app.app_name,
						icon_url: Array.isArray(app.app_logo_url)
							? app.app_logo_url[0]
							: app.app_logo_url,
						onClick: () => {
							const route = sidebar.app_landing_route(app) || "/desk";
							route.startsWith("http")
								? window.open(route, "_blank")
								: frappe.set_route(route);
						},
					})),
				{ is_divider: true },
				{ name: "all-apps", label: __("All apps"), icon: "grid-2x2", url: "/desk" },
			],
		});

		return items;
	}

	setup_menu() {
		this.menu = frappe.ui.create_menu({
			parent: this.wrapper,
			menu_items: this.menu_items(),
			onShow: this.toggle_active,
			onHide: this.toggle_active,
			onItemClick: this.toggle_active,
		});
	}

	// The header shows the open state while its menu is up, except when the sidebar is collapsed
	// to icons, where there is no header to highlight.
	toggle_active(wrapper) {
		$(wrapper).toggleClass("active-sidebar");
		if (!frappe.app.sidebar.sidebar_expanded) {
			$(wrapper).removeClass("active-sidebar");
		}
	}
	// What goes under the header's "Help" row: the help links registered for the page you are on,
	// then a divider, then the site's own help items from `Navbar Settings.help_dropdown`.
	get_help_siblings() {
		let help_dropdown_items = [];

		let custom_help_links = this.get_custom_help_links();

		help_dropdown_items = custom_help_links.concat(help_dropdown_items);

		(frappe.boot.navbar_settings?.help_dropdown || []).forEach((element) => {
			if (element.hidden) return;
			if (element.action?.includes("frappe.ui.toolbar.show_shortcuts")) return;
			if (element.condition && !frappe.utils.eval(element.condition)) return;
			let dropdown_children = {
				name: element.name,
				label: element.item_label,
			};
			if (element.item_type === "Route") {
				dropdown_children.url = element.route;
			}
			if (element.item_type === "Action") {
				dropdown_children.onClick = function () {
					frappe.utils.eval(element.action);
				};
			}
			help_dropdown_items.push(dropdown_children);
		});

		// The divider `get_custom_help_links` leaves behind separates the page's links from the
		// site's items. With nothing after it there is nothing to separate, and a menu ending in
		// a rule looks like it lost its last row.
		if (help_dropdown_items.at(-1)?.is_divider) help_dropdown_items.pop();

		return help_dropdown_items;
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
		if (links.length) {
			links.push({ is_divider: true });
		}
		return links;
	}

	make() {
		$(".sidebar-header").remove();
		this.title = this.get_display_title();
		this.set_header_icon();
		$(
			frappe.render_template("sidebar_header", {
				workspace_title: this.title,
			})
		).prependTo(this.sidebar_wrapper);
		this.wrapper = $(".sidebar-header");
		this.$header_title = this.wrapper.find(".header-title");
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

	setup_hover() {
		$(".sidebar-header").on("mouseover", function (event) {
			if ($(this).parent().hasClass("active-sidebar")) return;
			$(this).addClass("hover");
		});

		$(".sidebar-header").on("mouseleave", function () {
			$(this).removeClass("hover");
		});
	}

	toggle_width(expand) {
		if (!expand) {
			$(this.wrapper[0]).off("mouseleave");
			$(this.wrapper[0]).off("mouseover");
			this.wrapper.css("padding-left", "0px");
			this.wrapper.css("padding-right", "0px");
		} else {
			this.setup_hover();
			this.wrapper.css("padding-left", "8px");
			this.wrapper.css("padding-right", "8px");
		}
	}
};
