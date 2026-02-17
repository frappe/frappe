frappe.desktop_utils = {};
frappe.desktop_grids = [];
frappe.desktop_icons_objects = [];
frappe.new_icons = [];
$.extend(frappe.desktop_utils, {
	modal: null,
	modal_stack: [],
	create_desktop_modal: function (icon, icon_title, icons_data, grid) {
		if (!this.modal) {
			this.modal = new DesktopModal(icon);
		}
		this.modal_stack.push(icon);
		return this.modal;
	},
	close_desktop_modal: function () {
		if (this.modal) {
			this.modal.hide();
		}
	},
});
frappe.pages["desktop"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Desktop",
		single_column: true,
		hide_sidebar: true,
	});
	let desktop_page = new DesktopPage(page);
	frappe.pages["desktop"].desktop_page = desktop_page;
	// setup();
};

function get_workspaces_from_app_name(app_name) {
	const app = frappe.boot.app_data.filter((a) => {
		return a.app_title === app_name;
	});
	if (app.length > 0) return app[0].workspaces;
}

function get_route(desktop_icon) {
	let route;
	if (!desktop_icon) return;
	let item = {};
	if (desktop_icon.link_type == "External" && desktop_icon.link) {
		route = window.location.origin + desktop_icon.link;
		if (desktop_icon.link.startsWith("http") || desktop_icon.link.startsWith("https")) {
			route = desktop_icon.link;
		}
	} else {
		let sidebar = frappe.boot.workspace_sidebar_item[desktop_icon.label.toLowerCase()];
		if (desktop_icon.link_type == "Workspace Sidebar" && sidebar) {
			let first_link = sidebar.items.find((i) => i.type == "Link");
			if (first_link) {
				if (first_link.link_type === "Report") {
					let args = {
						type: first_link.link_type,
						name: first_link.link_to,
					};

					if (first_link.report || !frappe.app.sidebar.editor.edit_mode) {
						args.is_query_report =
							first_link.report.report_type === "Query Report" ||
							first_link.report.report_type == "Script Report";
						args.report_ref_doctype = first_link.report.ref_doctype;
					}

					route = frappe.utils.generate_route(args);
				} else if (first_link.link_type == "Workspace") {
					let workspaces = frappe.workspaces[frappe.router.slug(first_link.link_to)];
					if (workspaces) {
						let args = {
							type: "workspace",
							name: first_link.link_to,
							public: workspaces.public ? 1 : 0,
							route_options: {
								sidebar: desktop_icon.label,
							},
						};
						route = frappe.utils.generate_route(args);
					}
				} else if (first_link.link_type === "URL") {
					route = first_link.url;
				} else if (first_link.link_type == "Page" && first_link.route_options) {
					route = frappe.utils.generate_route({
						type: first_link.link_type,
						name: first_link.link_to,
						route_options: JSON.parse(first_link.route_options),
					});
				} else {
					route = frappe.utils.generate_route({
						type: first_link.link_type,
						name: first_link.link_to,
						tab: first_link.tab,
						route_options: {
							sidebar: desktop_icon.label,
						},
					});
				}
			}
		}
	}
	return route;
}

function get_desktop_icon_by_label(title, filters, force) {
	if (force === undefined) force = false;
	let icons = frappe.desktop_icons;
	if (!force && frappe.pages["desktop"].desktop_page.edit_mode) {
		icons = frappe.new_desktop_icons;
	}
	if (!filters) {
		return icons.find((f) => f.label === title);
	} else {
		return icons.find((f) => {
			return (
				f.label === title && Object.keys(filters).every((key) => f[key] === filters[key])
			);
		});
	}
}

function get_desktop_icon_by_idx(idx, parent_icon) {
	return frappe.boot.desktop_icons.find((f) => f.idx == idx && f.parent_icon == parent_icon);
}

function save_desktop(icons) {
	// saving in localStorage;
	frappe.pages["desktop"].desktop_page.save_layout(icons, frappe.new_icons);
}

function reset_to_default() {
	frappe.call({
		method: "frappe.desk.doctype.desktop_layout.desktop_layout.delete_layout",
		callback: function (r) {
			frappe.ui.toolbar.clear_cache();
		},
	});
}

function toggle_icons(icons) {
	icons.forEach((i) => {
		$(i).parent().parent().show();
	});
}

frappe.desktop_utils.get_folder_icons = function (folder_name) {
	let icons_in_folder = [];
	let icons = frappe.desktop_icons;
	if (frappe.pages["desktop"].desktop_page.edit_mode) {
		icons = frappe.new_desktop_icons;
	}
	icons.forEach((icon) => {
		if (icon.parent_icon == folder_name) {
			icons_in_folder.push(icon.label);
		}
	});
	return icons_in_folder;
};

function add_icons_to_folder(folder_name, items) {
	let folder = get_desktop_icon_by_label(folder_name);
	items.forEach((item) => {
		let icon = get_desktop_icon_by_label(item);
		icon.parent_icon = folder.label;
	});
	frappe.pages["desktop"].desktop_page.update();
}

class DesktopPage {
	constructor(page) {
		this.page = page;
		this.edit_mode = false;
		this.desktop_menu_items = [];
		this.make(this.page);
		this.setup();
	}
	update() {
		this.make(this.page);
		this.setup();
	}
	prepare() {
		this.apps_icons = [];
		this.hidden_icons = [];
		this.folders = [];
		const icon_map = {};
		let icons = this.edit_mode ? frappe.new_desktop_icons : frappe.desktop_icons;
		const all_icons = icons.filter((icon) => {
			if (icon.hidden != 1) {
				icon.child_icons = [];
				icon_map[icon.label] = icon;
				if (icon.icon_type == "Folder") {
					this.folders.push(icon.label);
				}
				return true;
			} else {
				this.hidden_icons.push(icon);
			}
			return false;
		});
		all_icons.forEach((icon) => {
			if (icon.parent_icon && icon_map[icon.parent_icon]) {
				icon_map[icon.parent_icon].child_icons.push(icon);
			}

			if (!icon.parent_icon || !icon_map[icon.parent_icon]) {
				this.apps_icons.push(icon);
			}
		});
	}
	get_saved_layout() {
		let keywords = ["null", "undefined"];
		if (keywords.includes(localStorage.getItem(`${frappe.session.user}:desktop`))) {
			return null;
		}
		return JSON.parse(localStorage.getItem(`${frappe.session.user}:desktop`));
	}
	sync_layout() {
		const me = this;
		let saved_layout = JSON.parse(localStorage.getItem(`${frappe.session.user}:desktop`));
		if (!this.data && saved_layout) {
			this.save_layout(saved_layout);
		} else if (Object.keys(this.data).length != 0) {
			frappe.desktop_icons = this.data;
		} else {
			frappe.desktop_icons = frappe.boot.desktop_icons;
		}
	}
	save_layout(layout, new_icons) {
		const me = this;
		frappe.call({
			method: "frappe.desk.doctype.desktop_layout.desktop_layout.save_layout",
			args: {
				user: frappe.session.user,
				layout: JSON.stringify(layout),
				new_icons: JSON.stringify(new_icons),
			},
			callback: function (r) {
				me.data = r.message.layout;
				me.make(me.page);
				me.setup();
				frappe.new_icons = [];
			},
		});
	}
	make() {
		this.page.page_head.hide();
		$(this.page.body).empty();
		$(frappe.render_template("desktop")).appendTo(this.page.body);
		if (!this.data) {
			this.data = JSON.parse($("#desktop-layout").text());
		}
		this.sync_layout();
		this.prepare();
		this.wrapper = this.page.body.find(".desktop-container");
		this.icon_grid = new DesktopIconGrid({
			wrapper: this.wrapper,
			icons_data: this.apps_icons,
			page_size: {
				row: 6,
				col: 3,
			},
		});
		this.setup_context_menu();
		if (this.edit_mode) {
			this.start_editing_layout();
		}
	}

	setup() {
		$(document).trigger("desktop_screen", { desktop: this });
		this.setup_avatar();
		this.setup_notifications();
		this.setup_navbar();
		this.setup_awesomebar();
		this.handle_route_change();
		this.setup_edit_button();
	}
	setup_edit_button() {
		if (this.edit_mode || frappe.is_mobile()) return;
		const me = this;
		$(".desktop-edit").remove();
		this.$desktop_edit_button = $(
			"<button class='btn btn-reset desktop-edit'></button>"
		).appendTo(document.body);
		this.$desktop_edit_button.html(
			frappe.utils.icon("square-pen", "md", "", "", "", "", "white")
		);
		this.$desktop_edit_button.on("click", () => {
			frappe.new_desktop_icons = JSON.parse(JSON.stringify(frappe.desktop_icons));
			me.start_editing_layout();
		});
	}
	setup_context_menu() {
		const me = this;
		let menu_items = [
			{
				label: "Edit Layout",
				icon: "edit",
				condition: function () {
					return !me.edit_mode;
				},
				onClick: function () {
					me.$desktop_edit_button.hide();
					frappe.new_desktop_icons = JSON.parse(JSON.stringify(frappe.desktop_icons));
					me.start_editing_layout();
				},
			},
			{
				label: "Reset Layout",
				icon: "rotate-ccw",
				onClick: function () {
					reset_to_default();
					me.update();
				},
			},
		];
		frappe.ui.create_menu({
			parent: this.wrapper,
			menu_items: menu_items,
			right_click: true,
		});
	}
	stop_editing_layout(action) {
		this.edit_mode = false;
		$(".desktop-icon").not(".folder-icon .desktop-icon").removeClass("desktop-edit-mode");
		$(".desktop-wrapper").removeAttr("data-mode");
		$(".add-new-icon").remove();
		this.desktop_pane.hide();
		if (action === "cancel") {
			frappe.new_desktop_icons = null;
			this.update();
			return;
		}
		// submit
		save_desktop(frappe.new_desktop_icons);
	}

	start_editing_layout() {
		this.edit_mode = true;
		const me = this;
		this.desktop_pane = new IconsPane();
		$(".desktop-wrapper").attr("data-mode", "Edit");
		$(".desktop-edit").remove();
		frappe.desktop_icons_objects.forEach((icon) => {
			icon.edit_mode = true;
		});
		frappe.desktop_grids.forEach((desktop_grid) => {
			if (!desktop_grid.no_dragging) {
				desktop_grid.grids.forEach((grid) => {
					desktop_grid.setup_reordering(grid);
				});
			}
		});
		this.add_new_icons_to_grid();
		if (this.edit_mode) {
			this.setup_edit_buttons();
			this.desktop_pane.show();
		}
	}
	add_new_icons_to_grid() {
		let grid = $($(".desktop-container .icons").get(0));
		this.add_new_icon = `<div class="desktop-icon desktop-edit-mode add-new-icon" title="Add New Icon">
		 ${frappe.utils.icon("plus", "lg")}
		 New Icon
		 </div>`;
		grid.append(this.add_new_icon);
		$(".add-new-icon").on("click", function () {
			frappe.ui.form.make_quick_entry(
				"Desktop Icon",
				function (icon) {
					frappe.new_desktop_icons.push(icon);
					frappe.new_icons.push(icon);
					frappe.pages["desktop"].desktop_page.update();
				},
				"",
				"",
				null,
				true,
				true
			);
		});
	}
	setup_edit_buttons() {
		const me = this;
		this.$edit_button = $(".edit-mode-buttons");
		this.$edit_button.find(".discard").on("click", function () {
			me.stop_editing_layout("cancel");
			me.delete_new_icons();
			$($(".desktop-container .icons").get(0)).find(".add-new-icon").remove();
		});
		this.$edit_button.find(".save").on("click", function () {
			me.stop_editing_layout("submit");
		});
	}
	setup_notifications() {
		this.notifications = new frappe.ui.Notifications({
			wrapper: $(".desktop-notifications"),
			full_height: false,
		});
	}

	delete_new_icons() {
		frappe.new_icons = [];
	}

	setup_avatar() {
		$(".desktop-avatar").html(frappe.avatar(frappe.session.user, "avatar-medium"));
		let is_dark = document.documentElement.getAttribute("data-theme") === "dark";
		let menu_items = [
			{
				icon: "edit",
				label: "Edit Profile",
				url: `/desk/user/${frappe.session.user}`,
			},
			{
				icon: is_dark ? "sun" : "moon",
				label: "Toggle Theme",
				onClick: function () {
					new frappe.ui.ThemeSwitcher().show();
				},
			},
			{
				icon: "info",
				label: "About",
				onClick: function () {
					return frappe.ui.toolbar.show_about();
				},
			},
			{
				icon: "support",
				label: "Frappe Support",
				onClick: function () {
					window.open("https://support.frappe.io/help", "_blank");
				},
			},
			{
				icon: "rotate-ccw",
				label: "Reset Desktop Layout",
				onClick: function () {
					reset_to_default();
					window.location.reload();
				},
			},
			{
				icon: "log-out",
				label: "Logout",
				onClick: function () {
					frappe.app.logout();
				},
			},
		];
		if (this.desktop_menu_items && this.desktop_menu_items.length)
			menu_items = [...menu_items, ...this.desktop_menu_items];
		frappe.ui.create_menu({
			parent: $(".desktop-avatar"),
			menu_items: menu_items,
			// If it's RTL, we want it to open on the right (false);
			// if it's LTR, we want it to open on the left (true).
			open_on_left: !frappe.utils.is_rtl(),
		});
	}
	add_menu_item(item) {
		if (this.desktop_menu_items && this.desktop_menu_items.find((i) => i.label === item.label))
			return;
		this.desktop_menu_items.push(item);
	}
	setup_navbar() {
		$(".sticky-top > .navbar").hide();
	}

	setup_awesomebar() {
		if (!frappe.is_mobile()) {
			$(".desktop-keyboard-shortcut").html("Ctrl+K");
			if (frappe.utils.is_mac()) {
				$(".desktop-keyboard-shortcut").html("⌘K");
			}
		}
		if (this.awesomebar_setup) return;
		this.awesomebar_setup = true;

		if (frappe.boot.desk_settings.search_bar) {
			let awesome_bar = new frappe.search.AwesomeBar();
			awesome_bar.setup(".desktop-search-wrapper #desktop-navbar-modal-search");
		}
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+g",
			action: function (e) {
				$(".desktop-search-wrapper #desktop-navbar-modal-search").click();
				e.preventDefault();
				return false;
			},
			description: __("Open Awesomebar"),
		});
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+k",
			action: function (e) {
				$(".desktop-search-wrapper #desktop-navbar-modal-search").click();
				e.preventDefault();
				return false;
			},
			description: __("Open Awesomebar"),
		});
	}
	handle_route_change() {
		const me = this;
		frappe.router.on("change", function () {
			if (frappe.get_route()[0] == "desktop" || frappe.get_route()[0] == "") {
				me.setup_navbar();
				me.setup_edit_button();
			} else {
				$(".navbar").show();
				frappe.desktop_utils.close_desktop_modal();
				// stop edit mode if route changes and cleanup
				me.edit_mode = false;
				$(".desktop-icon").removeClass("edit-mode");
				$(".desktop-wrapper").removeAttr("data-mode");
				$(".desktop-edit").remove();
			}
		});
	}
}

class DesktopIconGrid {
	constructor(opts) {
		$.extend(this, opts);
		this.init();
	}
	static folder_count = 0;
	init() {
		this.icons = [];
		this.icons_html = [];
		// this.page_size = {
		// 	col: opts.page_size?.col || 4,
		// 	row: opts.page_size?.row || 3,
		// 	total: function () {
		// 		return this.col * this.row;
		// 	},
		// };
		this.grids = [];
		this.prepare();
		this.make();
		frappe.desktop_grids.push(this);
	}
	add_folder() {
		DesktopIconGrid.folder_count++;
		let icon = frappe.model.get_new_doc("Desktop Icon");
		icon.icon_type = "Folder";
		icon.label = `Untitled ${DesktopIconGrid.folder_count}`;
		icon.idx = 100000;
		frappe.new_desktop_icons.push(icon);
		frappe.new_icons.push(icon);
		return icon;
	}
	prepare() {
		this.total_pages = 1;
		this.icons_data = this.icons_data.sort((a, b) => {
			if (a.idx === b.idx) {
				return a.label.localeCompare(b.label); // sort by label if idx is the same
			}
			return a.idx - b.idx; // sort by idx
		});
		this.icons_data_by_page =
			this.icons_data || this.split_data(this.icons_data, this.page_size.total());
	}
	make() {
		const me = this;
		this.icons_container = $(`<div class="icons-container"></div>`).appendTo(this.wrapper);
		if (this.compact) {
			this.icons_container.css("margin-top", "0px");
		}
		for (let i = 0; i < this.total_pages; i++) {
			let template = `<div class="icons"></div>`;

			if (this.row_size) {
				template = `<div class="icons" style="display: none; grid-template-columns: repeat(${this.row_size}, 1fr)"></div>`;
			}
			if (frappe.is_mobile()) {
				template = `<div class="icons" style="display: none; grid-template-columns: repeat(3, 1fr)"></div>`;
			}
			this.grids.push($(template).appendTo(this.icons_container));
			this.make_icons(this.icons_data_by_page, this.grids[i]);
		}
		if (!this.in_folder && this.total_pages > 1) {
			this.add_page_indicators();
			this.setup_arrows();
			this.setup_pagination();
			this.setup_swipe_gesture();
		} else {
			this.grids[0] && this.grids[0].css("display", "grid");
		}
	}
	setup_arrows() {
		if (this.in_modal) {
			const me = this;
			this.wrapper
				.parent()
				.parent()
				.parent()
				.on("shown.bs.modal", function () {
					me.add_arrows();
				});
		} else {
			this.add_arrows(this.wrapper.find(".icons"));
		}
	}
	setup_swipe_gesture() {
		const me = this;
		this.grids.forEach((grid) => {
			$(grid).on("wheel", function (event) {
				if (event.originalEvent) {
					event = event.originalEvent; // for jQuery or wrapped events
				}

				if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) {
					event.preventDefault();
					if (event.deltaX > 0) {
						if (me.current_page != me.total_pages - 1) me.current_page++;
						me.change_to_page(me.current_page);
					} else {
						if (me.current_page != 0) me.current_page--;
						me.change_to_page(me.current_page);
					}
				}
			});
		});
	}
	add_arrows(element) {
		if (!element) element = this.wrapper;
		const me = this;
		let stroke_color = "black";
		let horizontal_movement = 0;
		if (this.in_modal) {
			stroke_color = "white";
			horizontal_movement = "-40px";
		}
		this.left_arrow = $(
			frappe.utils.icon("chevron-left", "lg", "", "", "left-page-arrow", "", stroke_color)
		);
		this.right_arrow = $(
			frappe.utils.icon("chevron-right", "lg", "", "", "right-page-arrow", "", stroke_color)
		);

		this.icons_container.before(this.left_arrow);
		this.icons_container.after(this.right_arrow);

		let wrapper_style = getComputedStyle(element.get(0));
		let total_height = parseInt(wrapper_style.height) - 2 * parseInt(wrapper_style.paddingTop);

		this.left_arrow.css("top", `${total_height / 2}px`);
		this.right_arrow.css("top", `${total_height / 2}px`);
		if (horizontal_movement) {
			this.left_arrow.css("left", horizontal_movement);
			this.right_arrow.css("right", horizontal_movement);
			this.left_arrow.css("position", "absolute");
			this.right_arrow.css("position", "absolute");
		}
		this.left_arrow.on("click", function () {
			if (me.current_page != 0) me.current_page--;
			me.change_to_page(me.current_page);
		});
		this.right_arrow.on("click", function () {
			if (me.current_page != me.total_pages - 1) me.current_page++;
			me.change_to_page(me.current_page);
		});
	}
	add_page_indicators(tempplate) {
		this.page_indicators = [];
		if (this.total_pages > 1) {
			this.pagination_indicator = $(`<div class='page-indicator-container'></div>`).appendTo(
				this.icons_container
			);
			for (let i = 0; i < this.total_pages; i++) {
				this.page_indicators.push(
					$("<div class='page-indicator'></div>").appendTo(this.pagination_indicator)
				);
			}
		}
	}
	setup_pagination() {
		this.current_page = this.old_index = 0;
		this.change_to_page(this.current_page);
	}
	change_to_page(index) {
		this.grids.forEach((g) => $(g).css("display", "none"));
		this.grids[index].css("display", "grid");

		if (this.page_indicators.length) {
			this.page_indicators[this.old_index].removeClass("active-page");
			this.page_indicators[this.current_page].addClass("active-page");
		}
		this.current_page = index;
		this.old_index = index;
	}

	split_data(icons, size) {
		const result = [];

		for (let i = 0; i < icons.length; i += size) {
			result.push(icons.slice(i, i + size));
		}

		return result;
	}
	make_icons(icons_data, grid) {
		icons_data.forEach((icon) => {
			let icon_obj = new DesktopIcon(icon, this.in_folder, this);
			let icon_html = icon_obj.get_desktop_icon_html();
			this.icons.push(icon_obj);
			this.icons_html.push(icon_html);
			this.setup_actions_on_icon(icon_obj);
			grid.append(icon_html);
		});
		this.setup_tooltip();
	}
	setup_actions_on_icon(icon) {
		if (this.edit_mode) {
			icon.edit_mode = true;
		}
		if (this.is_pane) {
			icon.in_pane = true;
		}
	}
	setup_tooltip() {
		$('[data-toggle="tooltip"]').tooltip({
			placement: "bottom",
		});
	}
	remove_label_tooltip() {
		$('[data-toggle="tooltip"]').tooltip("disable");
	}
	setup_reordering(grid) {
		const me = this;
		this.hoverTarget = null;
		this.hoverTimer = null;
		if (!frappe.is_mobile()) {
			this.sortable = new Sortable($(grid).get(0), {
				swapThreshold: 0.09,
				desktop: true,
				animation: 150,
				sort: true, // keep sorting normally
				dragoverBubble: true,
				group: {
					name: this.name || "desktop",
					put: true,
					pull: true,
				},
				onAdd(evt) {
					if (Sortable.get(evt.from).option("group").name == "hidden-icons-grid") {
						let icon_name = $(evt.item).attr("data-id");
						let icon = get_desktop_icon_by_label(icon_name, {}, true);
						icon.index = evt.newIndex;
						icon.hidden = 0;
						frappe.new_desktop_icons.push(icon);
						let hidden_icons = frappe.pages.desktop.desktop_page.hidden_icons;
						let added_icon_index = hidden_icons.findIndex((d) => d.label == icon_name);
						hidden_icons.splice(added_icon_index, 1);
					}
				},
				onStart(evt) {
					frappe.desktop_utils.dragged_item = evt.item;
				},
				setData: function (/** DataTransfer */ dataTransfer, /** HTMLElement*/ dragEl) {
					let title = $(dragEl).find(".icon-title").text();
					let icon = me.icons.find((d) => {
						return d.icon_title === title;
					});
					dataTransfer.setData("text/plain", JSON.stringify(icon.icon_data)); // `dataTransfer` object of HTML5 DragEvent
				},
				onEnd: function (evt) {
					if (frappe.desktop_utils.in_folder_creation) return;
					if (evt.oldIndex !== evt.newIndex) {
						if (evt.to.parentElement == evt.from.parentElement) {
							let reordered_icons = me.sortable.toArray();
							let filters = {
								parent_icon: me.parent_icon?.icon_data.label || "" || null,
							};
							me.reorder_icons(reordered_icons, filters);
							me.parent_icon?.render_folder_thumbnail();
						} else {
							let from = $(evt.from.parentElement);
							let to = $(evt.to.parentElement);
							let title = $(evt.item).find(".icon-title").text();
							let selected_icon = get_desktop_icon_by_label(title);
							if ($(to.get(0).parentElement)) {
								me.reorder_icons(me.sortable.toArray());
								me.reorder_icons(
									frappe.pages[
										"desktop"
									].desktop_page.icon_grid.sortable.toArray()
								);
								selected_icon.idx = evt.newIndex;
								selected_icon.parent_icon = null;
							}
						}
					}
					// save_desktop();
				},
			});
		}
	}
	update_grid(icons) {
		this.wrapper.empty();
		this.init();
	}
	reorder_icons(reordered_icons, filters) {
		reordered_icons.forEach((d, idx) => {
			let icon = get_desktop_icon_by_label(d);
			if (icon) {
				icon.idx = idx;
			}
		});
		frappe.desktop_icons.sort((a, b) => a.idx - b.idx);
	}
	add_to_main_screen(title) {
		let icon = get_desktop_icon_by_label(title);
		icon.parent_icon = null;
	}
}
class DesktopIcon {
	constructor(icon, in_folder, grid_obj) {
		this.icon_data = icon;
		this.icon_title = this.icon_data.label;
		this.icon_subtitle = "";
		this.icon_type = this.icon_data.icon_type;
		this.in_folder = in_folder;
		this.icon_data.in_folder = in_folder;
		this.link_type = this.icon_data.link_type;
		this._edit_mode = false;
		this.in_pane = false;
		if (this.icon_type != "Folder" && !this.icon_data.sidebar) {
			this.icon_route = get_route(this.icon_data);
		}
		if (this.icon_data.child_icons) {
			this.child_icons = this.get_child_icons_data();
		}
		let render = this.validate_icon();
		if (render) {
			this.icon = $(
				frappe.render_template("desktop_icon", {
					icon: this.icon_data,
					in_folder: in_folder,
				})
			);
			this.icon_caption_area = $(this.icon.get(0).children[1]);
			this.parent_icon = this.icon_data.icon;
			this.setup_click();
			this.render_folder_thumbnail();
			this.grid = grid_obj;
			Object.defineProperty(this, "edit_mode", {
				get: function () {
					return this._edit_mode;
				},
				set: function (value) {
					if (value) {
						this.icon.addClass("desktop-edit-mode");
						if (this.in_folder) {
							this.icon.removeClass("desktop-edit-mode");
						}
						this.grid.remove_label_tooltip();
						this.setup_dragging();
						this.setup_edit_menu();
						this.setup_hide_button();
						this.icon.removeAttr("href");
					} else {
						this.icon.addClass("desktop-edit-mode");
						this.setup_click();
					}
					this._edit_mode = value;
				},
			});
			Object.defineProperty(this, "in_pane", {
				get: function () {
					return this._in_pane;
				},
				set: function (value) {
					this._in_pane = value;
					if (value) {
						this.icon.find(".hide-button").html(frappe.utils.icon("plus"));
						this.icon.find(".hide-button").attr("data-mode", "add");
						this.setup_hide_button();
					} else {
						this.icon.find(".hide-button").html(frappe.utils.icon("x"));
						this.icon.find(".hide-button").attr("data-mode", "hide");
					}
				},
			});
			frappe.desktop_icons_objects.push(this);
		}

		// this.child_icons = this.get_desktop_icon(this.icon_title).child_icons;
		// this.child_icons_data = this.get_child_icons_data();
	}
	setup_hide_button() {
		this.icon.find(".hide-button").on("click", function (event) {
			event.preventDefault();
			event.stopImmediatePropagation();
			let desktop_label = event.currentTarget.parentElement.dataset.id;
			let desktop_icon = get_desktop_icon_by_label(desktop_label);
			if (event.target.parentElement.dataset.mode == "hide") {
				desktop_icon.hidden = 1;
			} else {
				desktop_icon.hidden = 0;
			}
			frappe.pages["desktop"].desktop_page.update();
		});
	}
	validate_icon() {
		// validate if my workspaces are empty
		if (this.icon_data.label == "My Workspaces") {
			if (frappe.boot.workspace_sidebar_item["my workspaces"].items.length == 0)
				return false;
		}
		if (this.icon_type == "Folder") {
			if (this.icon_data.child_icons.length == 0) return false;
		}
		return true;
	}
	get_child_icons_data() {
		return this.icon_data.child_icons.sort((a, b) => a.idx - b.idx);
	}
	get_desktop_icon_html() {
		return this.icon;
	}
	setup_edit_menu() {
		const me = frappe.pages["desktop"].desktop_page;
		let icon_data = this.icon_data;
		const icon = this;
		frappe.ui.create_menu({
			parent: this.icon,
			right_click: true,
			menu_items: [
				{
					label: "Edit",
					icon: "edit",
					condition: function () {
						return icon_data.standard != 1;
					},
					onClick: function () {
						frappe.ui.form.make_quick_entry(
							"Desktop Icon",
							function (icon) {
								let old_index = frappe.new_desktop_icons.findIndex(
									(d_icon) => d_icon.label == icon.label
								);
								if (old_index !== -1) {
									frappe.new_desktop_icons.splice(old_index, 1);
								}
								frappe.new_desktop_icons.push(icon);
								frappe.new_icons.push(icon.name);
								frappe.pages["desktop"].desktop_page.update();
							},
							function (dialog) {
								dialog.set_df_property("label", "read_only", 1);
								dialog.fields.forEach((field) => {
									field.default = icon_data[field.fieldname];
								});
								dialog.script_manager.trigger("refresh");
							},
							icon_data,
							null
						);
					},
				},
				{
					label: "Create Folder",
					icon: "folder",
					onClick: function () {
						let folder = me.icon_grid.add_folder();
						add_icons_to_folder(folder.label, [icon_data.label]);
					},
				},
				{
					label: "Add To Folder",
					icon: "folder-open",
					condition: function () {
						return me.folders.length > 0;
					},
					items: me.folders.map((name) => {
						return {
							label: name,
							onClick: function () {
								add_icons_to_folder(this.label, [icon_data.label]);
							},
						};
					}),
				},
			],
		});
	}

	setup_click() {
		const me = this;
		if (this.child_icons?.length && (this.icon_type == "App" || this.icon_type == "Folder")) {
			$(this.icon).on("click", () => {
				let modal = frappe.desktop_utils.create_desktop_modal(me);
				modal.setup(me.icon_title, me.child_icons, 4);
				let $title = modal.modal.find(".modal-title");
				let title = new InlineEditor($title, this.icon_data.label, function (
					old_value,
					new_value
				) {
					let icon = get_desktop_icon_by_label(old_value);
					let folder_icons = frappe.desktop_utils.get_folder_icons(old_value);
					if (icon) {
						icon.label = new_value;
					}
					add_icons_to_folder(new_value, folder_icons);

					frappe.pages["desktop"].desktop_page.update();
				});
				modal.show();
			});
			if (this.icon_type == "App") {
				let content = `${this.child_icons.length} Workspaces`;
				$($(this.icon_caption_area).children()[1]).html(__(content));
			}
		} else {
			if (this.icon_route && this.icon_route.startsWith("http")) {
				this.icon.attr("target", "_blank");
			}
			if (this.icon_route) {
				this.icon.attr("href", this.icon_route);
			} else {
				this.icon.on("click", function (event) {
					frappe.msgprint(
						__(
							"Icon is not correctly configured please check the workspace sidebar to it"
						)
					);
				});
			}
		}
	}

	render_folder_thumbnail() {
		if (this.icon_type == "Folder") {
			if (!this.folder_wrapper) this.folder_wrapper = this.icon.find(".icon-container");
			this.folder_wrapper.html("");
			this.folder_grid = new DesktopIconGrid({
				wrapper: this.folder_wrapper,
				icons_data: this.child_icons,
				row_size: 3,
				page_size: {
					row: 3,
					col: 3,
				},
				in_folder: true,
				in_modal: false,
				no_dragging: true,
			});
			if (this.icon_type == "App") {
				this.folder_wrapper.addClass("folder-icon");
			}
		}
	}

	setup_dragging() {
		if (!frappe.pages["desktop"].desktop_page.edit_mode) return;
		this.icon.on("drag", (event) => {
			const mouse_x = event.clientX;
			const mouse_y = event.clientY;
			if (frappe.desktop_utils.modal) {
				let modal = frappe.desktop_utils.modal.modal
					.find(".modal-content")
					.get(0)
					.getBoundingClientRect();
				if (
					mouse_x > modal.right ||
					mouse_x < modal.left ||
					mouse_y > modal.bottom ||
					mouse_y < modal.top
				) {
					frappe.desktop_utils.close_desktop_modal();
				}
			}
		});
	}
}

class DesktopModal {
	constructor(icon) {
		this.parent_icon_obj = icon;
	}
	setup(icon_title, child_icons_data, grid_row_size) {
		const me = this;
		this.make_modal(icon_title);

		// Check if we're in edit mode
		const is_edit_mode = frappe.pages["desktop"].desktop_page.edit_mode;

		this.child_icon_grid = new DesktopIconGrid({
			wrapper: this.$child_icons_wrapper,
			icons_data: child_icons_data,
			row_size: grid_row_size,
			in_folder: false,
			in_modal: true,
			parent_icon: this.parent_icon_obj,
			edit_mode: is_edit_mode, // Pass edit mode state
		});

		// If in edit mode, setup reordering for the modal icons
		if (is_edit_mode) {
			this.child_icon_grid.grids.forEach((grid) => {
				this.child_icon_grid.setup_reordering(grid);
			});
		}

		this.modal.on("hidden.bs.modal", function () {
			me.modal.remove();
			frappe.desktop_utils.modal = null;
			frappe.desktop_utils.modal_stack = [];
		});
	}
	make_modal(icon_title) {
		if ($(".desktop-modal").length == 0) {
			this.modal = new frappe.get_modal(__(icon_title), "");
			this.modal.find(".modal-header").addClass("desktop-modal-heading");
			this.modal.addClass("desktop-modal");
			this.modal.find(".modal-dialog").attr("id", "desktop-modal");
			this.modal.find(".modal-body").addClass("desktop-modal-body");
			this.$child_icons_wrapper = this.modal.find(".desktop-modal-body");
		} else {
			this.modal.find(".modal-title").text(icon_title);
			$(this.modal.find(".modal-body")).empty();
			if (frappe.desktop_utils.modal_stack.length == 1) {
				this.title_section.find(".icon").remove();
			} else {
				this.add_back_button();
			}
		}
	}
	add_back_button() {
		const me = this;
		this.title_section = this.modal.find(".title-section").find(".modal-title");
		$(this.title_section).prepend(
			frappe.utils.icon("chevron-left", "md", "", "", "", "", "white")
		);
		$(this.title_section)
			.find(".icon")
			.on("click", function () {
				const [prev] = frappe.desktop_utils.modal_stack.splice(-1, 1);
				let icon =
					frappe.desktop_utils.modal_stack[frappe.desktop_utils.modal_stack.length - 1];
				if (icon) {
					me.setup(icon.icon_title, icon.child_icons, 4);
					me.show();
				}
			});
	}
	show() {
		this.modal.modal("show");
	}
	hide() {
		this.modal.modal("hide");
	}
}

class IconsPane {
	constructor() {
		this.wrapper = $($(".desktop-container .icons-container").get(0));
	}
	show() {
		this.wrapper.removeClass("hidden");
		if (this.grid) {
			this.grid.icons_data = frappe.pages.desktop.desktop_page.hidden_icons;
			this.grid.update_grid();
			return;
		}
		this.wrapper.append(
			"<span style='margin-top: 10px; margin-bottom: 20px'>Removed Icons</span>"
		);
		this.grid = new DesktopIconGrid({
			name: "hidden-icons-grid",
			wrapper: this.wrapper,
			icons_data: frappe.pages.desktop.desktop_page.hidden_icons,
			row_size: 6,
			edit_mode: true,
			compact: true,
			is_pane: true,
		});
		this.setup();
	}
	hide() {
		this.wrapper.addClass("hidden");
	}
	setup() {
		this.setup_close_button();
	}
	setup_close_button() {
		const me = this;
		this.wrapper.find(".close-button").on("click", function () {
			me.hide();
		});
	}
}

class InlineEditor {
	constructor(container, initialValue = "", onRename = () => {}) {
		this.container = container;
		this.initialValue = initialValue;
		this.onRename = onRename;

		this.render();
		this.bindEvents();
	}

	render() {
		this.container.html(`
			<div class="title-widget">
				<div class="title-input-label">
					<span>${__(this.initialValue)}</span>
				</div>
				<div class="title-input-wrapper">
					<input class="title-input">
				</div>
			</div>
		`);

		this.input = this.container.find(".title-input");
		this.label = this.container.find(".title-input-label");
	}

	bindEvents() {
		this.container.on("click", () => {
			if (frappe.pages["desktop"].desktop_page.edit_mode) {
				this.label.css("visibility", "hidden");
				this.input.focus().select();
			}
		});

		this.input.on("keydown", (event) => {
			if (event.key === "Enter") {
				const newValue = this.input.val().trim();
				this.input.css("display", "none");
				this.label.css("visibility", "visible");
				this.label.find("span").text(newValue);

				this.onRename(this.initialValue, newValue, this);
			}
		});

		this.input.on("blur", () => {
			this.label.css("visibility", "visible");
		});
	}
}
