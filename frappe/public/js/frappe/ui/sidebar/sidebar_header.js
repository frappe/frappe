frappe.ui.SidebarHeader = class SidebarHeader {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.sidebar_wrapper = $(".body-sidebar");
		this.drop_down_expanded = false;
		this.title = this.get_display_title();
		this.dropdown_items = this.build_dropdown_items();
		this.make();
		this.setup_app_switcher();
	}
	// Workspaces shown flat under "Public" / "Private" headings, followed by the Apps section.
	build_dropdown_items() {
		let items = [];

		let public_items = this.get_public_workspace_items();
		if (public_items.length) {
			items.push(...public_items);
		}

		let private_items = this.get_private_workspace_items();
		if (private_items.length) {
			items.push(...private_items);
		}

		let apps_section = this.fetch_apps();
		if (apps_section) items.push(apps_section);

		return items;
	}
	fetch_apps() {
		let apps = (frappe.boot.app_data || []).filter((app) => app.on_apps_screen);
		if (!apps.length) return null;

		let items = apps.map((app) => ({
			name: app.app_name,
			label: app.app_title,
			url: app.app_route,
			icon_url: Array.isArray(app.app_logo_url) ? app.app_logo_url[0] : app.app_logo_url,
		}));

		// always offer a way back to the desktop / apps screen, as the first entry
		items.unshift({
			name: "desktop",
			label: __("Go to Desktop"),
			icon: "grid",
			onClick: () => frappe.set_route("desktop"),
		});

		return {
			name: "apps",
			label: __("Apps"),
			icon: "grid",
			items,
		};
	}
	get_public_workspace_items() {
		let app_workspaces = (frappe.current_app && frappe.current_app.workspaces) || [];

		return app_workspaces
			.map((name) => frappe.workspaces[frappe.router.slug(name)])
			.filter((workspace) => workspace && !this.is_active_workspace(workspace))
			.map((workspace) => this.workspace_to_item(workspace))
			.filter(Boolean);
	}
	get_private_workspace_items() {
		return Object.values(frappe.workspaces || {})
			.filter(
				(workspace) =>
					!workspace.public &&
					workspace.for_user === frappe.session.user &&
					!this.is_active_workspace(workspace)
			)
			.map((workspace) => this.workspace_to_item(workspace))
			.filter(Boolean);
	}
	// The currently shown workspace shouldn't be offered as a switch target.
	is_active_workspace(workspace) {
		if (!workspace) return false;
		let active = frappe.router.slug(this.sidebar.sidebar_title || "");
		return frappe.router.slug(workspace.name || workspace.title || "") === active;
	}
	workspace_to_item(workspace) {
		if (!workspace) return null;
		let label = workspace.title || workspace.label;
		let sidebar_name = workspace.name || label;
		return {
			name: label.toLowerCase(),
			label: label,
			// land on the workspace's first sidebar link, falling back to the workspace page
			url: this.get_first_link_route(workspace) || frappe.utils.generate_route(workspace),
			icon: workspace.icon,
			// switch the sidebar to this workspace (and remember it) alongside navigating
			onClick: () => {
				if (frappe.boot.workspace_sidebar_item[sidebar_name.toLowerCase()]) {
					frappe.app.sidebar.select_sidebar(sidebar_name);
				}
			},
		};
	}
	get_first_link_route(workspace) {
		return frappe.app.sidebar.get_first_sidebar_route(workspace.name || workspace.title);
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
	}
	// Private workspaces are stored as `${title}-${for_user}`; show just the title in the
	// header. Module-generated sidebars have no Workspace entry, so fall back to the raw title.
	get_display_title() {
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

	setup_app_switcher() {
		frappe.ui.create_menu({
			parent: this.wrapper,
			menu_items: this.dropdown_items,
			onShow: this.toggle_active,
			onHide: this.toggle_active,
			onItemClick: this.toggle_active,
		});
	}

	toggle_active(wrapper) {
		$(wrapper).toggleClass("active-sidebar");
		if (!frappe.app.sidebar.sidebar_expanded) {
			$(wrapper).removeClass("active-sidebar");
		}
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
