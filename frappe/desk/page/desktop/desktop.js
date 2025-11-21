frappe.desktop_utils = {};
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
	} else {
		if (desktop_icon.link_type == "Workspace") {
			item = {
				type: desktop_icon.link_type,
				link: frappe.router.slug(desktop_icon.link_to),
			};
		} else if (desktop_icon.link_type == "DocType" || desktop_icon.link_type == "list") {
			item = {
				type: desktop_icon.link_type,
				name: desktop_icon.link_to,
			};
		}
		route = frappe.utils.generate_route(item);
	}

	return route;
}

function get_desktop_icon_by_label(title, filters) {
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

function get_desktop_icon_by_idx(idx, parent_icon) {
	return frappe.boot.desktop_icons.find((f) => f.idx == idx && f.parent_icon == parent_icon);
}

function save_desktop() {
	// saving in localStorage;
	localStorage.setItem(
		`${frappe.session.user}:desktop`,
		JSON.stringify(frappe.boot.desktop_icons)
	);
	frappe.toast("Desktop Saved");
	frappe.pages["desktop"].desktop_page.update();
}

function reset_to_default() {
	localStorage.setItem(`${frappe.session.user}:desktop`, null);
}

frappe.pages["desktop"].on_page_show = function () {
	frappe.pages["desktop"].desktop_page.setup();
};

function toggle_icons(icons) {
	icons.forEach((i) => {
		$(i).parent().parent().show();
	});
}

class DesktopPage {
	constructor(page) {
		this.page = page;
		this.prepare();
		this.make(page);
	}
	update() {
		this.prepare();
		this.make();
		this.setup();
	}

	prepare() {
		this.apps_icons = [];

		const icon_map = {};
		const all_icons = (
			JSON.parse(localStorage.getItem(`${frappe.session.user}:desktop`)) ||
			frappe.boot.desktop_icons
		).filter((icon) => {
			if (icon.hidden != 1) {
				icon.child_icons = [];
				icon_map[icon.label] = icon;
				return true;
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

	make() {
		this.page.page_head.hide();
		$(this.page.body).empty();
		$(frappe.render_template("desktop")).appendTo(this.page.body);
		this.wrapper = this.page.body.find(".desktop-container");
		this.icon_grid = new DesktopIconGrid({
			wrapper: this.wrapper,
			icons_data: this.apps_icons,
			page_size: {
				row: 6,
				col: 3,
			},
		});
	}

	setup() {
		this.setup_avatar();
		this.setup_navbar();
		this.setup_awesomebar();
		this.handke_route_change();
	}
	setup_avatar() {
		$(".desktop-avatar").html(frappe.avatar(frappe.session.user, "avatar-medium"));
		$(".desktop-avatar").data("menu", "user-menu");
		let menu_items = [
			{
				icon: "edit",
				label: "Edit Profile",
				url: `/update-profile/${frappe.session.user}`,
			},
			{
				icon: "lock",
				label: "Reset Password",
				url: "/update-password",
			},
			{
				icon: "rotate-ccw",
				label: "Reset to Default",
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
		frappe.ui.create_menu($(".desktop-avatar"), menu_items, null, true);
	}
	setup_navbar() {
		$(".sticky-top > .navbar").hide();
	}

	setup_awesomebar() {
		if (frappe.boot.desk_settings.search_bar) {
			let awesome_bar = new frappe.search.AwesomeBar();
			awesome_bar.setup(".desktop-search-wrapper #navbar-search");
		}
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+g",
			action: function (e) {
				$(".desktop-search-wrapper #navbar-search").focus();
				e.preventDefault();
				return false;
			},
			description: __("Open Awesomebar"),
		});
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+k",
			action: function (e) {
				$(".desktop-search-wrapper #navbar-search").focus();
				e.preventDefault();
				return false;
			},
			description: __("Open Awesomebar"),
		});
	}
	handke_route_change() {
		const me = this;
		frappe.router.on("change", function () {
			if (frappe.get_route()[0] == "desktop" || frappe.get_route()[0] == "")
				me.setup_navbar();
			else {
				$(".navbar").show();
				frappe.desktop_utils.close_desktop_modal();
			}
		});
	}

	// setup_icon_search() {
	// 	let all_icons = $(".icon-title");
	// 	let icons_to_show = [];
	// 	$(".desktop-container .icons").append(
	// 		"<div class='no-apps-message hidden'> No apps found </div>"
	// 	);
	// 	$(".desktop-search-wrapper > #navbar-search").on("input", function (e) {
	// 		let search_query = $(e.target).val().toLowerCase();
	// 		console.log(search_query);
	// 		icons_to_show = [];
	// 		all_icons.each(function (index, element) {
	// 			$(element).parent().parent().hide();
	// 			let label = $(element).text().toLowerCase();
	// 			if (label.includes(search_query)) {
	// 				icons_to_show.push(element);
	// 			}
	// 		});

	// 		if (icons_to_show.length == 0) {
	// 			$(".desktop-container .icons").find(".no-apps-message").removeClass("hidden");
	// 		} else {
	// 			$(".desktop-container .icons").find(".no-apps-message").addClass("hidden");
	// 		}
	// 		toggle_icons(icons_to_show);
	// 	});
	// }
}

class DesktopIconGrid {
	constructor(opts) {
		$.extend(this, opts);
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
	}

	prepare() {
		this.icons_data = this.icons_data.sort((a, b) => a.idx - b.idx);
		this.total_pages = 1;
		this.icons_data_by_page =
			this.icons_data || this.split_data(this.icons_data, this.page_size.total());
	}
	make() {
		const me = this;
		this.icons_container = $(`<div class="icons-container"></div>`).appendTo(this.wrapper);
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
			if (!this.no_dragging) {
				this.setup_reordering(this.grids[i]);
			}
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
			let icon_obj = new DesktopIcon(icon, this.in_folder);
			let icon_html = icon_obj.get_desktop_icon_html();
			this.icons.push(icon_obj);
			this.icons_html.push(icon_html);
			grid.append(icon_html);
		});
	}

	setup_reordering(grid) {
		const me = this;
		this.hoverTarget = null;
		this.hoverTimer = null;
		this.sortable = new Sortable($(grid).get(0), {
			swapThreshold: 0.09,
			animation: 150,
			sort: true, // keep sorting normally
			dragoverBubble: true,
			group: {
				name: "desktop",
				put: true,
				pull: true,
			},
			setData: function (/** DataTransfer */ dataTransfer, /** HTMLElement*/ dragEl) {
				let title = $(dragEl).find(".icon-title").text();
				let icon = me.icons.find((d) => {
					return d.icon_title === title;
				});
				dataTransfer.setData("text/plain", JSON.stringify(icon.icon_data)); // `dataTransfer` object of HTML5 DragEvent
			},
			onEnd: function (evt) {
				if (evt.oldIndex !== evt.newIndex) {
					if (evt.to.parentElement == evt.from.parentElement) {
						let reordered_icons = me.sortable.toArray();
						let filters = {
							parent_icon: me.parent_icon?.icon_data.label || null,
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
								frappe.pages["desktop"].desktop_page.icon_grid.sortable.toArray()
							);
							selected_icon.idx = evt.newIndex;
							selected_icon.parent_icon = null;
						}
					}
				} else {
					frappe.toast("Nothing changed");
				}
				save_desktop();
			},
		});
	}
	reorder_icons(reordered_icons, filters) {
		reordered_icons.forEach((d, idx) => {
			let icon = get_desktop_icon_by_label(d, filters);
			if (icon) {
				icon.idx = idx;
			}
		});
	}
	add_to_main_screen(title) {
		let icon = get_desktop_icon_by_label(title);
		icon.parent_icon = null;
	}
}
class DesktopIcon {
	constructor(icon, in_folder) {
		this.icon_data = icon;
		this.icon_title = this.icon_data.label;
		this.icon_subtitle = "";
		this.icon_type = this.icon_data.icon_type;
		this.in_folder = in_folder;
		this.link_type = this.icon_data.link_type;
		if (this.icon_type != "Folder" && !this.icon_data.sidebar) {
			this.icon_route = get_route(this.icon_data);
		}
		this.child_icons = this.get_child_icons_data();
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
			this.setup_dragging();
		}

		// this.child_icons = this.get_desktop_icon(this.icon_title).child_icons;
		// this.child_icons_data = this.get_child_icons_data();
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
		// validate if folder has no child
	}
	get_child_icons_data() {
		return this.icon_data.child_icons.sort((a, b) => a.idx - b.idx);
	}
	get_desktop_icon_html() {
		return this.icon;
	}
	setup_click() {
		const me = this;
		if (this.child_icons.length && (this.icon_type == "App" || this.icon_type == "Folder")) {
			$(this.icon).on("click", () => {
				let modal = frappe.desktop_utils.create_desktop_modal(me);
				modal.setup(me.icon_title, me.child_icons, 4);
				modal.show();
			});
			if (this.icon_type == "App") {
				$($(this.icon_caption_area).children()[1]).html(
					`${this.child_icons.length} Workspaces`
				);
			}
		} else {
			this.icon.attr("href", this.icon_route);
		}
		if (this.icon_data.sidebar) {
			const me = this;
			this.icon.on("click", function () {
				if (me.icon_data.sidebar == "My Workspaces") {
					let sidebar_name = me.icon_data.sidebar.toLowerCase();
					if (frappe.boot.workspace_sidebar_item[sidebar_name].items.length == 0) {
						frappe.toast("No Private Workspaces for user");
					} else {
						let workspace_name =
							frappe.boot.workspace_sidebar_item[sidebar_name].items[0]["link_to"];
						frappe.set_route("Workspaces", "private", workspace_name);
					}
				}
			});
		}
	}

	render_folder_thumbnail() {
		let condition =
			frappe.boot.show_app_icons_as_folder &&
			this.icon_type == "App" &&
			this.child_icons.length > 0;
		if (this.icon_type == "Folder" || condition) {
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
		this.child_icon_grid = new DesktopIconGrid({
			wrapper: this.$child_icons_wrapper,
			icons_data: child_icons_data,
			row_size: grid_row_size,
			in_folder: false,
			in_modal: true,
			parent_icon: this.parent_icon_obj,
		});

		this.modal.on("hidden.bs.modal", function () {
			me.modal.remove();
			frappe.desktop_utils.modal = null;
			frappe.desktop_utils.modal_stack = [];
		});
	}
	make_modal(icon_title) {
		if ($(".desktop-modal").length == 0) {
			this.modal = new frappe.get_modal(icon_title, "");
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
