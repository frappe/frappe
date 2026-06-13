frappe.ui.SidebarHeader = class SidebarHeader {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.sidebar_wrapper = $(".body-sidebar");
		this.drop_down_expanded = false;
		this.title = this.sidebar.sidebar_title;
		this.dropdown_items = this.build_dropdown_items();
		this.make();
		this.setup_app_switcher();
	}
	// Workspaces shown flat under "Public" / "Private" headings, followed by the Apps section.
	build_dropdown_items() {
		let items = [];

		let public_items = this.get_public_workspace_items();
		if (public_items.length) {
			items.push({ group: __("Public") }, ...public_items);
		}

		let private_items = this.get_private_workspace_items();
		if (private_items.length) {
			items.push({ group: __("Private") }, ...private_items);
		}

		let apps_section = this.fetch_apps();
		if (apps_section) items.push(apps_section);

		return items;
	}
	fetch_apps() {
		let apps = (frappe.boot.app_data || []).filter((app) => app.on_apps_screen);
		if (!apps.length) return null;

		return {
			name: "apps",
			label: __("Apps"),
			icon: "grid",
			items: apps.map((app) => ({
				name: app.app_name,
				label: app.app_title,
				url: app.app_route,
				icon_url: Array.isArray(app.app_logo_url) ? app.app_logo_url[0] : app.app_logo_url,
			})),
		};
	}
	get_public_workspace_items() {
		let workspaces_not_to_show = ["My Workspaces"];
		let app_workspaces = (frappe.current_app && frappe.current_app.workspaces) || [];

		return app_workspaces
			.filter((name) => !workspaces_not_to_show.includes(name))
			.map((name) => this.workspace_to_item(frappe.workspaces[frappe.router.slug(name)]))
			.filter(Boolean);
	}
	get_private_workspace_items() {
		return Object.values(frappe.workspaces || {})
			.filter((workspace) => !workspace.public && workspace.for_user === frappe.session.user)
			.map((workspace) => this.workspace_to_item(workspace))
			.filter(Boolean);
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
		let key = (workspace.name || workspace.title || "").toLowerCase();
		let sidebar = frappe.boot.workspace_sidebar_item[key];
		if (!sidebar) return null;

		for (let item of sidebar.items || []) {
			let route = frappe.ui.sidebar_item.get_route(item);
			if (route) return route;
		}
		return null;
	}
	get_icon_for_menu_item(icon, item) {
		if (frappe.utils.get_desktop_icon(icon.label, frappe.boot.desktop_icon_style)) {
			item.icon_url = frappe.utils.get_desktop_icon(
				icon.label,
				frappe.boot.desktop_icon_style
			);
		} else {
			item.icon_html = frappe.utils.desktop_icon(icon.label, "gray", "sm");
		}
	}
	build_folder_map(desktop_icons) {
		const folder_map = {};
		const sibling_icons = [];
		if (!frappe.current_app) return;
		this.sort_icons(desktop_icons);
		desktop_icons.forEach((icon) => {
			if (
				icon.link_type != "External" &&
				icon.app == frappe.current_app.app_name &&
				!icon.hidden
			) {
				if (icon.icon_type === "Folder" && !folder_map[icon.label]) {
					folder_map[icon.label] = [];
				}

				if (icon.parent_icon) {
					icon.url = frappe.utils.get_route_for_icon(icon);
					if (folder_map[icon.parent_icon]) folder_map[icon.parent_icon].push(icon);
				}
				sibling_icons.push(icon);
			}
		});

		return {
			folder_map: folder_map,
			sibling_icons: sibling_icons,
		};
	}
	sort_icons(desktop_icons) {
		let write = 0;
		for (let i = 0; i < desktop_icons.length; i++) {
			if (desktop_icons[i].icon_type === "Folder") {
				const item = desktop_icons.splice(i, 1)[0];
				desktop_icons.splice(write, 0, item);
				write++;
			}
		}
		return desktop_icons;
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
	set_header_icon() {
		let workspace = frappe.workspaces[frappe.router.slug(this.sidebar.sidebar_title)];
		if (workspace?.icon) {
			this.header_icon = frappe.utils.icon(workspace.icon, "md");
		} else {
			this.header_icon = `<img src=${this.get_default_icon()}></img>`;
		}
	}
	get_default_icon() {
		return frappe.boot.app_data[0].app_logo_url;
	}
	get_desktop_icon_by_label(title, filters) {
		if (!filters) {
			return frappe.boot.desktop_icons.find((f) => f.label === title && f.hidden != 1);
		} else {
			return frappe.boot.desktop_icons.find((f) => {
				return (
					f.label === title &&
					Object.keys(filters).every((key) => f[key] === filters[key]) &&
					f.hidden != 1
				);
			});
		}
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
