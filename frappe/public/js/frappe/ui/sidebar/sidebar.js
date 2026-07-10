import "./sidebar_item";
frappe.ui.Sidebar = class Sidebar {
	constructor() {
		if (!frappe.boot.setup_complete) {
			// no sidebar if setup is not complete
			return;
		}
		this.make_dom();
		// states
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
	}

	prepare() {
		try {
			this.add_standard_items();
			this.sidebar_data = frappe.boot.workspace_sidebar_item[this.workspace_title];
			this.workspace_sidebar_items = this.sidebar_data.items;
			this.all_sidebar_items = frappe.boot.workspace_sidebar_item;
			this.find_nested_items();
		} catch (e) {
			console.log(e);
		}
	}
	// Resolve the app context from the current route and store it on `frappe.current_app` (plus
	// the header's subtitle/logo). Driven by the router (called from the `route change` handler),
	// so the app is decided by where you navigated to -- not as a side-effect of rendering the
	// header. On a workspace route the app comes from that workspace; on any other route the app
	// context persists (you stay "in" the app whose sidebar is active).
	//
	// The app is read from the workspace's own `app` field (with the sidebar payload's `app` as a
	// backup), rather than by scanning `app_data.workspaces` for a match. That scan misses
	// app-less/custom workspaces on a direct page load, which left `frappe.current_app` stale and
	// made the workspace selector flaky across refreshes.
	set_current_app() {
		if (frappe.boot.app_name_style === "Default") return;

		const route = frappe.get_route();
		if (route[0] === "Workspaces") {
			// a workspace route names its workspace -> the app comes from the workspace itself.
			// Custom (user-created, non-standard) workspaces belong to no app, so they never carry
			// an app context -- even if an older one has a stale `app` value.
			const name = route[route.length - 1];
			const workspace = frappe.workspaces[frappe.router.slug(name)];
			const sidebar = frappe.boot.workspace_sidebar_item[name.toLowerCase()];
			const app_name =
				workspace && !workspace.standard
					? null
					: (workspace && workspace.app) || (sidebar && sidebar.app);
			const app = app_name && frappe.boot.app_data.find((a) => a.app_name === app_name);
			if (app) {
				frappe.current_app = app;
				this.header_subtitle = app.app_title;
				this.app_logo_url = app.app_logo_url;
			} else {
				// no owning app (a custom workspace) -> clear the app context so the header/selector
				// don't keep showing the app you came from
				frappe.current_app = null;
				this.header_subtitle = frappe.session.user;
			}
			return;
		}

		// any other route -> derive the app from the routed entity (its module's app), the same
		// way the shell/sidebar is resolved. This is what makes a cold reload onto a
		// doctype/report figure out the app. If it can't be resolved (meta not loaded yet), keep
		// the current app context rather than clearing it.
		const app_name = this.app_from_route(this.entity_from_route(route));
		const app = app_name && frappe.boot.app_data.find((a) => a.app_name === app_name);
		if (app) {
			frappe.current_app = app;
			this.header_subtitle = app.app_title;
			this.app_logo_url = app.app_logo_url;
		}
	}

	// The app a route is heading into: the app that owns the routed doctype, resolved via its
	// module (meta.module -> module_app). Returns undefined when the entity isn't a doctype or its
	// meta isn't loaded yet, in which case the caller keeps the current app context.
	app_from_route(entity) {
		const meta = entity && frappe.get_meta(entity);
		if (!meta?.module) return undefined;
		return frappe.boot.module_app[frappe.scrub(meta.module)];
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

	setup_events() {
		const me = this;
		frappe.router.on("change", function () {
			// Resolve the app context from the route first, so `frappe.current_app` is correct
			// before the sidebar/header renders below.
			frappe.app.sidebar.set_current_app();
			if (frappe.route_options && frappe.route_options.sidebar) {
				frappe.app.sidebar.select_sidebar(frappe.route_options.sidebar);
				frappe.route_options = null;
			} else {
				frappe.app.sidebar.set_workspace_sidebar();
			}
			// The sidebar's setup() rebuilds the header, but it's skipped when the sidebar didn't
			// change (e.g. navigating within the same workspace). Refresh the header here so it
			// always reflects the app context resolved above.
			frappe.app.sidebar.refresh_header();
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+/",
			action: () => me.toggle_width(),
			description: __("Toggle sidebar"),
		});
	}

	// Re-render the header so it reflects the current app context (set by set_current_app) even
	// when the sidebar itself didn't change and setup() -- which builds the header -- wasn't
	// re-run. SidebarHeader.make() removes the existing header first, so this is safe to repeat.
	refresh_header() {
		if (this.sidebar_title) {
			this.sidebar_header = new frappe.ui.SidebarHeader(this);
		}
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
		this.setup_user_menu();
	}

	setup_user_menu() {
		const $btn = this.wrapper.find(".sidebar-user-button");
		const $container = this.wrapper.find(".dropdown-navbar-user");

		frappe.ui.create_menu({
			parent: $container,
			open_on_top: true,
			menu_items: [
				{
					name: "settings",
					label: __("Settings"),
					icon: "settings",
					onClick: function () {
						frappe.ui.show_user_settings("profile");
					},
				},
				{
					name: "workspace-selector",
					label: __("Manage Workspaces"),
					icon: "monitor",
					onClick: function () {
						new frappe.ui.WorkspacePicker();
					},
				},
				...frappe.boot.navbar_settings.settings_dropdown.map((item) => ({
					...item,
					label: item.item_label,
				})),
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
		let exact_match = null;
		let path_match = null;

		const route_params = Object.assign(
			{},
			Object.fromEntries(new URLSearchParams(window.location.search)),
			frappe.route_options || {}
		);

		$(".item-anchor").each(function () {
			const raw = $(this).attr("href") || "";
			const [href_path, href_query] = raw.split("?");
			const href = decodeURIComponent(href_path.split("#")[0]);

			const path = decodeURIComponent(window.location.pathname);

			// ensure no trailing slash mismatch
			const clean_href = href.replace(/\/$/, "");
			const clean_path = path.replace(/\/$/, "");

			const isActive = clean_path === clean_href || clean_path.startsWith(clean_href + "/");
			if (!href || !isActive) return;

			if (href_query) {
				let filter_match = true;
				new URLSearchParams(href_query).forEach((value, key) => {
					if (String(route_params[key]) !== String(value)) filter_match = false;
				});
				if (filter_match) exact_match = $(this).parent();
			} else {
				path_match = $(this).parent();
			}
		});

		const best = exact_match || path_match;
		if (best) {
			match = true;
			if (that.active_item) that.active_item.removeClass("active-sidebar");
			that.active_item = best;
		}
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
		this.create_sidebar(this.workspace_sidebar_items);

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
		this.handle_outside_click();
	}
	add_standard_items(items) {
		if (this.standard_items_setup) return;
		this.standard_items = [];
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
				this.wrapper.find(".dropdown-background-tasks").addClass("hidden");
				if (frappe.is_mobile()) {
					this.wrapper.removeClass("expanded");
				}
			},
		});
		this.standard_items.push({
			label: __("Background Tasks"),
			icon: "server",
			standard: true,
			type: "Button",
			class: "sidebar-background-tasks hidden",
			onClick: () => {
				this.wrapper.find(".dropdown-notifications").addClass("hidden");
				this.wrapper.find(".dropdown-background-tasks").toggleClass("hidden");
				if (frappe.is_mobile()) {
					this.wrapper.removeClass("expanded");
				}
			},
		});
		this.standard_items.forEach((w) => {
			this.add_item(this.$standard_items_sections, w);
		});
		this.setup_notifications();
		this.setup_background_tasks();
		this.standard_items_setup = true;
	}
	setup_notifications() {
		if (frappe.boot.desk_settings.notifications && frappe.session.user !== "Guest") {
			this.notifications = new frappe.ui.Notifications({ full_height: true });
		}
	}
	setup_background_tasks() {
		if (frappe.session.user !== "Guest") {
			this.background_tasks = new frappe.ui.BackgroundTasks({ full_height: true });
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

	// The sidebar is mostly selection-driven: it's chosen via the header switcher (or a direct
	// workspace route) and then stays put as you navigate. Two things move it automatically:
	//   - navigating to an entity that lives in some sidebar but NOT the current one follows it to
	//     the sidebar that owns it. Ownership is resolved from the boot sidebar payload via
	//     get_workspace_sidebars() -- the workspace whose item is flagged default_workspace wins,
	//     else the first sidebar that contains the item.
	//   - navigating to an entity that no sidebar links at all (e.g. a custom/standalone doctype)
	//     falls back to its module's autogenerated sidebar via sidebar_from_module().
	// Resolving from data (not the DOM/location) keeps it independent of route/render timing, and it
	// takes priority over the cold-entry fallback. The active-item highlight stays route-aware via
	// set_active_workspace_item().
	set_workspace_sidebar() {
		try {
			const route = frappe.get_route();

			if (route[0] === "Workspaces" && route.length >= 2) {
				// explicit workspace route -> user picked this workspace; make it the sticky selection
				const name = route[route.length - 1];
				if (frappe.boot.workspace_sidebar_item[name.toLowerCase()]) {
					this.select_sidebar(name);
				}
			} else {
				// Find every sidebar that contains the routed entity. Ownership resolution does NOT
				// consult the route's app: a sidebar may deliberately curate a cross-app link (e.g.
				// System Settings, owned by `frappe`, linked in the erpnext-owned ERPNext Settings
				// sidebar), and filtering by the doctype's app would drop the very sidebar you're on.
				// This matches the cold-entry path (resolve_initial_sidebar), which is also app-blind.
				// If the entity isn't already in the current sidebar, follow it to the one that owns
				// it: get_workspace_sidebars() puts the default_workspace owner first, else the first
				// sidebar that contains it.
				const entity = this.entity_from_route(route);
				const candidates = this.get_workspace_sidebars(entity);
				const in_current = candidates.some(
					(s) => s.toLowerCase() === this.workspace_title
				);

				if (this.workspace_title && candidates.length && !in_current) {
					this.select_sidebar(candidates[0]);
				} else if (this.sidebar_title && !candidates.length) {
					// the entity isn't linked in any sidebar -> fall back to its module's
					// autogenerated sidebar, so navigating to a custom/standalone doctype lands in
					// its own module shell instead of staying on the current one.
					const module_sidebar = this.sidebar_from_module(entity);
					if (module_sidebar && module_sidebar.toLowerCase() !== this.workspace_title) {
						this.select_sidebar(module_sidebar);
					}
				} else if (!this.sidebar_title) {
					// cold entry / deep link whose entity isn't in any sidebar -> resolve once
					const target = this.initial_sidebar(route);
					if (target) frappe.app.sidebar.setup(target);
				}
			}
		} catch (e) {
			console.error(e);
		}

		this.set_active_workspace_item();
	}

	// Switch to a workspace's sidebar and remember it so the choice survives navigation/reload.
	select_sidebar(name) {
		if (name && name !== this.sidebar_title) {
			frappe.app.sidebar.setup(name);
		}
		if (name) localStorage.setItem("selected_sidebar", name);
	}

	// Route of the first navigable item in a workspace's sidebar (or null if it has none).
	get_first_sidebar_route(name) {
		let sidebar = frappe.boot.workspace_sidebar_item[(name || "").toLowerCase()];
		if (!sidebar) return null;

		for (let item of sidebar.items || []) {
			let route = frappe.ui.sidebar_item.get_route(item);
			if (route) return route;
		}
		return null;
	}

	// Switch the sidebar to `name` and navigate to its first item (falling back to the
	// workspace page). Shared by the header switcher and global search.
	open_workspace(name) {
		if (frappe.boot.workspace_sidebar_item[(name || "").toLowerCase()]) {
			this.select_sidebar(name);
		}

		let route = this.get_first_sidebar_route(name);
		if (route) {
			frappe.set_route(route);
		} else {
			frappe.set_route("Workspaces", frappe.router.slug(name));
		}
	}

	initial_sidebar(route) {
		return this.resolve_initial_sidebar(route).sidebar;
	}

	// Pick the sidebar to show on cold entry, returning both the choice and why it was made.
	// Precedence:
	//   1. when the routed entity is linked in some sidebar: keep the last selected sidebar if it is
	//      one of them, else the first sidebar that contains it
	//   2. otherwise derive a sidebar from the doctype's module — the first sidebar belonging to the
	//      app that owns the module. This lands custom/standalone doctypes that no sidebar links
	//      directly into their own app's shell, instead of inheriting whatever was last selected.
	//   3. otherwise keep the last selected sidebar (the route belongs to no sidebar at all)
	//   4. the first available sidebar
	// User.default_workspace is intentionally NOT consulted here: it made the sidebar sticky to
	// one workspace regardless of route, which broke the illusion that each entity lives in its
	// own app shell.
	resolve_initial_sidebar(route) {
		const all = frappe.boot.workspace_sidebar_item || {};
		const exists = (name) => (name && all[name.toLowerCase()] ? name : null);

		const entity = this.entity_from_route(route);
		const candidates = this.get_workspace_sidebars(entity);
		const persisted = exists(localStorage.getItem("selected_sidebar"));

		// 1. the entity is directly linked in one or more sidebars
		if (candidates.length) {
			if (persisted && candidates.some((c) => c.toLowerCase() === persisted.toLowerCase())) {
				return {
					sidebar: persisted,
					reason: `last selected sidebar "${persisted}" — route entity "${entity}" belongs to it`,
				};
			}
			return {
				sidebar: candidates[0],
				reason: `derived from route entity "${entity}", which appears in: ${candidates.join(
					", "
				)}`,
			};
		}

		// 2. the entity isn't linked anywhere -> fall back to its module's app shell, before
		// keeping the last selection, so custom/standalone doctypes land in their own app.
		const module_sidebar = this.sidebar_from_module(entity);
		if (module_sidebar) {
			return {
				sidebar: module_sidebar,
				reason: `derived from "${entity}"'s module app — no sidebar links it directly`,
			};
		}

		// 3. nothing ties the route to a sidebar -> keep the last selection
		if (persisted) {
			return {
				sidebar: persisted,
				reason: `last selected sidebar "${persisted}" — route "${entity}" belongs to no sidebar, so the selection is kept`,
			};
		}

		// 4. first available
		const first = Object.values(all)[0];
		return {
			sidebar: first && first.label,
			reason: `fallback to the first available sidebar (route entity "${entity}" matched none)`,
		};
	}

	// Debug helper: explain why the current sidebar is shown.
	// Call from the console as `frappe.app.sidebar.explain_sidebar()`.
	explain(route = frappe.get_route()) {
		const { sidebar: resolved, reason } = this.resolve_initial_sidebar(route);
		const current = this.sidebar_title;
		const was_manually_selected =
			current && resolved && current.toLowerCase() !== resolved.toLowerCase();

		const info = {
			current_sidebar: current,
			route,
			reason: was_manually_selected
				? `shown because it was explicitly selected ("${current}"). On a cold reload it would instead resolve to "${resolved}" — ${reason}`
				: reason,
			resolved_on_reload: resolved,
		};
		console.info("[sidebar] why:", info);
		return info;
	}

	// The autogenerated sidebar for the entity's module, or null. Used to place an entity that no
	// sidebar links directly into its own module's sidebar (every module has one). The module's
	// autogenerated sidebar is keyed by the module name, so we look it up directly rather than
	// scanning for the first sidebar carrying the module -- the latter varies per user as
	// permission filtering changes which sidebars survive and in what order. Returns null when the
	// module can't be determined (e.g. meta not loaded yet) or has no sidebar.
	sidebar_from_module(entity) {
		const meta = entity && frappe.get_meta(entity);
		if (!meta?.module) return null;
		const sidebar = this.all_sidebar_items?.[meta.module.toLowerCase()];
		return sidebar ? sidebar.label : null;
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

	// Titles of every sidebar that contains `link_to`, across all apps. Resolution is app-blind on
	// purpose (see set_workspace_sidebar) so curated cross-app links resolve correctly.
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

		// If one of these workspaces owns the entity (its item is flagged default_workspace),
		// surface it first so callers that take the top candidate land in the workspace the entity
		// belongs to.
		const owner = this.default_workspace_for(link_to);
		if (owner && sidebars.some((s) => s.toLowerCase() === owner.toLowerCase())) {
			sidebars = [owner, ...sidebars.filter((s) => s.toLowerCase() !== owner.toLowerCase())];
		}
		return sidebars;
	}

	// The workspace an entity belongs to, or undefined. An entity (link_to) can appear in
	// several sidebars; the item flagged `default_workspace` marks its owning workspace, so
	// navigation can route the doctype to that shell's sidebar. The map is built server-side
	// (bootinfo.default_workspace_map) from the permission-filtered sidebar payload.
	default_workspace_for(link_to) {
		const map = frappe.boot.default_workspace_map || {};
		return link_to ? map[link_to] : undefined;
	}
};
