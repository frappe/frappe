frappe.provide("frappe.ui");

frappe.ui.Sidebar = class Sidebar {
	constructor() {
		this.items = {};

		if (!frappe.boot.setup_complete) {
			// no sidebar if setup is not complete
			return;
		}

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
		this.wrapper = $(`
			<div class="body-sidebar-container">
				<div class="body-sidebar-placeholder"></div>
				<div class="body-sidebar">
					<a href="/app" style="text-decoration: none">
						<div class="standard-sidebar-item">
							<div class="sidebar-item-icon">
								<img
									class="app-logo"
									src="${frappe.boot.app_logo_url}"
									alt="${__("App Logo")}"
								>
							</div>
							<div class="sidebar-item-label" style="margin-left: 5px; margin-top: 1px">
								${__(frappe.boot.sysdefaults.app_name)}
							</div>
						</div>
					</a>
					<div class="sidebar-items">
					</div>
					<div class="mb-4">
						<a class="edit-sidebar-link text-extra-muted">Edit sidebar</a>
					</div>
				</div>
			</div>
		`).prependTo("body");

		this.$sidebar = this.wrapper.find(".sidebar-items");

		this.wrapper.find(".body-sidebar .edit-sidebar-link").on("click", () => {
			frappe.quick_edit("Workspace Settings");
		});
	}

	setup_pages() {
		this.sidebar_pages = frappe.boot.sidebar_pages;
		this.all_pages = this.sidebar_pages.pages;
		this.has_access = this.sidebar_pages.has_access;
		this.has_create_access = this.sidebar_pages.has_create_access;

		this.all_pages.forEach((page) => {
			page.is_editable = !page.public || this.has_access;
		});

		if (this.all_pages) {
			frappe.workspaces = {};
			frappe.workspace_list = [];
			for (let page of this.all_pages) {
				frappe.workspaces[frappe.router.slug(page.name)] = {
					title: page.title,
					public: page.public,
				};

				frappe.workspace_list.push(page);
			}
			this.make_sidebar();
		}
	}

	make_sidebar() {
		if (this.wrapper.find(".standard-sidebar-section")[0]) {
			this.wrapper.find(".standard-sidebar-section").remove();
		}

		let parent_pages = this.all_pages.filter((p) => !p.parent_page).uniqBy((p) => p.title);
		parent_pages = [
			...parent_pages.filter((p) => !p.public),
			...parent_pages.filter((p) => p.public),
		];

		this.build_sidebar_section("All", parent_pages);

		// Scroll sidebar to selected page if it is not in viewport.
		this.wrapper.find(".selected").length &&
			!frappe.dom.is_element_in_viewport(this.wrapper.find(".selected")) &&
			this.wrapper.find(".selected")[0].scrollIntoView();
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
		for (let item of items) {
			// visibility not explicitly set to 0
			if (item.visibility !== 0) {
				this.append_item(item, child_container);
			}
		}
		child_container.appendTo(item_container);
	}

	append_item(item, container) {
		let is_current_page = false;

		item.selected = is_current_page;

		if (is_current_page) {
			this.current_page = { name: item.title, public: item.public };
		}

		let $item_container = this.sidebar_item_container(item);
		let sidebar_control = $item_container.find(".sidebar-item-control");

		let child_items = this.all_pages.filter((page) => page.parent_page == item.title);
		if (child_items.length > 0) {
			let child_container = $item_container.find(".sidebar-child-item");
			child_container.addClass("hidden");
			this.prepare_sidebar(child_items, child_container, $item_container);
		}

		$item_container.appendTo(container);
		this.sidebar_items[item.public ? "public" : "private"][item.title] = $item_container;

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

		return $(`
			<div
				class="sidebar-item-container ${item.is_editable ? "is-draggable" : ""}"
				item-parent="${item.parent_page}"
				item-name="${item.title}"
				item-public="${item.public || 0}"
				item-is-hidden="${item.is_hidden || 0}"
			>
				<div class="standard-sidebar-item ${item.selected ? "selected" : ""}">
					<a
						href="/app/${
							item.public
								? frappe.router.slug(item.title)
								: "private/" + frappe.router.slug(item.title)
						}"
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
				(e) => e.parent_page == item.title && (e.is_hidden == 0 || !this.is_read_only)
			)
		) {
			$drop_icon.removeClass("hidden");
		}
		$drop_icon.on("click", () => {
			let icon =
				$drop_icon.find("use").attr("href") === "#es-line-down"
					? "#es-line-up"
					: "#es-line-down";
			$drop_icon.find("use").attr("href", icon);
			$child_item_section.toggleClass("hidden");
		});
	}
};
