export class SidebarEditor {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.edit_mode = false;
		this.setup();
	}
	setup() {
		this.handle_route_change();
	}
	handle_route_change() {
		const me = this;
		frappe.router.on("change", function () {
			if (frappe.get_prev_route().length == 0) return;
			if (frappe.get_prev_route().length !== frappe.get_route().length && me.edit_mode) {
				me.stop();
			}
		});
	}
	toggle() {
		if (this.edit_mode) {
			this.stop();
		} else {
			this.start();
		}
	}

	start() {
		const me = this;
		this.edit_mode = true;
		this.sidebar.open();

		this.sidebar.wrapper.attr("data-mode", "edit");
		this.new_sidebar_items = Array.from(me.sidebar.workspace_sidebar_items);
		$(this.active_item).removeClass("active-sidebar");
		this.sidebar.wrapper.find(".edit-mode").toggleClass("hidden");
		this.add_new_item_button = this.sidebar.wrapper.find("[data-name='add-sidebar-item']");
		this.setup_sorting();

		this.setup_editing_controls();
		this.add_new_item_button.on("click", function () {
			me.show_new_dialog();
		});
	}
	stop() {
		this.edit_mode = false;
		$(this.active_item).addClass("active-sidebar");
		this.sidebar.wrapper.find(".edit-mode").toggleClass("hidden");
		this.sidebar.wrapper.removeAttr("data-mode");
		this.add_new_item_button = this.sidebar.wrapper.find("[data-name='add-sidebar-item']");
	}

	setup_editing_controls() {
		const me = this;
		this.save_sidebar_button = this.sidebar.wrapper.find(".save-sidebar");
		this.discard_button = this.sidebar.wrapper.find(".discard-button");
		this.save_sidebar_button.on("click", async function (event) {
			frappe.show_alert({
				message: __("Saving Sidebar"),
				indicator: "success",
			});
			me.prepare_data();
			await frappe.call({
				type: "POST",
				method: "frappe.desk.doctype.workspace_sidebar.workspace_sidebar.add_sidebar_items",
				args: {
					sidebar_title: me.workspace_title || me.sidebar.sidebar_title,
					sidebar_items: me.new_sidebar_items,
				},
				callback: function (r) {
					frappe.boot.workspace_sidebar_item[r.message.name.toLowerCase()] = [
						...me.new_sidebar_items,
					];
					frappe.ui.toolbar.clear_cache();
					me.stop();
					me.sidebar.make_sidebar();
				},
			});
		});

		this.discard_button.on("click", function () {
			me.toggle();
			me.sidebar.make_sidebar();
		});
	}
	prepare_data() {
		this.new_sidebar_items.forEach((item) => {
			if (!item.nested_items) return;
			item.nested_items.forEach((nested_item) => {
				if (nested_item.parent) {
					delete nested_item.parent;
				}
			});
		});
	}
	setup_sorting() {
		const me = this;
		this.fetch;
		this.sortable = Sortable.create($(".sidebar-items").get(0), {
			handler: ".drag-handle",
			group: "sidebar-item",
			onAdd: function (event) {
				let old_index = event.oldIndex;
				let section_name = $(event.from).parent().attr("item-name");
				let item_data = me.get_item_data(section_name).nested_items[old_index];
				me.get_item_data(section_name).nested_items.splice(old_index, 1);
				item_data.child = 0;
				me.new_sidebar_items.splice(event.newIndex, 0, item_data);
			},
			onMove: function (evt, originalEvent) {
				me.close_section = false;
				let item_name = $(evt.related).attr("item-name");
				let item_data = me.get_item_data(item_name);
				if (item_data && item_data.type == "Section Break") {
					let item_obj = me.get_item_obj(item_data);
					if (me.current_section_break) me.current_section_break.close();
					me.current_section_break = item_obj;
					if (item_obj && item_obj.collapsed) {
						item_obj.open();
						return 1;
					}
					if (me.current_section_break) {
						let nested_container = me.current_section_break.wrapper
							.find(".nested-container")
							.first()
							.get(0)
							.getBoundingClientRect();
						if (
							nested_container.top > originalEvent.clientY ||
							originalEvent.clientY < nested_container.bottom
						) {
							me.current_section_break.close();
							me.current_section_break = null;
						}
					}
				}
			},
			onStart: function () {
				me.sorting = true;
			},
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
	get_item_data(item_name) {
		let item_data;
		if (item_name) {
			this.new_sidebar_items.forEach((item) => {
				if (item.label == item_name) {
					item_data = item;
				}
				if (item.nested_items && item.nested_items.length > 0) {
					item.nested_items.forEach((nested_item) => {
						if (nested_item.label == item_name) {
							item_data = nested_item;
						}
					});
				}
			});

			return item_data;
		}
	}
	get_item_obj(item_data) {
		return frappe.app.sidebar.items.find((item) => {
			return item.item == item_data;
		});
	}
	setup_sorting_for_nested_container() {
		const me = this;
		$(".nested-container").each(function (index, el) {
			Sortable.create(el, {
				handle: ".drag-handle",
				group: "sidebar-item",
				onAdd: function (event) {
					let old_index = event.oldIndex;
					let item_data = me.new_sidebar_items[old_index];
					me.new_sidebar_items.splice(old_index, 1);
					item_data.child = 1;
					let section_name = $(event.to).parent().attr("item-name");
					me.get_item_data(section_name).nested_items.splice(
						event.newIndex,
						0,
						item_data
					);
				},
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
					let index = me.new_sidebar_items.findIndex((f) => {
						return f.label == opts.parent_item.label;
					});

					if (!me.new_sidebar_items[index].nested_items) {
						me.new_sidebar_items[index].nested_items = [];
					}
					me.new_sidebar_items[index].nested_items.push(values);
				} else if (opts && opts.item) {
					if (opts.item.child) {
						let parent_item = me.find_parent(me.new_sidebar_items, opts.item);
						if (parent_item) {
							let index = parent_item.nested_items.indexOf(opts.item);
							let parent_item_index = me.new_sidebar_items.indexOf(parent_item);
							me.new_sidebar_items[parent_item_index].nested_items[index] = values;
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
				me.sidebar.create_sidebar(me.new_sidebar_items);
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

	show_new_dialog(opts) {
		let d = this.make_dialog(opts);
		d.show();
	}

	hide_field(fieldname) {
		this.dialog.set_df_property(fieldname, "hidden", true);
	}

	show_field(fieldname) {
		this.dialog.set_df_property(fieldname, "hidden", false);
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
			let parent_item = this.find_parent(this.new_sidebar_items, item);
			if (parent_item) {
				index = parent_item.nested_items.indexOf(item);
				parent_item.nested_items.splice(index, 1);
			}
		} else {
			index = this.new_sidebar_items.indexOf(item);
			this.new_sidebar_items.splice(index, 1);
		}
		this.sidebar.make_sidebar();
	}

	add_below(item) {
		let index = this.new_sidebar_items.indexOf(item);
		this.show_new_dialog(index);
		this.sidebar.make_sidebar();
	}

	duplicate_item(item) {
		let index = this.new_sidebar_items.indexOf(item);
		this.new_sidebar_items.splice(index, 0, item);
		this.sidebar.make_sidebar();
	}

	edit_item(item) {
		let d = this.make_dialog({
			item: item,
		});
		d.show();
		this.sidebar.make_sidebar();
	}

	perform_action(action_name, item_data) {
		let index = this.new_sidebar_items.indexOf(item_data);
		let parent_item = this.find_parent(this.new_sidebar_items, item_data);
		switch (action_name) {
			case "edit":
				this.edit_item(item_data);
				break;
			case "delete":
				this.delete_item(item_data);
				break;
			case "add_item_below":
				this.edit_item(item_data);
				break;
			case "duplicate":
				this.duplicate_item(item_data);
				break;
			default:
				break;
		}
		this.sidebar.make_sidebar();
	}
}
