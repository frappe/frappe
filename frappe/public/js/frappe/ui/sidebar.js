frappe.ui.Sidebar = class Sidebar {
	constructor() {
		this.items = {};
		this.sidebar_expanded = false;

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
		this.apps_switcher.populate_apps_menu();
	}

	make_dom() {
		this.set_default_app();
		this.wrapper = $(frappe.render_template("sidebar")).prependTo("body");

		this.app_switcher_dropdown = $(
			frappe.render_template("apps_switcher", {
				app_logo_url: frappe.boot.app_data[0].app_logo_url,
				app_title: __(frappe.boot.app_data[0].app_title),
			})
		).prependTo(this.wrapper.find(".body-sidebar"));

		this.$sidebar = this.wrapper.find(".sidebar-items");

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
		if (this.is_route_in_sidebar(decodeURIComponent(window.location.pathname))) {
			this.active_item.addClass("active-sidebar");
		}
	}

	is_route_in_sidebar(route_name) {
		let match = false;
		const that = this;
		$(".item-anchor").each(function () {
			if ($(this).attr("href") == route_name) {
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
			this.make_sidebar();
		}
		this.set_hover();
		if (localStorage.getItem("sidebar-expanded") !== null) {
			this.sidebar_expanded = JSON.parse(localStorage.getItem("sidebar-expanded"));
			this.expand_sidebar();
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
		this.set_active_workspace_item();
		this.set_hover();
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
			// $(".close-sidebar").css("display", "none");
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
	toggle_sidebar() {
		if (!this.sidebar_expanded) {
			this.open_sidebar();
		} else {
			this.close_sidebar();
		}
	}
	expand_sidebar() {
		let direction;
		if (this.sidebar_expanded) {
			this.wrapper.addClass("expanded");
			// this.sidebar_expanded = false
			direction = "left";
		} else {
			this.wrapper.removeClass("expanded");
			// this.sidebar_expanded = true
			direction = "right";
		}
		localStorage.setItem("sidebar-expanded", this.sidebar_expanded);
		this.wrapper
			.find(".body-sidebar .collapse-sidebar-link")
			.find("use")
			.attr("href", `#icon-arrow-${direction}-to-line`);
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
	toggle_sorting() {
		this.sorting_items.forEach((item) => {
			var state = item.option("disabled");
			item.option("disabled", !state);
		});
	}
	setup_sorting() {
		if (!this.has_access) return;
		this.sorting_items = [];
		for (let container of this.$sidebar.find(".nested-container")) {
			this.sorting_items[this.sorting_items.length] = Sortable.create(container, {
				group: "sidebar-items",
				disabled: true,
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

	close_sidebar() {
		this.sidebar_expanded = false;
		this.expand_sidebar();
	}
	open_sidebar() {
		this.sidebar_expanded = true;
		this.expand_sidebar();
	}

	reload() {
		return frappe.workspace.get_pages().then((r) => {
			frappe.boot.sidebar_pages = r;
			this.setup_pages();
		});
	}
};
