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

		let items = apps.map((app) => {
			let logo = Array.isArray(app.app_logo_url) ? app.app_logo_url[0] : app.app_logo_url;
			return {
				name: app.app_name,
				label: app.app_title,
				url: app.app_route,
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
	get_public_workspace_items() {
		// `frappe.boot.user_workspaces` is the user's personal selector preference
		// (`User.workspaces`). When set, it is authoritative for the selector and may include
		// private workspaces too, so it drives both. Otherwise fall back to the current app's
		// workspaces plus any public custom (user-created, non-standard) workspaces -- those
		// don't belong to an app's list (a "true custom" workspace has no app), so they'd
		// otherwise never appear. Private ones are auto-listed by `get_private_workspace_items`.
		let user_workspaces = frappe.boot.user_workspaces || [];
		let source;
		if (user_workspaces.length) {
			source = user_workspaces;
		} else {
			// App-associated workspaces (standard and custom) come from the current app's list,
			// so they stay scoped to their app. `frappe.current_app` is set deterministically at
			// routing time (Sidebar.set_current_app), so it reliably reflects the active
			// workspace's app here. App-less custom workspaces belong to no app, so they're added
			// separately here -- otherwise they'd never appear in any selector.
			let app_workspaces = (frappe.current_app && frappe.current_app.workspaces) || [];
			let appless_custom = Object.values(frappe.workspaces || {})
				.filter((workspace) => workspace.public && !workspace.standard && !workspace.app)
				.map((workspace) => workspace.name);
			source = [...new Set([...app_workspaces, ...appless_custom])];
		}

		return source
			.map((name) => frappe.workspaces[frappe.router.slug(name)])
			.filter((workspace) => workspace && !this.is_active_workspace(workspace))
			.map((workspace) => this.workspace_to_item(workspace))
			.filter(Boolean);
	}
	get_private_workspace_items() {
		// when the user has curated a selection, any private workspaces they want are already
		// part of it (rendered above) -- don't auto-append them again
		if ((frappe.boot.user_workspaces || []).length) return [];

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
		let label = workspace.title || workspace.label || workspace.name;
		if (!label) return null;
		let sidebar_name = workspace.name || label;
		return {
			name: label.toLowerCase(),
			label: label,
			// land on the workspace's first sidebar link, falling back to the workspace page
			url: this.get_first_link_route(workspace) || this.workspace_route(workspace),
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
	// The workspace's own desk route -- used when it has no sidebar items to land on.
	workspace_route(workspace) {
		let slug = frappe.router.slug(workspace.name || workspace.title);
		return `/desk/${workspace.public ? slug : "private/" + slug}`;
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
