frappe.ui.MobileSidebar = class MobileSidebar {
	constructor() {
		this.items = [
			{
				label: "Home",
				icon: "home",
				route: "/app/m-navigation",
			},
			{
				label: "Apps",
				icon: "layout-grid",
				route: "/apps",
				onclick: function () {
					console.log("open app");
				},
			},
		];

		if (!frappe.boot.setup_complete) {
			// no sidebar if setup is not complete
			return;
		}

		// this.set_all_pages();
		this.make_dom();

		this.setup_pages();
		this.make_sidebar();
		this.apps_switcher.populate_apps_menu();
	}

	make_dom() {
		this.set_default_app();
		this.wrapper = $(frappe.render_template("mobile_sidebar"));
		$(".main-section").after(this.wrapper);

		this.app_switcher_dropdown = $(
			frappe.render_template("apps_switcher", {
				app_logo_url: frappe.boot.app_data[0].app_logo_url,
				app_title: __(frappe.boot.app_data[0].app_title),
			})
		).prependTo(this.wrapper.find(".body-sidebar"));

		this.$sidebar = this.wrapper.find(".mobile-sidebar-items");

		this.wrapper.find(".body-sidebar .collapse-sidebar-link").on("click", () => {
			this.toggle_sidebar();
		});

		this.apps_switcher = new frappe.ui.AppsSwitcher(this);
		this.apps_switcher.create_app_data_map();
	}

	set_hover() {
		$(".standard-sidebar-item > .item-anchor").on("mouseover", function (event) {
			if ($(this).parent().hasClass("active-sidebar")) return;
			$(this).parent().addClass("hover");
		});

		$(".standard-sidebar-item > .item-anchor").on("mouseleave", function () {
			$(this).parent().removeClass("hover");
		});
	}

	set_all_pages() {
		this.sidebar_pages = frappe.boot.sidebar_pages;
		this.all_pages = this.sidebar_pages.pages;
		this.has_access = this.sidebar_pages.has_access;
		this.has_create_access = this.sidebar_pages.has_create_access;
	}

	set_default_app() {
		// sort apps based on # of workspaces
		frappe.boot.app_data.sort((a, b) => (a.workspaces.length < b.workspaces.length ? 1 : -1));
		frappe.current_app = frappe.boot.app_data[0].app_name;
	}

	set_active_workspace_item() {
		if (!frappe.get_route()) return;
		let current_route = frappe.get_route();
		let current_route_str = frappe.get_route_str();
		let current_item;
		if (current_route[0] == "Workspaces") {
			current_item = current_route[1];
		} else if (frappe.breadcrumbs) {
			if (Object.keys(frappe.breadcrumbs.all).length == 0) return;
			if (frappe.breadcrumbs.all[current_route_str]) {
				current_item =
					frappe.breadcrumbs.all[current_route_str].workspace ||
					frappe.breadcrumbs.all[current_route_str].module;
			}
		}
		if (this.is_route_in_sidebar(current_item)) {
			this.active_item.addClass("active-sidebar");
		}
		if (this.active_item) {
			if (this.is_nested_item(this.active_item.parent())) {
				let current_item = this.active_item.parent();
				this.expand_parent_item(current_item);
			}
		}
	}
	expand_parent_item(item) {
		let parent_title = item.attr("item-parent");
		if (!parent_title) return;

		let parent = this.get_sidebar_item(parent_title);
		$($(parent).children()[1]).removeClass("hidden");
		if (parent) {
			if (this.is_nested_item($(parent))) {
				this.expand_parent_item($(parent));
			}
		}
	}
	is_nested_item(item) {
		if (item.attr("item-parent")) {
			return true;
		} else {
			return false;
		}
	}

	get_sidebar_item(name) {
		let sidebar_item = "";
		$(".sidebar-item-container").each(function () {
			if ($(this).attr("item-name") == name) {
				sidebar_item = this;
			}
		});
		return sidebar_item;
	}
	is_route_in_sidebar(active_module) {
		let match = false;
		const that = this;
		$(".item-anchor").each(function () {
			if ($(this).attr("title") == active_module) {
				match = true;
				if (that.active_item) that.active_item.removeClass("active-sidebar");
				that.active_item = $(this).parent();
				// this exists the each loop
				return false;
			}
		});
		return match;
	}

	setup_pages() {
		this.set_all_pages();
		this.all_pages.forEach((page) => {
			page.is_editable = !page.public || this.has_access;
			if (typeof page.content == "string") {
				page.content = JSON.parse(page.content);
			}
		});

		if (this.all_pages) {
			frappe.workspaces = {};
			frappe.workspace_list = [];
			frappe.workspace_map = {};
			for (let page of this.all_pages) {
				frappe.workspaces[frappe.router.slug(page.name)] = {
					name: page.name,
					public: page.public,
				};
				if (!page.app && page.module) {
					page.app = frappe.boot.module_app[frappe.slug(page.module)];
				}
				frappe.workspace_map[page.name] = page;
				frappe.workspace_list.push(page);
			}
		}
		this.set_hover();
	}
	build_sidebar_section() {}
	make_sidebar() {
		for (let item of this.items) {
			console.log(item);
			let item_container = $(`
				<div
					class="mobile-item-container" data-name=${item.label}
				>
						<a
							href="${item.route}"
							target=""
							class="mobile-item-anchor" title="${__(item.label)}"
						>
							<span class="sidebar-item-icon icon icon-md" item-icon=${item.icon || "folder-normal"}>
								${
									item.icon
										? frappe.utils.icon(item.icon || "folder-normal", "md")
										: `<span class="indicator ${item.indicator_color}"></span>`
								}
							</span>
							<span class="sidebar-item-label">${__(item.label)}<span>
						</a>
				</div>
			`);
			item_container.appendTo(this.$sidebar);
		}
	}

	reload() {
		return frappe.workspace.get_pages().then((r) => {
			frappe.boot.sidebar_pages = r;
			this.setup_pages();
		});
	}
	set_height() {
		$(".body-sidebar").css("height", window.innerHeight + "px");
		$(".overlay").css("height", window.innerHeight + "px");
		document.body.style.overflow = "hidden";
	}
};
