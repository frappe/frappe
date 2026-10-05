// The Desktop Icon grid: the /app/desktop page when Desktop Settings -> Desktop Page is
// `Desktop Icons` (folders, drag-to-reorder, edit mode). The default `Apps` mode uses the
// hook-driven grid in desktop.js instead.
//
// Loaded lazily by frappe/desk/page/desktop/desktop.js, because Page.load_assets reads exactly
// one `<page_name>.js` per page, so a second file in that folder would never be served. Keeping
// it out of desk.bundle also keeps about 1200 lines off every desk page load.
//
// The page extends the Apps screen, so both modes share one header, search, avatar menu and
// stylesheet. Only the grid differs: this one draws the Desktop Icon rows, folders included.
import "./frappe/ui/desktop_icons_item.html";

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
function get_route(desktop_icon) {
	let route;
	if (!desktop_icon) return;
	if (desktop_icon.link_type == "External" && desktop_icon.link) {
		route = window.location.origin + desktop_icon.link;
		if (desktop_icon.link.startsWith("http") || desktop_icon.link.startsWith("https")) {
			route = desktop_icon.link;
		}
	} else if (desktop_icon.link_type == "Workspace Sidebar") {
		// The same landing the Apps screen and the dock open, in the `/desk/<shell>/...` grammar.
		let sidebar = frappe.utils.sidebar_for_module(desktop_icon.module || desktop_icon.label);
		if (sidebar) route = frappe.app.sidebar?.module_landing_route(sidebar.name);
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

class DesktopIconsPage extends frappe.ui.DesktopPage {
	constructor(page) {
		super(page);
		this.edit_mode = false;
		this.add_menu_item({
			icon: "rotate-ccw",
			label: "Reset Desktop Layout",
			onclick: function () {
				reset_to_default();
				window.location.reload();
			},
		});
		// Registered once here, alongside the Apps page's own listener for the navbar.
		frappe.router.on("change", () => {
			if (frappe.get_route()[0] == "desktop" || frappe.get_route()[0] == "") return;
			frappe.desktop_utils.close_desktop_modal();
			// stop edit mode if route changes and cleanup
			this.edit_mode = false;
			$(".desktop-icon").removeClass("edit-mode");
			$(".desktop-wrapper").removeAttr("data-mode");
			$(".desktop-edit").remove();
		});
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
				me.make();
				frappe.new_icons = [];
			},
		});
	}
	render_app_icons() {
		if (!this.data) {
			this.data = JSON.parse($("#desktop-layout").text());
		}
		this.sync_layout();
		this.prepare();
		this.icon_grid = new DesktopIconGrid({
			wrapper: this.wrapper,
			icons_data: this.apps_icons,
		});
		this.setup_context_menu();
		if (this.edit_mode) {
			this.start_editing_layout();
		}
	}

	setup_context_menu() {
		const me = this;
		new frappe.ui.ContextMenu({
			target: this.wrapper,
			options: [
				{
					label: __("Edit Layout"),
					icon: "pencil",
					condition: function () {
						return !me.edit_mode;
					},
					onclick: function () {
						frappe.new_desktop_icons = JSON.parse(
							JSON.stringify(frappe.desktop_icons)
						);
						me.start_editing_layout();
					},
				},
				{
					label: __("Reset Layout"),
					icon: "rotate-ccw",
					onclick: function () {
						reset_to_default();
						me.update();
					},
				},
			],
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
				desktop_grid.setup_reordering(desktop_grid.grid);
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
		  <div>Workspace</div>
		 </div>`;
		grid.append(this.add_new_icon);
		$(".add-new-icon").on("click", function () {
			let d = new frappe.ui.Dialog({
				title: "New Workspace",
				fields: [
					{
						label: "Label",
						fieldname: "label",
						fieldtype: "Data",
					},
					{
						label: "Public",
						fieldname: "public",
						fieldtype: "Check",
					},
				],
				primary_action_label: "Create",
				primary_action: function (values) {
					let icon = frappe.model.get_new_doc("Desktop Icon");
					icon.workspace = {
						label: values.label,
						public: values.public,
					};
					icon.link_type = "Workspace Sidebar";
					icon.label = values.label;
					frappe.new_desktop_icons.push(icon);
					frappe.new_icons.push(icon);
					frappe.pages["desktop"].desktop_page.update();
					d.hide();
				},
			});
			d.show();
			// frappe.ui.form.make_quick_entry(
			// 	"Desktop Icon",
			// 	function (icon) {
			// 		frappe.new_desktop_icons.push(icon);
			// 		frappe.new_icons.push(icon);
			// 		frappe.pages["desktop"].desktop_page.update();
			// 	},
			// 	"",
			// 	"",
			// 	null,
			// 	true,
			// 	true
			// );
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
	delete_new_icons() {
		frappe.new_icons = [];
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
		this.prepare();
		this.make();
		frappe.desktop_grids.push(this);
	}
	add_folder() {
		DesktopIconGrid.folder_count++;
		let icon = frappe.model.get_new_doc("Desktop Icon");
		icon.icon_type = "Folder";
		icon.label = __("Untitled {0}", [DesktopIconGrid.folder_count]);
		icon.idx = 100000;
		frappe.new_desktop_icons.push(icon);
		frappe.new_icons.push(icon);
		return icon;
	}
	prepare() {
		this.icons_data.sort((a, b) => {
			if (a.idx === b.idx) {
				return a.label.localeCompare(b.label); // sort by label if idx is the same
			}
			return a.idx - b.idx; // sort by idx
		});
	}
	make() {
		this.icons_container = $(`<div class="icons-container"></div>`).appendTo(this.wrapper);
		if (this.compact) {
			this.icons_container.css("margin-top", "0px");
		}
		this.grid = $(`<div class="icons"></div>`).appendTo(this.icons_container);
		const columns = frappe.is_mobile() ? 3 : this.row_size;
		if (columns) {
			this.grid.css("grid-template-columns", `repeat(${columns}, 1fr)`);
		}
		this.make_icons(this.icons_data, this.grid);
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
	}
	setup_actions_on_icon(icon) {
		if (this.edit_mode) {
			icon.edit_mode = true;
		}
		if (this.is_pane) {
			icon.in_pane = true;
		}
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
					let label = $(dragEl).attr("data-id");
					let icon = me.icons.find((d) => {
						return d.icon_title === label;
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
							let label = $(evt.item).attr("data-id");
							let selected_icon = get_desktop_icon_by_label(label);
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
				frappe.render_template("desktop_icons_item", {
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
		new frappe.ui.ContextMenu({
			target: this.icon,
			options: [
				{
					label: __("Edit"),
					icon: "pencil",
					condition: function () {
						return icon_data.standard != 1;
					},
					onclick: function () {
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
					label: __("Create Folder"),
					icon: "folder",
					onclick: function () {
						let folder = me.icon_grid.add_folder();
						add_icons_to_folder(folder.label, [icon_data.label]);
					},
				},
				{
					label: __("Add To Folder"),
					icon: "folder-open",
					condition: function () {
						return me.folders.length > 0;
					},
					// Read at hover, so the list is the folders that exist when the menu is
					// opened rather than the ones that existed when the icon was drawn.
					// The folder each row adds to is the one it closes over: a row handler is
					// called with no receiver, so the `this.label` this used to read was never
					// the row.
					submenu: () =>
						me.folders.map((name) => ({
							label: name,
							onclick: () => add_icons_to_folder(name, [icon_data.label]),
						})),
				},
			],
		});
	}

	setup_click() {
		const me = this;
		if (this.child_icons?.length && (this.icon_type == "App" || this.icon_type == "Folder")) {
			$(this.icon).on("click", (event) => {
				event.preventDefault();
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
				in_folder: true,
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
			parent_icon: this.parent_icon_obj,
			edit_mode: is_edit_mode, // Pass edit mode state
		});

		// If in edit mode, setup reordering for the modal icons
		if (is_edit_mode) {
			this.child_icon_grid.setup_reordering(this.child_icon_grid.grid);
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
			// the modal sits outside the page body, so it needs the page's title tooltip of its own
			frappe.ui.Tooltip.delegate(this.modal.get(0), ".icon-title", {
				only_on_overflow: true,
				side: "bottom",
				delay: 150,
			});
			this.modal.find(".desktop-modal-heading").on("click", (e) => {
				if (!$(e.target).closest(".modal-title").length) {
					this.hide();
				}
			});
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
		this.wrapper.append(`<span class="removed-icons-heading">${__("Removed Icons")}</span>`);
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
					<span>${frappe.utils.escape_html(__(this.initialValue))}</span>
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

frappe.ui.DesktopIconsPage = DesktopIconsPage;
