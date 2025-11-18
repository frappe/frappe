frappe.ui.SidebarHeader = class SidebarHeader {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.sidebar_wrapper = $(".body-sidebar");
		this.drop_down_expanded = false;
		this.workspace_title = this.sidebar.workspace_title;
		const me = this;
		this.dropdown_items = [
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
					me.sidebar.edit_mode = true;
					me.sidebar.toggle_editing_mode();
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
		this.make();
		this.setup_app_switcher();
		this.populate_dropdown_menu();
		this.setup_select_options();
	}

	make() {
		$(".sidebar-header").remove();
		$(".sidebar-header-menu").remove();
		this.set_header_icon();
		$(
			frappe.render_template("sidebar_header", {
				workspace_title: this.workspace_title,
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
		let desktop_icon = this.get_desktop_icon_by_label(this.sidebar.workspace_title);
		if (desktop_icon && desktop_icon.logo_url) {
			this.header_icon = this.get_desktop_icon_by_label(
				this.sidebar.workspace_title
			).logo_url;
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
		}
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
		this.dropdown_menu = $(".sidebar-header-menu");
		$(".sidebar-header").on("click", (e) => {
			this.toggle_dropdown_menu();
			e.stopImmediatePropagation();
		});
	}

	toggle_dropdown_menu() {
		this.toggle_active();
		this.dropdown_menu.toggleClass("hidden");
	}

	populate_dropdown_menu() {
		const me = this;
		this.check_editing_access();
		this.dropdown_items.forEach((d) => {
			me.add_app_item(d);
		});
	}
	check_editing_access() {
		if (!frappe.boot.developer_mode) {
			this.dropdown_items.splice(1, 1);
		}
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

	toggle_active() {
		this.toggle_dropdown();
		this.wrapper.toggleClass("active-sidebar");
		if (!this.sidebar.sidebar_expanded) {
			this.wrapper.removeClass("active-sidebar");
		}
	}

	toggle_dropdown() {
		if (this.drop_down_expanded) {
			this.drop_down_expanded = false;
		} else {
			this.drop_down_expanded = true;
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
