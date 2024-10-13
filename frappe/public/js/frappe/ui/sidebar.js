frappe.provide("frappe.ui");

frappe.ui.Sidebar = class Sidebar {
	constructor() {
		this.items = {};

		if (!frappe.boot.setup_complete) {
			// no sidebar if setup is not complete
			return;
		}

		this.set_all_pages();
		this.make_dom();
		this.sidebar_items = {
			public: {},
			private: {},
		};
		this.indicator_colors = [
			"green",
			"cyan",
			"blue",
			"orange",
			"yellow",
			"gray",
			"grey",
			"red",
			"pink",
			"darkgrey",
			"purple",
			"light-blue",
		];

		this.setup_pages();
	}

	make_dom() {
		this.set_default_app();
		this.wrapper = $(
			frappe.render_template("sidebar", {
				app_logo_url: frappe.boot.app_data[0].app_logo_url,
				app_title: __(frappe.boot.app_data[0].app_title),
			})
		).prependTo("body");

		this.$sidebar = this.wrapper.find(".sidebar-items");

		if (this.has_access) {
			this.wrapper
				.find(".body-sidebar .edit-sidebar-link")
				.removeClass("hidden")
				.on("click", () => {
					frappe.quick_edit("Workspace Settings");
				});
		}

		this.setup_app_switcher();
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

	setup_app_switcher() {
		let app_switcher_menu = $(".app-switcher-menu");

		$(".app-switcher-dropdown").on("click", () => {
			app_switcher_menu.toggleClass("hidden");
		});

		// hover out of the sidebar
		this.wrapper.find(".body-sidebar").on("mouseleave", () => {
			app_switcher_menu.addClass("hidden");

			// hide any expanded menus as they leave a blank space in the sidebar
			this.wrapper.find(".drop-icon[data-state='opened'").click();
		});

		frappe.boot.app_data_map = {};
		this.add_private_app(app_switcher_menu);

		for (var app of frappe.boot.app_data) {
			frappe.boot.app_data_map[app.app_name] = app;
			if (app.workspaces?.length) {
				this.add_app_item(app, app_switcher_menu);
			}
		}
		this.add_website_select(app_switcher_menu);
		this.setup_select_app(app_switcher_menu);
	}

	add_app_item(app, app_switcher_menu) {
		$(`<div class="app-item" data-app-name="${app.app_name}"
			data-app-route="${app.app_route}">
			<a>
				<div class="sidebar-item-icon">
					<img
						class="app-logo"
						src="${app.app_logo_url}"
						alt="${__("App Logo")}"
					>
				</div>
				<span class="app-item-title">${app.app_title}</span>
			</a>
		</div>`).appendTo(app_switcher_menu);
	}

	add_private_app(app_switcher_menu) {
		let private_pages = this.all_pages.filter((p) => p.public === 0);
		if (private_pages.length === 0) return;

		const app = {
			app_name: "private",
			app_title: __("My Workspaces"),
			app_route: "/app/private",
			app_logo_url: "/assets/frappe/images/frappe-framework-logo.svg",
			workspaces: private_pages,
		};

		frappe.boot.app_data_map["private"] = app;
		$(`<div class="divider"></div>`).prependTo(app_switcher_menu);
		$(`<div class="app-item" data-app-name="${app.app_name}"
			data-app-route="${app.app_route}">
			<a>
				<div class="sidebar-item-icon">
					<img
						class="app-logo"
						src="${app.app_logo_url}"
						alt="${__("App Logo")}"
					>
				</div>
				<span class="app-item-title">${app.app_title}</span>
			</a>
		</div>`).prependTo(app_switcher_menu);
	}

	setup_select_app(app_switcher_menu) {
		app_switcher_menu.find(".app-item").on("click", (e) => {
			let item = $(e.delegateTarget);
			let route = item.attr("data-app-route");
			app_switcher_menu.toggleClass("hidden");

			if (route.startsWith("/app/private")) {
				this.set_current_app("private");
				let ws = Object.values(frappe.workspace_map).find((ws) => ws.public === 0);
				route += "/" + frappe.router.slug(ws.title);
				frappe.set_route(route);
			} else if (route.startsWith("/app")) {
				frappe.set_route(route);
				this.set_current_app(item.attr("data-app-name"));
			} else {
				// new page
				window.open(route);
			}
		});
	}

	set_current_app(app) {
		if (!app) {
			console.warn("set_current_app: app not defined");
			return;
		}
		let app_data = frappe.boot.app_data_map[app] || frappe.boot.app_data_map["frappe"];

		this.wrapper
			.find(".app-switcher-dropdown .sidebar-item-icon img")
			.attr("src", app_data.app_logo_url);
		this.wrapper.find(".app-switcher-dropdown .sidebar-item-label").html(app_data.app_title);

		$(".navbar-brand .app-logo").attr("src", app_data.app_logo_url);

		if (frappe.current_app === app) return;
		frappe.current_app = app;

		// re-render the sidebar
		this.make_sidebar();
	}

	add_website_select(app_switcher_menu) {
		$(`<div class="divider"></div>`).appendTo(app_switcher_menu);
		this.add_app_item(
			{
				app_name: "website",
				app_title: __("Website"),
				app_route: "/",
				app_logo_url: "/assets/frappe/images/web.svg",
			},
			app_switcher_menu
		);
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
			this.make_sidebar();
		}
	}

	make_sidebar() {
		if (this.wrapper.find(".standard-sidebar-section")[0]) {
			this.wrapper.find(".standard-sidebar-section").remove();
		}

		let app_workspaces = frappe.boot.app_data_map[frappe.current_app || "frappe"].workspaces;

		let parent_pages = this.all_pages.filter((p) => !p.parent_page).uniqBy((p) => p.name);
		if (frappe.current_app === "private") {
			parent_pages = parent_pages.filter((p) => !p.public);
		} else {
			parent_pages = parent_pages.filter((p) => p.public && app_workspaces.includes(p.name));
		}

		this.build_sidebar_section("All", parent_pages);

		// Scroll sidebar to selected page if it is not in viewport.
		this.wrapper.find(".selected").length &&
			!frappe.dom.is_element_in_viewport(this.wrapper.find(".selected")) &&
			this.wrapper.find(".selected")[0].scrollIntoView();

		this.setup_sorting();
	}

	build_sidebar_section(title, root_pages) {
		let sidebar_section = $(
			`<div class="standard-sidebar-section nested-container" data-title="${title}"></div>`
		);

		this.prepare_sidebar(root_pages, sidebar_section, this.wrapper.find(".sidebar-items"));

		if (Object.keys(root_pages).length === 0) {
			sidebar_section.addClass("hidden");
		}

		$(".item-anchor").on("click", () => {
			$(".list-sidebar.hidden-xs.hidden-sm").removeClass("opened");
			$(".close-sidebar").css("display", "none");
			$("body").css("overflow", "auto");
		});

		if (
			sidebar_section.find(".sidebar-item-container").length &&
			sidebar_section.find("> [item-is-hidden='0']").length == 0
		) {
			sidebar_section.addClass("hidden show-in-edit-mode");
		}
	}

	prepare_sidebar(items, child_container, item_container) {
		let last_item = null;
		for (let item of items) {
			if (item.public && last_item && !last_item.public) {
				$(`<div class="divider"></div>`).appendTo(child_container);
			}

			// visibility not explicitly set to 0
			if (item.visibility !== 0) {
				this.append_item(item, child_container);
			}
			last_item = item;
		}
		child_container.appendTo(item_container);
	}

	append_item(item, container) {
		let is_current_page = false;

		item.selected = is_current_page;

		if (is_current_page) {
			this.current_page = { name: item.name, public: item.public };
		}

		let $item_container = this.sidebar_item_container(item);
		let sidebar_control = $item_container.find(".sidebar-item-control");

		let child_items = this.all_pages.filter(
			(page) => page.parent_page == item.name || page.parent_page == item.title
		);
		if (child_items.length > 0) {
			let child_container = $item_container.find(".sidebar-child-item");
			child_container.addClass("hidden");
			this.prepare_sidebar(child_items, child_container, $item_container);
		}

		$item_container.appendTo(container);
		this.sidebar_items[item.public ? "public" : "private"][item.name] = $item_container;

		if ($item_container.parent().hasClass("hidden") && is_current_page) {
			$item_container.parent().toggleClass("hidden");
		}

		this.add_toggle_children(item, sidebar_control, $item_container);

		if (child_items.length > 0) {
			$item_container.find(".drop-icon").first().addClass("show-in-edit-mode");
		}
	}

	sidebar_item_container(item) {
		item.indicator_color =
			item.indicator_color || this.indicator_colors[Math.floor(Math.random() * 12)];
		let path;
		if (item.type === "Link") {
			if (item.link_type === "Report") {
				path = frappe.utils.generate_route({
					type: item.link_type,
					name: item.link_to,
					is_query_report: item.report.report_type === "Query Report",
					report_ref_doctype: item.report.ref_doctype,
				});
			} else {
				path = frappe.utils.generate_route({ type: item.link_type, name: item.link_to });
			}
		} else if (item.type === "URL") {
			path = item.external_link;
		} else {
			if (item.public) {
				path = "/app/" + frappe.router.slug(item.name);
			} else {
				path = "/app/private/" + frappe.router.slug(item.name.split("-")[0]);
			}
		}

		return $(`
			<div
				class="sidebar-item-container ${item.is_editable ? "is-draggable" : ""}"
				item-parent="${item.parent_page}"
				item-name="${item.name}"
				item-title="${item.title}"
				item-public="${item.public || 0}"
				item-is-hidden="${item.is_hidden || 0}"
			>
				<div class="standard-sidebar-item ${item.selected ? "selected" : ""}">
					<a
						href="${path}"
						target="${item.type === "URL" ? "_blank" : ""}"
						class="item-anchor ${item.is_editable ? "" : "block-click"}" title="${__(item.title)}"
					>
						<span class="sidebar-item-icon" item-icon=${item.icon || "folder-normal"}>
							${
								item.public || item.icon
									? frappe.utils.icon(item.icon || "folder-normal", "md")
									: `<span class="indicator ${item.indicator_color}"></span>`
							}
						</span>
						<span class="sidebar-item-label">${__(item.title)}<span>
					</a>
					<div class="sidebar-item-control"></div>
				</div>
				<div class="sidebar-child-item nested-container"></div>
			</div>
		`);
	}

	add_toggle_children(item, sidebar_control, item_container) {
		let drop_icon = "es-line-down";
		if (
			this.current_page &&
			item_container.find(`[item-name="${this.current_page.name}"]`).length
		) {
			drop_icon = "small-up";
		}

		let $child_item_section = item_container.find(".sidebar-child-item");
		let $drop_icon = $(`<button class="btn-reset drop-icon hidden">`)
			.html(frappe.utils.icon(drop_icon, "sm"))
			.appendTo(sidebar_control);

		if (
			this.all_pages.some(
				(e) =>
					(e.parent_page == item.title || e.parent_page == item.name) &&
					(e.is_hidden == 0 || !this.is_read_only)
			)
		) {
			$drop_icon.removeClass("hidden");
		}
		$drop_icon.on("click", () => {
			let opened = $drop_icon.find("use").attr("href") === "#es-line-down";

			if (!opened) {
				$drop_icon.attr("data-state", "closed").find("use").attr("href", "#es-line-down");
			} else {
				$drop_icon.attr("data-state", "opened").find("use").attr("href", "#es-line-up");
			}
			``;
			$child_item_section.toggleClass("hidden");
		});
	}

	setup_sorting() {
		if (!this.has_access) return;

		for (let container of this.$sidebar.find(".nested-container")) {
			Sortable.create(container, {
				group: "sidebar-items",
				fitler: ".divider",
				onEnd: () => {
					let sidebar_items = [];
					for (let container of this.$sidebar.find(".nested-container")) {
						for (let item of $(container).children()) {
							let parent = "";
							if ($(item).parent().hasClass("sidebar-child-item")) {
								parent = $(item)
									.parent()
									.closest(".sidebar-item-container")
									.attr("item-name");
							}

							sidebar_items.push({
								name: item.getAttribute("item-name"),
								parent: parent,
							});
						}
					}
					frappe.xcall(
						"frappe.desk.doctype.workspace_settings.workspace_settings.set_sequence",
						{
							sidebar_items: sidebar_items,
						}
					);
				},
			});
		}
	}

	reload() {
		return frappe.workspace.get_pages().then((r) => {
			frappe.boot.sidebar_pages = r;
			this.setup_pages();
		});
	}
};
