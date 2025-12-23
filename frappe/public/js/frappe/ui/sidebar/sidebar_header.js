frappe.ui.SidebarHeader = class SidebarHeader {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.sidebar_wrapper = $(".body-sidebar");
		this.drop_down_expanded = false;
		this.title = this.sidebar.sidebar_title;
		const me = this;
		this.sibling_workspaces = this.fetch_sibling_workspaces();
		this.dropdown_items = [
			{
				name: "workspaces",
				label: "Workspaces",
				icon: "wallpaper",
				condition: function () {
					return me.sibling_workspaces && me.sibling_workspaces.length > 0;
				},
				items: this.sibling_workspaces,
			},
			{
				name: "desktop",
				label: __("Desktop"),
				icon: "layout-grid",
				onClick: function (el) {
					frappe.set_route("/desk");
				},
			},
			{
				name: "edit-sidebar",
				label: __("Edit Sidebar"),
				icon: "edit",
				onClick: function () {
					me.sidebar.editor.toggle();
				},
			},
			{
				name: "website",
				label: __("Website"),
				icon: "web",
				onClick: function () {
					window.open(window.location.origin);
				},
			},
		];
		if (frappe.boot.desk_settings.notifications) {
			this.dropdown_items.push({
				name: "help",
				label: "Help",
				icon: "info",
				items: this.get_help_siblings(),
			});
		}
		this.make();
		this.setup_app_switcher();
		this.populate_dropdown_menu();
		this.setup_select_options();
	}
	fetch_sibling_workspaces() {
		let sibling_workspaces = [];
		if (frappe.current_app) {
			let workspaces = [...frappe.current_app.workspaces];
			workspaces.splice(workspaces.indexOf(this.title), 1);
			workspaces.forEach((w) => {
				let item = {
					name: w.toLowerCase(),
					label: w,
					icon: "wallpaper",
					url: frappe.utils.generate_route({
						type: "Workspace",
						route: frappe.router.slug(w),
					}),
				};
				sibling_workspaces.push(item);
			});
			return sibling_workspaces;
		}
	}

	get_help_siblings() {
		const navbar_settings = frappe.boot.navbar_settings;
		let help_dropdown_items = [];

		let custom_help_links = this.get_custom_help_links();

		help_dropdown_items = custom_help_links.concat(help_dropdown_items);

		navbar_settings.help_dropdown.forEach((element) => {
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
		$(".sidebar-header-menu").remove();
		this.set_header_icon();
		$(
			frappe.render_template("sidebar_header", {
				workspace_title: this.title,
				header_icon: this.header_icon,
				header_bg_color: this.header_stroke_color,
			})
		).prependTo(this.sidebar_wrapper);
		this.wrapper = $(".sidebar-header");
		this.dropdown_menu = this.wrapper.find(".sidebar-header-menu");
		this.$header_title = this.wrapper.find(".header-title");
		this.$drop_icon = this.wrapper.find(".drop-icon");
	}
	set_header_icon() {
		let desktop_icon = this.get_desktop_icon_by_label(this.sidebar.sidebar_title);
		let desktop_icon_url =
			desktop_icon && frappe.utils.get_desktop_icon(desktop_icon.label, "solid");
		if (desktop_icon_url) {
			this.header_icon = desktop_icon_url;
			this.header_icon = `<img src=${this.header_icon}></img>`;
		} else if (desktop_icon && desktop_icon.logo_url) {
			this.header_icon = desktop_icon.logo_url;
			this.header_icon = `<img src=${this.header_icon}></img>`;
		} else if (this.sidebar.sidebar_data) {
			this.header_icon = this.sidebar.sidebar_data.header_icon;
			this.header_icon = frappe.utils.icon(
				this.header_icon,
				"lg",
				"",
				"",
				"",
				false,
				`var(${this.header_bg_color})`
			);
		} else {
			this.header_icon = this.get_default_icon();
			this.header_icon = `<img src=${this.header_icon}></img>`;
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

	populate_dropdown_menu() {
		const me = this;
		this.dropdown_items.forEach((d) => {
			me.add_app_item(d);
		});
	}

	add_app_item(item) {
		$(`<div class="dropdown-menu-item" data-name="${item.name}"
			data-app-route="${item.route}">
			<a ${item.href ? `href="${item.href}"` : ""}>
				<div class="sidebar-item-icon">
					${
						item.icon
							? frappe.utils.icon(item.icon)
							: `<img
							class="logo"
							src="${item.icon_url}"
						>`
					}
				</div>
				<span class="menu-item-title">${item.label}</span>
			</a>
		</div>`).appendTo(this.dropdown_menu);
	}

	setup_select_options() {
		this.dropdown_menu.find(".dropdown-menu-item").on("click", (e) => {
			let item = $(e.delegateTarget);
			let name = item.attr("data-name");
			let current_item = this.dropdown_items.find((f) => f.name == name);
			this.dropdown_menu.toggleClass("hidden");
			this.toggle_active();
			current_item.onClick(item);
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
