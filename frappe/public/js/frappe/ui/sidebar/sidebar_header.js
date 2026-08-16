frappe.ui.SidebarHeader = class SidebarHeader {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.sidebar_wrapper = $(".body-sidebar");
		this.title = this.get_display_title();
		this.make();
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
			})
		).prependTo(this.sidebar_wrapper);
		this.wrapper = $(".sidebar-header");
		this.$header_title = this.wrapper.find(".header-title");
		this.$drop_icon = this.wrapper.find(".drop-icon");
		this.toggle_width(this.sidebar.sidebar_expanded);
	}
	// The header names the module whose sidebar is on screen -- the sidebar belongs to a module,
	// so it should say which one. It used to show the owning app's title and fall back to the
	// module only when there was no app, which meant every module in an app shared one header:
	// "Frappe Framework" whether you were in Core, Website or Integrations.
	//
	// The app is still identifiable from the logo and the dock; the header is where the module
	// goes. `label` is the Sidebar's title, which an app (or a customization) may override,
	// falling back to the module name itself.
	get_display_title() {
		return (
			this.sidebar.sidebar_data?.label ||
			this.sidebar.current_module ||
			this.sidebar.get_sidebar_app()?.app_title
		);
	}
	// The module's own icon, used by the onboarding widget. An authored `header_icon`, else a
	// letter icon from its title -- the same pair the rail uses. There is no app-logo fallback:
	// an app's logo was never this module's icon, and the one that stood in was whichever app
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
