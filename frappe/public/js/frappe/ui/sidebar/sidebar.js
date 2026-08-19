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

		// if CRM is installed on the site, link to the route configured via add_to_apps_screen
		const installed_app = (frappe.boot.apps_data.apps || []).find((app) => app.name === "crm");
		if (installed_app && installed_app.route) {
			const title = __("Switch to CRM");
			const message = __("Open Frappe CRM");
			this.promotional_banners.push({
				title,
				message,
				link: installed_app.route,
				icon,
				is_internal: true,
			});
			return;
		}

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

		// if Helpdesk is installed on the site, link to the route configured via add_to_apps_screen
		const installed_app = (frappe.boot.apps_data.apps || []).find(
			(app) => app.name === "helpdesk"
		);
		if (installed_app && installed_app.route) {
			const title = __("Switch to Helpdesk");
			const message = __("Open Frappe Helpdesk");
			this.promotional_banners.push({
				title,
				message,
				link: installed_app.route,
				icon,
				is_internal: true,
			});
			return;
		}

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
			const target = banner.is_internal ? "" : ` target="_blank"`;
			let banner_html = $(`
				<a class="promotional-banner px-2"${target} title="${banner.message}">
					<span class="promotional-banner-title">${banner.title}</span>
				</a>
			`);

			// Set href via .attr() rather than template interpolation: banner.link can be
			// a server-derived route (apps_data), so interpolating it risks attribute
			// breakout / javascript: injection.
			banner_html.attr("href", banner.link);
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
		if (module_name && !frappe.is_mobile()) {
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
		this.store_last_show_sidebar_for_item();
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
			let card_obj = new frappe.ui.Card(card);
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
		this.setup_reload();
		frappe.router.on("change", function (router) {
			if (frappe.route_options && frappe.route_options.sidebar) {
				frappe.app.sidebar.setup(frappe.route_options.sidebar);
				frappe.route_options = null;
			} else {
				frappe.app.sidebar.set_workspace_sidebar(router);
			}
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+/",
			action: () => me.toggle_width(),
			description: __("Toggle sidebar"),
		});
	}

	// Fired on page-change / form-refresh. Handles visibility, then runs the
	// same resolver as the router so every navigation event picks a sidebar.
	// set_workspace_sidebar is idempotent, so re-running it here is a no-op
	// unless the route actually warrants a different sidebar.
	refresh() {
		if (!frappe.container.page.page) return;
		if (frappe.container.page.page.hide_sidebar) {
			this.wrapper.hide();
			return;
		}
		this.wrapper.show();
		this.set_workspace_sidebar();
	}
	toggle(hide) {
		if (hide) {
			this.wrapper.hide();
		} else {
			this.wrapper.show();
		}
	}
	make_dom() {
		this.load_sidebar_state();
		this.wrapper = $(
			frappe.render_template("sidebar", {
				expanded: this.sidebar_expanded,
				avatar: frappe.avatar(frappe.session.user, "avatar-medium-2"),
				navbar_settings: frappe.boot.navbar_settings,
			})
		).prependTo("body");
		this.$sidebar = this.wrapper.find(".sidebar-items");

		this.wrapper.find(".body-sidebar .sidebar-resize-handle").on("click", () => {
			this.toggle_width();
		});

		this.wrapper.find(".body-sidebar .collapse-sidebar-link").on("click", () => {
			this.toggle_width();
		});

		this.wrapper.find(".overlay").on("click", () => {
			this.close();
		});
<<<<<<< HEAD
=======
		this.setup_user_menu();
	}

	setup_user_menu() {
		this.create_user_menu({
			parent: this.wrapper.find(".dropdown-navbar-user"),
			button: this.wrapper.find(".sidebar-user-button"),
		});
	}

	// Build the user dropdown (profile, workspaces, theme, logout, ...) on a given trigger element.
	// Shared by the sidebar's user button and the workspace dock's avatar so both open the same menu.
	// `button` is the element that gets the active-state class while the menu is open.
	create_user_menu({ parent, button }) {
		const me = this;
		const $btn = button;
		const $container = parent;

		frappe.ui.create_menu({
			parent: $container,
			open_on_top: true,
			menu_items: [
				{
					name: "settings",
					label: __("Settings"),
					icon: "settings",
					onClick: function () {
						// The Settings dialog is lazy (not in the desk bundle); pull it
						// in on click, then open it.
						frappe
							.require("user_settings_dialog.bundle.js")
							.then(() => frappe.ui.show_user_settings("profile"))
							.catch((e) => {
								console.error(
									"Sidebar: failed to load user_settings_dialog.bundle.js",
									e
								);
								frappe.ui.toast({
									message: __(
										"Could not open Settings. Please refresh the page."
									),
									type: "error",
								});
							});
					},
				},
				{
					name: "workspace-selector",
					label: __("Manage Dock"),
					icon: "monitor",
					onClick: function () {
						new frappe.ui.DockManager();
					},
				},
				{
					name: "reload",
					label: __("Reload"),
					icon: "rotate-ccw",
					onClick: function () {
						frappe.ui.toolbar.clear_cache();
					},
				},
				...frappe.boot.navbar_settings.settings_dropdown
					.filter((item) => !item.hidden)
					.map((item) => {
						const mapped = {
							name: item.name,
							label: item.item_label,
							icon: item.icon,
							condition: item.condition,
						};
						if (item.item_type === "Route") {
							mapped.url = item.route;
						} else if (item.item_type === "Action") {
							mapped.onClick = () => frappe.utils.eval(item.action);
						}
						return mapped;
					}),
				{ is_divider: true },
				{
					name: "logout",
					label: __("Logout"),
					icon: "log-out",
					onClick: function () {
						frappe.app.logout();
					},
				},
			],
			onShow: function () {
				$btn.addClass("user-menu-active");
			},
			onHide: function () {
				$btn.removeClass("user-menu-active");
			},
			onItemClick: function () {
				$btn.removeClass("user-menu-active");
			},
		});
>>>>>>> 185e658c39 (fix(navbar): Onclick link for routesclear)
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
				this.add_item(this.$items_container, w);
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
			suffix: "<span class='sidebar-notification-count hidden' aria-live='polite'></span>",
			onClick: () => {
				const $dropdown = this.wrapper.find(".dropdown-notifications");
				$dropdown.toggleClass("hidden");
				if (!$dropdown.hasClass("hidden")) {
					$dropdown.trigger("show.bs.dropdown");
				}
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
		const is_rtl = frappe.utils.is_rtl();
		if (this.sidebar_expanded) {
			this.wrapper.addClass("expanded");
			$('[data-toggle="tooltip"]').tooltip("dispose");
			this.wrapper.find(".avatar-name-email").show();
			this.wrapper.find(".onboarding-sidebar span").show();
			this.wrapper.find(".promotional-banner-title").show();
		} else {
			this.wrapper.removeClass("expanded");
			$('[data-toggle="tooltip"]').tooltip({
				boundary: "window",
				container: "body",
				trigger: "hover",
			});
			this.wrapper.find(".avatar-name-email").hide();
			this.wrapper.find(".onboarding-sidebar span").hide();
			this.wrapper.find(".promotional-banner-title").hide();
		}

		localStorage.setItem("sidebar-expanded", this.sidebar_expanded);
		const chevron_icon = this.sidebar_expanded
			? is_rtl
				? "chevron-right"
				: "chevron-left"
			: is_rtl
			? "chevron-left"
			: "chevron-right";
		this.wrapper
			.find(".body-sidebar .collapse-sidebar-link")
			.find("use")
			.attr("href", `#icon-${chevron_icon}`);
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
			const route = frappe.get_route();
			let target;

			if (route.length === 2 && frappe.boot.workspace_sidebar_item[route[1].toLowerCase()]) {
				// route points directly at a workspace, e.g. List/<Workspace>
				target = route[1];
			} else {
				const entity = this.entity_from_route(route);
				const module = router?.meta?.module;
				target = this.resolve_sidebar(entity, module);
			}

			// only rebuild when the target differs from the current sidebar, so
			// this stays a cheap no-op when re-run by page-change / form-refresh
			if (target && target !== this.sidebar_title) {
				frappe.app.sidebar.setup(target);
			}
		} catch (e) {
			console.error(e);
		}

		this.set_active_workspace_item();
	}

	entity_from_route(route) {
		switch (route.length) {
			case 1:
				return route[0];
			case 3:
				return route[0] === "Workspaces" && route[1] === "private" ? route[2] : route[1];
			case 2:
				// view-type routes like ["List", "Customer"] or
				// ["query-report", "Balance Sheet"] -> entity is the second element
				return route[1];
			default:
				return route[1];
		}
	}

	// Pick which workspace sidebar to show for the current route.
	// Returns a workspace title (or null). Rules are ordered by priority:
	// the first one that yields a sidebar wins.
	resolve_sidebar(entity, module) {
		let candidates = this.get_workspace_sidebars(entity);
		this.preferred_sidebars = candidates;

		const remembered = JSON.parse(localStorage.getItem("sidebar_item_map") || "{}");

		let sidebar_name = null;

		if (this.sidebar_title && candidates.includes(this.sidebar_title)) {
			// 1. current sidebar already links to this entity -> keep it
			sidebar_name = this.sidebar_title;
		} else if (remembered[entity]?.length) {
			// 2. previously remembered choice for this entity
			sidebar_name = remembered[entity][0];
		} else {
			// 3. narrow candidates to the active app
			if (module) {
				candidates = this.filter_sidebars_from_app(
					candidates,
					frappe.boot.module_app[module.toLowerCase().replace(/[ -]/g, "_")]
				);
			}

			// 4. resolve by what is left
			if (candidates.length === 1) {
				sidebar_name = candidates[0];
			} else if (candidates.length > 1) {
				sidebar_name = candidates.find((c) => c.toLowerCase() === module?.toLowerCase());
			} else if (module) {
				sidebar_name = this.resolve_module_sidebar(module);
			}
		}
		if (!sidebar_name && candidates.length > 0) {
			sidebar_name = candidates[0];
		}
		return sidebar_name;
	}
	filter_sidebars_from_app(sidebars, app) {
		let filter_sidebars = [];
		sidebars.forEach((sidebar) => {
			const config = frappe.boot.workspace_sidebar_item[sidebar.toLowerCase()];
			if (config && config.app === app && !filter_sidebars.includes(sidebar)) {
				filter_sidebars.push(sidebar);
			}
		});
		return filter_sidebars;
	}
	// Public entry point used by page/report views to switch the sidebar
	// to the one for a module. Resolution itself lives in resolve_module_sidebar.
	show_sidebar_for_module(module) {
		if (this.sidebar_title && this.preferred_sidebars.includes(this.sidebar_title)) {
			this.set_active_workspace_item();
			return;
		}
		const target = this.resolve_module_sidebar(module);
		if (target) frappe.app.sidebar.setup(target);
	}
	resolve_module_sidebar(module) {
		return frappe.boot.workspace_sidebar_item[module.toLowerCase()] ? module : null;
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
	setup_reload() {
		const me = this;
		this.item_sidebar_map = {};
		$(window).on("beforeunload", function () {
			me.store_last_show_sidebar_for_item();
		});
	}
	store_last_show_sidebar_for_item() {
		const me = this;
		if (frappe.app.sidebar.active_item) {
			let active_item = frappe.app.sidebar.active_item.parent().data("id");
			if (!me.item_sidebar_map[active_item]) {
				me.item_sidebar_map[active_item] = [];
			}
			me.item_sidebar_map[active_item].push(me.sidebar_title);
			localStorage.setItem("sidebar_item_map", JSON.stringify(me.item_sidebar_map));
		}
	}
};
