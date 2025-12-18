import "./sidebar_item";
import { SidebarEditor } from "./sidebar_editor";
frappe.ui.Sidebar = class Sidebar {
	constructor() {
		if (!frappe.boot.setup_complete) {
			// no sidebar if setup is not complete
			return;
		}
		this.make_dom();
		// states
		this.editor = new SidebarEditor(this);
		this.edit_mode = this.editor.edit_mode;
		this.sidebar_expanded = false;
		this.all_sidebar_items = frappe.boot.workspace_sidebar_item;
		this.$items = [];
		this.fields_for_dialog = [];
		this.workspace_sidebar_items = [];
		this.$items_container = this.wrapper.find(".sidebar-items");
		this.$standard_items_sections = this.wrapper.find(".standard-items-sections");
		this.$sidebar = this.wrapper.find(".body-sidebar");
		this.items = [];
		this.setup_events();
		this.sidebar_module_map = {};
		this.build_sidebar_module_map();
		this.standard_items_setup = false;
	}

	prepare() {
		try {
			this.add_standard_items();
			this.sidebar_data = frappe.boot.workspace_sidebar_item[this.workspace_title];
			this.workspace_sidebar_items = this.sidebar_data.items;
			if (this.edit_mode) {
				this.workspace_sidebar_items = this.editor.new_sidebar_items;
			}
			this.choose_app_name();
			this.find_nested_items();
		} catch (e) {
			console.log(e);
		}
	}
	build_sidebar_module_map() {
		for (const [key, value] of Object.entries(frappe.boot.workspace_sidebar_item)) {
			if (value.module) {
				if (!this.sidebar_module_map[value.module]) {
					this.sidebar_module_map[value.module] = [];
				}
				this.sidebar_module_map[value.module].push(value.label);
			}
		}
	}
	choose_app_name() {
		if (frappe.boot.app_name_style === "Default") return;

		for (const app of frappe.boot.app_data) {
			if (
				app.workspaces.includes(this.sidebar_title) ||
				(frappe.boot.workspace_sidebar_item[this.workspace_title] &&
					app.app_name == frappe.boot.workspace_sidebar_item[this.workspace_title].app)
			) {
				this.header_subtitle = app.app_title;
				frappe.current_app = app;
				this.app_logo_url = app.app_logo_url;
				return;
			}
		}

		const icon = frappe.boot.desktop_icons.find((i) => i.label === this.sidebar_title);
		if (icon) {
			this.header_subtitle = icon.parent_icon;
		}

		if (this.sidebar_title == "My Workspaces") {
			this.header_subtitle = frappe.session.user;
		}
	}

	find_nested_items() {
		const me = this;
		let currentSection = null;
		const updated_items = [];

		this.workspace_sidebar_items.forEach((item) => {
			item.nested_items = [];

			if (item.type === "Section Break") {
				currentSection = item;
				updated_items.push(item);
			} else if (currentSection && item.child) {
				item.parent = currentSection;
				currentSection.nested_items.push(item);
			} else {
				updated_items.push(item);
			}
		});
		this.workspace_sidebar_items = updated_items;
	}
	setup(workspace_title) {
		this.sidebar_title = workspace_title;
		this.check_for_private_workspace(workspace_title);
		this.workspace_title = this.sidebar_title.toLowerCase();

		this.prepare();
		this.$sidebar.attr("data-title", this.sidebar_title);
		this.sidebar_header = new frappe.ui.SidebarHeader(this);
		this.make_sidebar();
	}
	check_for_private_workspace(workspace_title) {
		if (workspace_title == "private" || workspace_title == "Personal") {
			this.sidebar_title = "My Workspaces";
		}
	}
	setup_events() {
		const me = this;
		frappe.router.on("change", function (router) {
			frappe.app.sidebar.set_workspace_sidebar(router);
		});
		$(document).on("page-change", function () {
			frappe.app.sidebar.toggle();
		});
		$(document).on("form-refresh", function () {
			frappe.app.sidebar.toggle();
		});
	}

	toggle() {
		if (!frappe.container.page.page) return;
		if (frappe.container.page.page.hide_sidebar) {
			this.wrapper.hide();
		} else {
			this.wrapper.show();
			this.set_sidebar_for_page();
		}
	}
	make_dom() {
		this.load_sidebar_state();
		this.wrapper = $(
			frappe.render_template("sidebar", {
				expanded: this.sidebar_expanded,
				avatar: frappe.avatar(frappe.session.user, "avatar-medium"),
				navbar_settings: frappe.boot.navbar_settings,
			})
		).prependTo("body");
		this.$sidebar = this.wrapper.find(".sidebar-items");

		this.wrapper.find(".body-sidebar .collapse-sidebar-link").on("click", () => {
			this.toggle_width();
		});

		this.wrapper.find(".overlay").on("click", () => {
			this.close();
		});
	}

	set_active_workspace_item() {
		if (this.is_route_in_sidebar()) {
			this.active_item.addClass("active-sidebar");
		}
	}

	is_route_in_sidebar() {
		let match = false;
		const that = this;
		$(".item-anchor").each(function () {
			let href = decodeURIComponent($(this).attr("href")?.split("?")[0]);
			const path = decodeURIComponent(window.location.pathname);

			// Match only if path equals href or starts with it followed by "/" or end of string
			const isActive = href === path;
			if (href && isActive) {
				match = true;
				if (that.active_item) that.active_item.removeClass("active-sidebar");
				that.active_item = $(this).parent();
			}
		});
		return match;
	}

	set_sidebar_state() {
		this.load_sidebar_state();
		if (this.workspace_sidebar_items.length === 0) {
			this.sidebar_expanded = true;
		}

		this.expand_sidebar();
	}

	load_sidebar_state() {
		this.sidebar_expanded = true;
		if (localStorage.getItem("sidebar-expanded") !== null) {
			this.sidebar_expanded = JSON.parse(localStorage.getItem("sidebar-expanded"));
		}

		if (frappe.is_mobile()) {
			this.sidebar_expanded = false;
		}
	}
	empty() {
		if (this.wrapper.find(".sidebar-items")[0]) {
			this.wrapper.find(".sidebar-items").html("");
		}
	}
	make_sidebar() {
		this.empty();
		this.wrapper.find(".collapse-sidebar-link").removeClass("hidden");
		if (this.editor.edit_mode) {
			this.create_sidebar(this.editor.new_sidebar_items);
		} else {
			this.create_sidebar(this.workspace_sidebar_items);
		}

		// Scroll sidebar to selected page if it is not in viewport.
		this.wrapper.find(".selected").length &&
			!frappe.dom.is_element_in_viewport(this.wrapper.find(".selected")) &&
			this.wrapper.find(".selected")[0].scrollIntoView();

		this.set_active_workspace_item();
		this.set_sidebar_state();
	}
	create_sidebar(items) {
		this.empty();
		if (items && items.length > 0) {
			items.forEach((w) => {
				if (!w.display_depends_on || frappe.utils.eval(w.display_depends_on)) {
					w.label = __(w.label);
					this.add_item(this.$items_container, w);
				}
			});
		} else {
			let no_items_message = $(
				"<div class='flex' style='padding: 30px'> No Sidebar Items </div>"
			);
			this.wrapper.find(".sidebar-items").append(no_items_message);
			this.wrapper.find(".collapse-sidebar-link").addClass("hidden");
		}
		if (this.edit_mode) {
			$(".edit-menu").removeClass("hidden");
		}
		this.handle_outside_click();
	}
	add_standard_items(items) {
		if (this.standard_items_setup) return;
		this.standard_items = [];
		if (!frappe.is_mobile()) {
			this.standard_items.push({
				label: __("Search"),
				icon: "search",
				standard: true,
				type: "Button",
				id: "navbar-modal-search",
				suffix: {
					keyboard_shortcut: "CtrlK",
				},
				class: "navbar-search-bar hidden",
			});
		}
		this.standard_items.push({
			label: __("Notification"),
			icon: "bell",
			standard: true,
			type: "Button",
			class: "sidebar-notification hidden",
			onClick: () => {
				this.wrapper.find(".dropdown-notifications").toggleClass("hidden");
				if (frappe.is_mobile()) {
					this.wrapper.removeClass("expanded");
				}
			},
		});
		this.standard_items.forEach((w) => {
			this.add_item(this.$standard_items_sections, w);
		});
		this.setup_awesomebar();
		this.setup_notifications();
		this.standard_items_setup = true;
	}
	setup_awesomebar() {
		if (frappe.boot.desk_settings.search_bar) {
			let awesome_bar = new frappe.search.AwesomeBar();
			awesome_bar.setup("#navbar-modal-search");

			frappe.search.utils.make_function_searchable(
				frappe.utils.generate_tracking_url,
				__("Generate Tracking URL")
			);
			if (frappe.model.can_read("RQ Job")) {
				frappe.search.utils.make_function_searchable(function () {
					frappe.set_route("List", "RQ Job");
				}, __("Background Jobs"));
			}
		}
	}
	setup_notifications() {
		if (frappe.boot.desk_settings.notifications && frappe.session.user !== "Guest") {
			this.notifications = new frappe.ui.Notifications();
		}
	}
	add_item(container, item) {
		this.items.push(
			this.make_sidebar_item({
				container: container,
				item: item,
			})
		);
	}
	make_sidebar_item(opts) {
		let class_name = `Type${frappe.utils.to_title_case(opts.item.type).replace(/ /g, "")}`;

		return new frappe.ui.sidebar_item[class_name](opts);
	}
	update_item(item, index) {}

	remove_item(item, index) {}

	toggle_width() {
		if (!this.sidebar_expanded) {
			this.open();
		} else {
			this.close();
		}
	}

	expand_sidebar() {
		let direction;
		if (this.sidebar_expanded) {
			this.wrapper.addClass("expanded");
			// this.sidebar_expanded = false
			direction = "right";
			$('[data-toggle="tooltip"]').tooltip("dispose");
			this.wrapper.find(".avatar-name-email").show();
		} else {
			this.wrapper.removeClass("expanded");
			// this.sidebar_expanded = true
			direction = "left";
			$('[data-toggle="tooltip"]').tooltip({
				boundary: "window",
				container: "body",
				trigger: "hover",
			});
			this.wrapper.find(".avatar-name-email").hide();
		}

		localStorage.setItem("sidebar-expanded", this.sidebar_expanded);
		this.wrapper
			.find(".body-sidebar .collapse-sidebar-link")
			.find("use")
			.attr("href", `#icon-panel-${direction}-open`);
		this.sidebar_header.toggle_width(this.sidebar_expanded);
		$(document).trigger("sidebar-expand", {
			sidebar_expand: this.sidebar_expanded,
		});
	}

	close() {
		this.sidebar_expanded = false;

		this.expand_sidebar();
		if (frappe.is_mobile()) frappe.app.sidebar.prevent_scroll();
	}
	open() {
		this.sidebar_expanded = true;
		this.expand_sidebar();
		this.set_active_workspace_item();
	}

	set_height() {
		$(".body-sidebar").css("height", window.innerHeight + "px");
		$(".overlay").css("height", window.innerHeight + "px");
		document.body.style.overflow = "hidden";
	}

	handle_outside_click() {
		document.addEventListener("click", (e) => {
			if (this.sidebar_header.drop_down_expanded) {
				if (!e.composedPath().includes(this.sidebar_header.app_switcher_dropdown)) {
					this.sidebar_header.toggle_dropdown_menu();
				}
			}
		});
	}

	prevent_scroll() {
		let main_section = $(".main-section");
		if (this.sidebar_expanded) {
			main_section.css("overflow", "hidden");
		} else {
			main_section.css("overflow", "");
		}
	}

	set_workspace_sidebar(router) {
		try {
			let route = frappe.get_route();
			let view, entity_name;
			switch (route.length) {
				case 1:
					view = "Page";
					entity_name = route[1];
					break;
				case 2:
					view = route[0];
					entity_name = route[1];

					if (frappe.boot.workspace_sidebar_item[entity_name.toLowerCase()]) {
						frappe.app.sidebar.setup(entity_name);
						return;
					}
					break;
				case 3:
					view = route[0];
					entity_name = route[1];
					if (route[0] == "Workspaces" && route[1] == "private") {
						entity_name = route[2];
					}
					break;
				default:
					entity_name = route[1];
			}

			let sidebars = this.get_correct_workspace_sidebars(entity_name);
			let module = router?.meta?.module;
			if (this.sidebar_title && sidebars.includes(this.sidebar_title)) {
				this.set_active_workspace_item();
				return;
			}

			if (sidebars.length == 1) {
				frappe.app.sidebar.setup(sidebars[0]);
			} else if (module) {
				this.show_sidebar_for_module(module);
			}
		} catch (e) {
			console.log(e);
		}

		this.set_active_workspace_item();
	}
	show_sidebar_for_module(module) {
		let sidebars =
			this.sidebar_module_map[module] &&
			this.sidebar_module_map[module].sort((a, b) => {
				return a.localeCompare(b);
			});
		if (sidebars && sidebars.length) {
			if (this.sidebar_title) return;
			frappe.app.sidebar.setup(sidebars[0]);
		}
	}
	set_sidebar_for_page() {
		let route = frappe.get_route();
		let views = ["List", "Form", "Workspaces", "query-report"];
		let matches = views.some((view) => route.includes(view));
		if (matches) return;
		let workspace_title;
		if (route.length == 2) {
			workspace_title = this.get_correct_workspace_sidebars(route[1]);
		} else {
			workspace_title = this.get_correct_workspace_sidebars(route[0]);
		}
		let module_name = workspace_title[0];
		if (module_name) {
			frappe.app.sidebar.setup(module_name || this.sidebar_title);
		}
	}

	get_correct_workspace_sidebars(link_to) {
		let sidebars = [];
		Object.entries(this.all_sidebar_items).forEach(([name, sidebar]) => {
			const { items, label } = sidebar;
			items.forEach((item) => {
				if (item.link_to === link_to) {
					sidebars.push(label || name);
				}
			});
		});
		return sidebars;
	}
};
