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
		this.cards = [];
		this.setup_events();
		this.sidebar_module_map = {};
		this.build_sidebar_module_map();
		this.standard_items_setup = false;
		this.preferred_sidebars = [];
	}

	prepare() {
		try {
			this.add_standard_items();
			this.sidebar_data = frappe.boot.workspace_sidebar_item[this.workspace_title];
			this.workspace_sidebar_items = this.sidebar_data.items;
			this.all_sidebar_items = frappe.boot.workspace_sidebar_item;
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
			if (value.module && !value.label.includes("My Workspaces")) {
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
			} else {
				let app_name = frappe.boot.module_app[this.workspace_title];
				if (app_name) {
					let app_title = frappe.boot.app_data.find((f) => {
						return f.app_name == app_name;
					}).app_title;
					this.header_subtitle = app_title;
				} else {
					this.header_subtitle = frappe.session.user;
				}
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

	setup_promotional_banners() {
		if (
			cint(frappe.sys_defaults?.disable_product_suggestion) ||
			!frappe.user.has_role("System Manager")
		)
			return;

		let module = this.all_sidebar_items?.[this.workspace_title]?.["module"] || "";
		if (!module) return;

		this.$promotional_banners = this.wrapper.find(".promotional-banners");
		this.$promotional_banners.empty();
		this.promotional_banners = [];

		this.get_crm_banner(module);
		this.get_helpdesk_banner(module);

		this.render_promotional_banners();
	}

	get_crm_banner(module) {
		if (module != "CRM") return;

		const icon =
			$(`<svg width="16" height="16" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M0 11.2C0 7.27963 0 5.31945 0.762954 3.82207C1.43407 2.50493 2.50493 1.43407 3.82207 0.762954C5.31945 0 7.27963 0 11.2 0H16.8C20.7204 0 22.6806 0 24.1779 0.762954C25.4951 1.43407 26.5659 2.50493 27.237 3.82207C28 5.31945 28 7.27963 28 11.2V16.8C28 20.7204 28 22.6806 27.237 24.1779C26.5659 25.4951 25.4951 26.5659 24.1779 27.237C22.6806 28 20.7204 28 16.8 28H11.2C7.27963 28 5.31945 28 3.82207 27.237C2.50493 26.5659 1.43407 25.4951 0.762954 24.1779C0 22.6806 0 20.7204 0 16.8V11.2Z" fill="#DB4EE0"/>
<path d="M5.02441 6.58252V9.09486H20.4627V10.9791L15.0135 16.3806V19.3201H12.9676V16.3806C12.9676 16.3806 9.78529 13.1774 8.62962 12.0469H5.03698L10.0156 17.0087C10.3045 17.2851 10.4678 17.6745 10.4678 18.0765V21.041L17.5259 21.0661V18.0765C17.5259 17.6745 17.6892 17.2851 17.9781 17.0087L22.9751 12.0343V6.58252H5.02441Z" fill="#F1FCFF"/>
</svg>
`);

		const title = __("Switch to Frappe CRM");
		const message = __(
			"Sales without complexity, lock-in and per-user costs. Try it for free!"
		);
		const link =
			"https://frappe.io/crm?utm_source=crm-sidebar&utm_medium=sidebar&utm_campaign=frappe-ad";

		this.promotional_banners.push({ title, message, link, icon });
	}

	get_helpdesk_banner(module) {
		if (module != "Support") return;

		const icon =
			$(`<svg width="16" height="16" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M0 11.2C0 7.27963 0 5.31945 0.762954 3.82207C1.43407 2.50493 2.50493 1.43407 3.82207 0.762954C5.31945 0 7.27963 0 11.2 0H16.8C20.7204 0 22.6806 0 24.1779 0.762954C25.4951 1.43407 26.5659 2.50493 27.237 3.82207C28 5.31945 28 7.27963 28 11.2V16.8C28 20.7204 28 22.6806 27.237 24.1779C26.5659 25.4951 25.4951 26.5659 24.1779 27.237C22.6806 28 20.7204 28 16.8 28H11.2C7.27963 28 5.31945 28 3.82207 27.237C2.50493 26.5659 1.43407 25.4951 0.762954 24.1779C0 22.6806 0 20.7204 0 16.8V11.2Z" fill="#7D42FB"/>
<path d="M22.7237 12.1723V6.65771H5.26367V9.17005H20.2239V11.5568C19.2189 11.8457 18.4904 12.7753 18.4904 13.8681C18.4904 14.961 19.2189 15.878 20.2239 16.1669V18.5536H7.77601V11.9964H5.26367V21.066H22.7362V15.5514L21.2414 14.4836V13.2526L22.7362 12.1849L22.7237 12.1723Z" fill="#EDF7FF"/>
</svg>
`);

		const title = __("Switch to Helpdesk");
		const message = __(
			"Support without complexity, lock-in and per-user costs. Try it for free!"
		);
		const link =
			"https://frappe.io/helpdesk?utm_source=support-sidebar&utm_medium=sidebar&utm_campaign=frappe-ad";

		this.promotional_banners.push({ title, message, link, icon });
	}

	render_promotional_banners() {
		let me = this;

		if (this.promotional_banners.length === 0) {
			this.$promotional_banners.hide();
			return;
		}

		this.$promotional_banners.show();

		this.promotional_banners.forEach((banner) => {
			let banner_html = $(`
				<a href="${banner.link}" class="promotional-banner" target="_blank" title="${banner.message}">
					<span>${banner.title}</span>
				</a>
			`);

			banner_html.prepend(banner.icon);
			me.$promotional_banners.append(banner_html);
		});
	}

	remove_onboarding_wrapper() {
		this.$onboarding.empty();
		this.wrapper.find(".onboarding-sidebar").removeClass("hidden");

		if (!this.sidebar_data?.module_onboarding) {
			this.wrapper.find(".onboarding-sidebar").addClass("hidden");
		}
	}

	setup_onboarding() {
		let me = this;
		this.$onboarding = this.wrapper.find(".user-onboarding");

		if (!this.sidebar_data || !this.sidebar_data.module_onboarding) {
			this.remove_onboarding_wrapper();
			return;
		}

		let module_name = this.sidebar_data.module_onboarding;

		if (this?.onboarding_widget[module_name]) {
			return;
		}

		this.remove_onboarding_wrapper();
		if (module_name) {
			if (
				this?.onboarding_widget[module_name] &&
				this.onboarding_widget[module_name].hide_panel
			) {
				return;
			}

			return frappe
				.call({
					method: "frappe.desk.desktop.get_onboarding_data",
					args: {
						// send sorted min requirements to increase chance of cache hit
						module: module_name,
					},
					type: "GET",
				})
				.then((data) => {
					if (data.message?.length > 0) {
						let onboarding_data = data.message[0];
						me.onboarding_widget = {};
						me.onboarding_widget[module_name] = new frappe.ui.UserOnboarding({
							title: onboarding_data.title,
							steps: onboarding_data.items,
							wrapper: me.$onboarding,
							header_icon: me.sidebar_header.header_icon,
						});
					} else {
						this.wrapper.find(".onboarding-sidebar").addClass("hidden");
					}
				});
		} else {
			this.wrapper.find(".onboarding-sidebar").addClass("hidden");
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
		if (!this.onboarding_widget) {
			this.onboarding_widget = {};
		}

		$(document).trigger("sidebar_setup", { sidebar: this });
		this.sidebar_title = workspace_title;
		this.check_for_private_workspace(workspace_title);
		this.workspace_title = this.sidebar_title.toLowerCase();

		this.prepare();
		this.$sidebar.attr("data-title", this.sidebar_title);
		this.sidebar_header = new frappe.ui.SidebarHeader(this);
		this.make_sidebar();
		this.add_sidebar_cards();
		this.setup_promotional_banners();
		this.setup_onboarding();

		this.wrapper.find(".onboarding-sidebar").click(() => {
			if (this.sidebar_data?.module_onboarding) {
				delete this.onboarding_widget[this.sidebar_data.module_onboarding];
			}

			this.setup_onboarding();
		});
	}
	add_card(card) {
		if (this.cards && this.cards.find((i) => i.title === card.title)) return;
		card.parent = this.wrapper.find(".body-sidebar-cards");
		delete card.styles;
		this.cards.push(card);
	}
	add_sidebar_cards() {
		this.wrapper.find(".body-sidebar-cards").html("");
		this.cards.forEach((card) => {
			let card_obj = new frappe.ui.SidebarCard(card);
			card.obj = card_obj;
		});
	}

	check_for_private_workspace(workspace_title) {
		if (workspace_title == "private" || workspace_title == "Personal") {
			this.sidebar_title = "My Workspaces";
		}
	}
	setup_events() {
		const me = this;
		frappe.router.on("change", function (router) {
			if (frappe.route_options.sidebar) {
				frappe.app.sidebar.setup(frappe.route_options.sidebar);
				frappe.route_options = null;
			} else {
				frappe.app.sidebar.set_workspace_sidebar(router);
			}
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
			this.expand_parent_section();
		}
	}

	expand_parent_section() {
		if (!this.active_item) return;
		let active_section;
		$(".section-item").each((index, element) => {
			if (element.contains(this.active_item.get(0))) {
				active_section = element.dataset.id;
			}
		});

		if (active_section) {
			let section = this.get_item(active_section);
			if (section) {
				if (this.sidebar_expanded && section.collapsed) {
					section.open();
				}
			}
		}
	}

	get_item(name) {
		for (let item of this.items) {
			if (item.item.label === name) {
				return item;
			}
		}
	}

	is_route_in_sidebar() {
		let match = false;
		const that = this;
		$(".item-anchor").each(function () {
			let href = decodeURIComponent($(this).attr("href")?.split("?")[0].split("#")[0]);

			const path = decodeURIComponent(window.location.pathname);

			// ensure no trailing slash mismatch
			const clean_href = href.replace(/\/$/, "");
			const clean_path = path.replace(/\/$/, "");

			const isActive = clean_path === clean_href || clean_path.startsWith(clean_href + "/");

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
					keyboard_shortcut: "Ctrl+K",
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
	get_workspace_for_module(module) {
		for (let i = 0; i < frappe.boot.workspaces.pages.length; i++) {
			const workspace = frappe.boot.workspaces.pages[i];
			if (workspace.module == module && !workspace.parent_page) {
				return workspace.name;
			}
		}
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
			this.notifications = new frappe.ui.Notifications({ full_height: true });
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
					entity_name = route[0];
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
			let sidebars = this.get_workspace_sidebars(entity_name);
			this.preferred_sidebars = sidebars;
			let module = router?.meta?.module;
			if (this.sidebar_title && sidebars.includes(this.sidebar_title)) {
				this.set_active_workspace_item();
				return;
			}
			if (module) {
				sidebars = this.filter_sidebars_from_app(
					sidebars,
					frappe.boot.module_app[module.toLowerCase()]
				);
			}
			if (sidebars.length == 1) {
				frappe.app.sidebar.setup(sidebars[0]);
			} else if (sidebars.length > 1) {
				let sidebar = this.get_workspace_for_module(module);
				if (sidebars.includes(this.get_workspace_for_module(module))) {
					frappe.app.sidebar.setup(sidebar);
				} else {
					frappe.app.sidebar.setup(module);
				}
			} else if (module) {
				this.show_sidebar_for_module(module);
			}
		} catch (e) {
			console.log(e);
		}

		this.set_active_workspace_item();
	}
	filter_sidebars_from_app(sidebars, app) {
		let filter_sidebars = [];
		sidebars.forEach((sidebar) => {
			if (
				!filter_sidebars.includes(sidebar) &&
				frappe.boot.workspace_sidebar_item[sidebar.toLowerCase()].app === app
			) {
				filter_sidebars.push(sidebar);
			}
		});
		return filter_sidebars;
	}
	show_sidebar_for_module(module) {
		if (this.sidebar_title && this.preferred_sidebars.includes(this.sidebar_title)) {
			this.set_active_workspace_item();
			return;
		}
		if (this.sidebar_fixes && this.sidebar_title != module) return;
		let workspace_name = this.get_workspace_for_module(module);
		if (frappe.boot.workspace_sidebar_item[module.toLowerCase()]) {
			frappe.app.sidebar.setup(module);
		} else if (
			workspace_name &&
			frappe.boot.workspace_sidebar_item[workspace_name.toLowerCase()]
		) {
			frappe.app.sidebar.setup(workspace_name);
		} else {
			let sidebars =
				this.sidebar_module_map[module] &&
				this.sidebar_module_map[module].sort((a, b) => {
					return a.localeCompare(b);
				});
			if (frappe.get_route())
				if (sidebars && sidebars.length) {
					frappe.app.sidebar.setup(sidebars[0]);
				}
		}
	}
	set_sidebar_for_page() {
		let route = frappe.get_route();
		let views = ["List", "Form", "Workspaces", "query-report"];
		let matches = views.some((view) => route.includes(view));
		if (matches) return;
		let workspace_title;
		if (route.length == 2) {
			workspace_title = this.get_workspace_sidebars(route[1]);
		} else {
			workspace_title = this.get_workspace_sidebars(route[0]);
		}
		let module_name = workspace_title[0];
		if (module_name) {
			frappe.app.sidebar.setup(module_name || this.sidebar_title);
		}
	}

	get_workspace_sidebars(link_to) {
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
