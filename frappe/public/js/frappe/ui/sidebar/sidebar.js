import "./sidebar_item";
frappe.ui.Sidebar = class Sidebar {
	constructor() {
		if (!frappe.boot.setup_complete) {
			// no sidebar if setup is not complete
			return;
		}
		this.make_dom();
		// states
		this.edit_mode = false;
		this.sidebar_expanded = false;
		this.all_sidebar_items = frappe.boot.workspace_sidebar_item;
		this.$items = [];
		this.fields_for_dialog = [];
		this.workspace_sidebar_items = [];
		this.new_sidebar_items = [];
		this.$items_container = this.wrapper.find(".sidebar-items");
		this.$sidebar = this.wrapper.find(".body-sidebar");
		this.items = [];
		this.setup_events();
		this.sidebar_module_map = {};
		this.build_sidebar_module_map();
	}

	prepare() {
		try {
			this.sidebar_data =
				frappe.boot.workspace_sidebar_item[this.workspace_title.toLowerCase()];
			this.workspace_sidebar_items = this.sidebar_data.items;
			if (this.edit_mode) {
				this.workspace_sidebar_items = this.new_sidebar_items;
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
			if (app.workspaces.includes(this.workspace_title)) {
				this.header_subtitle = app.app_title;
				this.app_logo_url = app.app_logo_url;
				return;
			}
		}

		const icon = frappe.boot.desktop_icons.find((i) => i.label === this.workspace_title);
		if (icon) {
			this.header_subtitle = icon.parent_icon;
		}

		if (this.workspace_title == "My Workspaces") {
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
		this.workspace_title = workspace_title;
		this.check_for_private_workspace(workspace_title);
		this.prepare();
		this.$sidebar.attr("data-title", this.workspace_title);
		this.sidebar_header = new frappe.ui.SidebarHeader(this);
		this.make_sidebar();
		this.setup_complete = true;
	}
	check_for_private_workspace(workspace_title) {
		if (workspace_title == "private" || workspace_title == "Personal") {
			this.workspace_title = "My Workspaces";
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
			let href = $(this).attr("href")?.split("?")[0];
			const path = decodeURIComponent(window.location.pathname);

			// Match only if path equals href or starts with it followed by "/" or end of string
			const isActive = new RegExp(`^${href}(?:/|$)`).test(path);
			if (href && isActive) {
				match = true;
				if (that.active_item) that.active_item.removeClass("active-sidebar");
				that.active_item = $(this).parent();
				// this exists the each loop
				return false;
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
				if (!w.display_depends_on || frappe.utils.eval(w.display_depends_on)) {
					this.add_item(w);
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

	add_item(item) {
		this.items.push(
			this.make_sidebar_item({
				container: this.$items_container,
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
			direction = "left";
			$('[data-toggle="tooltip"]').tooltip("dispose");
		} else {
			this.wrapper.removeClass("expanded");
			// this.sidebar_expanded = true
			direction = "right";
			$('[data-toggle="tooltip"]').tooltip({
				boundary: "window",
				container: "body",
				trigger: "hover",
			});
		}

		localStorage.setItem("sidebar-expanded", this.sidebar_expanded);
		this.wrapper
			.find(".body-sidebar .collapse-sidebar-link")
			.find("use")
			.attr("href", `#icon-arrow-${direction}-to-line`);
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
			if (frappe.get_route()[0] == "setup-wizard") return;
			if (route[0] == "Workspaces") {
				let workspace;
				if (!route[1]) {
					workspace = "My Workspaces";
				} else {
					workspace = route[1];
				}

				frappe.app.sidebar.setup(workspace);
			} else if (route[0] == "List" || route[0] == "Form") {
				let doctype = route[1];
				let sidebars = this.get_correct_workspace_sidebars(doctype);
				// prevents switching of the sidebar if one item is linked in two sidebars
				if (sidebars.includes(this.workspace_title)) {
					frappe.app.sidebar.setup(this.workspace_title);
					return;
				}
				if (sidebars.length == 0) {
					let module_name = router.meta?.module;
					if (module_name) {
						frappe.app.sidebar.setup(
							this.sidebar_module_map[module_name][0] || module_name
						);
					}
				} else {
					if (
						this.workspace_title &&
						sidebars.includes(this.workspace_title.toLowerCase())
					) {
						frappe.app.sidebar.setup(this.workspace_title.toLowerCase());
					} else {
						frappe.app.sidebar.setup(sidebars[0]);
					}
				}
			} else if (route[0] == "query-report") {
				let doctype = route[1];
				let sidebars = this.get_correct_workspace_sidebars(doctype);
				if (
					this.workspace_title &&
					sidebars.includes(this.workspace_title.toLowerCase())
				) {
					frappe.app.sidebar.setup(this.workspace_title.toLowerCase());
				} else {
					frappe.app.sidebar.setup(sidebars[0]);
				}
			}
		} catch (e) {
			console.log(e);
		}

		this.set_active_workspace_item();
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
			workspace_title = this.get_correct_workspace_sidebars(route);
		}
		let module_name = workspace_title[0];
		if (module_name) {
			frappe.app.sidebar.setup(module_name || this.workspace_title);
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

	toggle_editing_mode() {
		const me = this;
		if (this.edit_mode) {
			this.open();
			this.wrapper.attr("data-mode", "edit");
			this.new_sidebar_items = Array.from(me.workspace_sidebar_items);
			$(this.active_item).removeClass("active-sidebar");
			$(".collapse-sidebar-link").addClass("hidden");
			this.wrapper.find(".edit-mode").removeClass("hidden");
			this.add_new_item_button = this.wrapper.find("[data-name='add-sidebar-item']");
			this.setup_sorting();

			this.setup_editing_controls();
			this.add_new_item_button.on("click", function () {
				me.show_new_dialog();
			});
		} else {
			$(this.active_item).addClass("active-sidebar");
			$(".collapse-sidebar-link").removeClass("hidden");
			this.wrapper.find(".edit-mode").addClass("hidden");
			this.add_new_item_button = this.wrapper.find("[data-name='add-sidebar-item']");
		}
	}
	setup_sorting() {
		const me = this;
		this.sortable = Sortable.create($(".sidebar-items").get(0), {
			handler: ".drag-handle",
			onEnd: function (event) {
				if (me.new_sidebar_items.length == 0) {
					me.new_sidebar_items = Array.from(me.workspace_sidebar_items);
				}
				let old_index = event.oldIndex;
				let new_index = event.newIndex;
				me.new_sidebar_items[old_index];
				let b = me.new_sidebar_items[old_index];
				me.new_sidebar_items[old_index] = me.new_sidebar_items[new_index];
				me.new_sidebar_items[new_index] = b;
			},
		});
		this.setup_sorting_for_nested_container();
	}
	setup_sorting_for_nested_container() {
		const me = this;
		$(".nested-container").each(function (index, el) {
			Sortable.create(el, {
				handle: ".drag-handle",
				onEnd: function (event) {
					let new_index = event.newIndex;
					let old_index = event.oldIndex;
					let item_label = $(event.item).data("id");
					me.new_sidebar_items.forEach((item) => {
						if (item.nested_items.length) {
							let child = item.nested_items.find(
								(child) => child.label === item_label
							);
							if (child) {
								let b = item.nested_items[old_index];
								item.nested_items[old_index] = item.nested_items[new_index];
								item.nested_items[new_index] = b;
							}
						}
					});
				},
			});
		});
	}
	make_dialog(opts) {
		let title = "New Sidebar Item";

		const me = this;
		this.dialog_opts = opts;

		// Create the dialog
		let dialog_fields = [
			{
				fieldname: "label",
				fieldtype: "Data",
				in_list_view: 1,
				label: "Label",
				onchange: function (opts) {
					let label = this.get_value();
					switch (label) {
						case "Home":
							d.set_value("icon", "home");
							d.set_value("link_type", "Workspace");
							d.set_value("link_to", me.workspace_title);
							break;

						case "Reports":
							d.set_value("type", "Section Break");
							d.set_value("link_to", null);
							break;

						case "Dashboard":
							d.set_value("link_type", "Dashboard");
							d.set_value("link_to", me.workspace_title);
							d.set_value("icon", "layout-dashboard");
							break;

						case "Learn":
							d.set_value("icon", "graduation-cap");
							d.set_value("link_type", "URL");
							break;

						case "Settings":
							d.set_value("icon", "settings");
							break;
					}

					if (d.get_value("type") == "Link" && d.get_value("link_type") !== "URL") {
						d.set_value("link_to", label);
					}

					if (
						me.dialog_opts &&
						me.dialog_opts.parent_item &&
						me.dialog_opts.parent_item.label == "Reports"
					) {
						d.set_value("icon", "table");
						d.set_value("link_type", "Report");
					}
				},
			},
			{
				default: "Link",
				fieldname: "type",
				fieldtype: "Select",
				in_list_view: 1,
				label: "Type",
				options: "Link\nSection Break\nSpacer\nSidebar Item Group",
				onchange: function () {
					let type = this.get_value();
					if (type == "Section Break") {
						d.set_value("link_to", null);
					}
				},
			},
			{
				default: "DocType",
				depends_on: "eval: doc.type == 'Link'",
				fieldname: "link_type",
				fieldtype: "Select",
				in_list_view: 1,
				label: "Link Type",
				options: "DocType\nPage\nReport\nWorkspace\nDashboard\nURL",
				onchange: function () {
					d.set_value("link_to", null);
				},
			},
			{
				depends_on: "eval: doc.link_type != \"URL\" && doc.type == 'Link'",
				fieldname: "link_to",
				fieldtype: "Dynamic Link",
				in_list_view: 1,
				label: "Link To",
				options: "link_type",
				onchange: function () {
					if (d.get_value("link_type") == "DocType") {
						let doctype = this.get_value();
						if (doctype) {
							me.setup_filter(d, doctype);
						}
					}
				},
			},
			{
				depends_on: 'eval: doc.link_type == "URL"',
				fieldname: "url",
				fieldtype: "Data",
				label: "URL",
			},
			{
				depends_on:
					'eval: doc.type == "Link" || (doc.indent == 1 && doc.type == "Section Break")',
				fieldname: "icon",
				fieldtype: "Icon",
				options: "Emojis",
				in_list_view: 1,
				label: "Icon",
			},
			{
				fieldtype: "HTML",
				fieldname: "filter_area",
			},
			{
				depends_on: 'eval: doc.type == "Section Break"',
				fieldname: "display_section",
				fieldtype: "Section Break",
				label: "Options",
			},
			{
				default: "0",
				depends_on: 'eval: doc.type == "Section Break"',
				fieldname: "indent",
				fieldtype: "Check",
				label: "Indent",
			},
			{
				depends_on: "eval: doc.indent == 1",
				fieldname: "show_arrow",
				fieldtype: "Check",
				label: "Show Arrow",
			},
			{
				default: "1",
				depends_on: 'eval: doc.type == "Section Break"',
				fieldname: "collapsible",
				fieldtype: "Check",
				label: "Collapsible",
			},
			{
				fieldname: "column_break_krzu",
				fieldtype: "Column Break",
			},
			{
				default: "0",
				depends_on: 'eval: doc.type == "Section Break"',
				fieldname: "keep_closed",
				fieldtype: "Check",
				label: "Keep Closed",
			},
			{
				fieldname: "details_section",
				fieldtype: "Section Break",
				label: "Details",
			},

			{
				fieldtype: "Section Break",
			},
			{
				fieldname: "display_depends_on",
				fieldtype: "Code",
				label: "Display Depends On (JS)",
				options: "JS",
				max_height: "10px",
			},
			{
				fieldtype: "Section Break",
			},
			{
				fieldname: "route_options",
				fieldtype: "Code",
				display_depends_on: "eval: doc.link_type == 'Page'",
				label: "Route Options",
				options: "JSON",
				max_height: "50px",
			},
		];
		if (opts && opts.item) {
			dialog_fields.forEach((f) => {
				if (
					opts.item[f.fieldname] !== undefined &&
					f.fieldtype !== "Section Break" &&
					f.fieldtype !== "Column Break"
				) {
					f.default = opts.item[f.fieldname];
				}
			});
			title = "Edit Sidebar Item";
		}
		let d;
		this.dialog = d = new frappe.ui.Dialog({
			title: title,
			fields: dialog_fields,
			primary_action_label: "Save",
			size: "small",
			primary_action(values) {
				if (me.filter_group) {
					me.filter_group.get_filters();
				}

				if (me.new_sidebar_items.length === 0) {
					me.new_sidebar_items = Array.from(me.workspace_sidebar_items);
				}
				if (opts && opts.nested) {
					values.child = 1;
					console.log("Add it as a nested item");
					console.log(opts.parent_item);
					let index = me.new_sidebar_items.findIndex((f) => {
						return f.label == opts.parent_item.label;
					});

					if (!me.new_sidebar_items[index].nested_items) {
						me.new_sidebar_items[index].nested_items = [];
					}
					me.new_sidebar_items[index].nested_items.push(values);
				} else if (opts && opts.item) {
					if (opts.item.child) {
						let parent_icon = me.find_parent(me.new_sidebar_items, opts.item);
						if (parent_icon) {
							let index = parent_icon.nested_items.indexOf(opts.item);
							let parent_icon_index = me.new_sidebar_items.indexOf(parent_icon);
							me.new_sidebar_items[parent_icon_index].nested_items[index] = values;
						}
					} else {
						let index = me.new_sidebar_items.indexOf(opts.item);

						me.new_sidebar_items[index] = {
							...me.new_sidebar_items[index],
							...values,
						};
					}
				} else {
					me.new_sidebar_items.push(values);
				}
				me.create_sidebar(me.new_sidebar_items);
				me.setup_sorting_for_nested_container();
				d.hide();
			},
		});

		return d;
	}
	setup_filter(d, doctype) {
		if (this.filter_group) {
			this.filter_group.wrapper.empty();
			delete this.filter_group;
		}

		// let $loading = this.dialog.get_field("filter_area_loading").$wrapper;
		// $(`<span class="text-muted">${__("Loading Filters...")}</span>`).appendTo($loading);

		this.filters = [];

		this.generate_filter_from_json && this.generate_filter_from_json();

		this.filter_group = new frappe.ui.FilterGroup({
			parent: d.get_field("filter_area").$wrapper,
			doctype: doctype,
			on_change: () => {},
		});

		frappe.model.with_doctype(doctype, () => {
			this.filter_group.add_filters_to_filter_group(this.filters);
		});
	}
	hide_field(fieldname) {
		this.dialog.set_df_property(fieldname, "hidden", true);
	}

	show_field(fieldname) {
		this.dialog.set_df_property(fieldname, "hidden", false);
	}
	setup_editing_controls() {
		const me = this;
		this.save_sidebar_button = this.wrapper.find(".save-sidebar");
		this.discard_button = this.wrapper.find(".discard-button");
		this.save_sidebar_button.on("click", async function (event) {
			frappe.show_alert({
				message: __("Saving Sidebar"),
				indicator: "success",
			});

			await frappe.call({
				type: "POST",
				method: "frappe.desk.doctype.workspace_sidebar.workspace_sidebar.add_sidebar_items",
				args: {
					sidebar_title:
						me.workspace_title || frappe.app.sidebar.sidebar_header.workspace_title,
					sidebar_items: me.new_sidebar_items,
				},
				callback: function (r) {
					frappe.boot.workspace_sidebar_item[me.workspace_title.toLowerCase()] = [
						...me.new_sidebar_items,
					];
					frappe.ui.toolbar.clear_cache();
					me.edit_mode = false;
					me.toggle_editing_mode();
					me.make_sidebar(me);
				},
			});
		});

		this.discard_button.on("click", function () {
			me.edit_mode = false;
			me.toggle_editing_mode();
			me.make_sidebar(me);
		});
	}

	find_parent(sidebar_items, item) {
		for (const f of sidebar_items) {
			if (f.nested_items && f.nested_items.includes(item)) {
				return f;
			}
		}
	}

	delete_item(item) {
		let index;
		if (item.child) {
			let parent_icon = this.find_parent(this.new_sidebar_items, item);
			index = parent_icon.nested_items.indexOf(item);
			parent_icon.nested_items.splice(index, 1);
		} else {
			index = this.new_sidebar_items.indexOf(item);
			this.new_sidebar_items.splice(index, 1);
		}
		this.create_sidebar(this.new_sidebar_items);
	}

	add_below(item) {
		let index = this.workspace_sidebar_items.indexOf(item);
		this.show_new_dialog(index);
		this.create_sidebar(this.new_sidebar_items);
	}

	duplicate_item(item) {
		let index = this.workspace_sidebar_items.indexOf(item);
		this.new_sidebar_items.splice(index, 0, item);
		this.create_sidebar(this.new_sidebar_items);
	}

	edit_item(item) {
		let d = this.make_dialog({
			item: item,
		});
		d.show();
	}

	show_new_dialog(opts) {
		let d = this.make_dialog(opts);
		d.show();
	}
	make_fields_for_grids(fields) {
		let doc_fields = Array.from(fields);
		doc_fields = doc_fields
			.filter((f) => f.fieldtype !== "Section Break" && f.fieldtype !== "Column Break")
			.map((f, i) => ({
				...f,
				in_list_view: i < 5 ? 1 : 0,
			}));
		let link_to_field = doc_fields.find((f) => f.label == "Link To");
		link_to_field.field_in_dialog = true;
		return doc_fields;
	}
};
