frappe.ui.SidebarHeader = class SidebarHeader {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.sidebar_wrapper = $(".body-sidebar");
		this.drop_down_expanded = false;
		this.title = this.get_display_title();
		// with the dock active it owns workspace switching, so the header dropdown drops the inline
		// selector list (the dock has it); the workspace picker dialog is added below in both modes
		this.dock_active = sidebar.workspace_dock_enabled();
		this.dropdown_items = this.build_dropdown_items();
		this.make();
	}
	// Workspaces (the shared selector set, owned by Sidebar) then the Apps section, and finally the
	// "My Workspaces" picker dialog -- the same entry as the user menu, so it's reachable here too.
	build_dropdown_items() {
		let items = this.dock_active ? [] : this.sidebar.get_workspace_selector_items();

		let apps_section = this.fetch_apps();
		if (apps_section) items.push(apps_section);
		items.push({
			name: "workspace-selector",
			label: __("Manage Dock"),
			icon: "monitor",
			onClick: () => new frappe.ui.DockManager(),
		});

		return items;
	}
	fetch_apps() {
		let apps = (frappe.boot.app_data || []).filter((app) => app.on_apps_screen);
		if (!apps.length) return null;

		let items = apps.map((app) => {
			let logo = Array.isArray(app.app_logo_url) ? app.app_logo_url[0] : app.app_logo_url;
			return {
				name: app.app_name,
				label: app.app_title,
				// an app that ships no workspaces has no declared route either -- it lands on its
				// first module sidebar instead (see app_landing_route)
				url: this.sidebar.app_landing_route(app),
				icon_url: logo,
				// no logo declared -> render an alphabet icon, matching the desktop apps screen
				icon_html: logo
					? undefined
					: frappe.utils.desktop_icon(app.app_title, "gray", "sm", "Solid"),
			};
		});

		return {
			name: "apps",
			label: __("Apps"),
			icon: "layout-grid",
			items,
		};
	}
	get_help_siblings() {
		const navbar_settings = frappe.boot.navbar_settings;
		let help_dropdown_items = [];

		let custom_help_links = this.get_custom_help_links();

		help_dropdown_items = custom_help_links.concat(help_dropdown_items);

		navbar_settings.help_dropdown.forEach((element) => {
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
		this.set_header_icon();
		$(
			frappe.render_template("sidebar_header", {
				workspace_title: this.title,
				header_icon: this.header_icon,
				header_bg_color: this.header_stroke_color,
			})
		).prependTo(this.sidebar_wrapper);
		this.wrapper = $(".sidebar-header");
		this.$header_title = this.wrapper.find(".header-title");
		this.$drop_icon = this.wrapper.find(".drop-icon");
		this.toggle_width(this.sidebar.sidebar_expanded);
	}
	// The header shows the app the current sidebar belongs to. Custom / app-less / module sidebars
	// have no owning app, so fall back to the workspace title (private workspaces are stored as
	// `${title}-${for_user}`; show just the title).
	get_display_title() {
		let app = this.sidebar.get_sidebar_app();
		if (app) return app.app_title;

		let workspace = frappe.workspaces[frappe.router.slug(this.sidebar.sidebar_title)];
		if (workspace && !workspace.public && workspace.for_user) {
			return workspace.title;
		}
		return this.sidebar.sidebar_title;
	}
	set_header_icon() {
		let workspace = frappe.workspaces[frappe.router.slug(this.sidebar.sidebar_title)];
		if (this.sidebar.sidebar_data?.from_module) {
			// auto-generated module sidebars have no real icon; render a letter icon from the
			// title (matching the desktop apps screen) instead of the default app logo.
			this.header_icon = frappe.utils.desktop_icon(this.sidebar.sidebar_title, "gray", "sm");
		} else if (workspace?.icon) {
			this.header_icon = frappe.utils.icon(workspace.icon, "md");
		} else {
			this.header_icon = `<img src=${this.get_default_icon()}></img>`;
		}
	}
	get_default_icon() {
		return frappe.boot.app_data[0].app_logo_url;
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
