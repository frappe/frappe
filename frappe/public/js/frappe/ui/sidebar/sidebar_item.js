frappe.provide("frappe.ui.sidebar_item");
frappe.ui.sidebar_item.TypeLink = class SidebarItem {
	constructor(opts) {
		this.item = opts.item;
		this.container = opts.container;
		this.nested_items = opts.item.nested_items || [];
		this.workspace_title = $(".body-sidebar").attr("data-title").toLowerCase();
		this.prepare(opts);
		this.make();
	}
	get_path() {
		let path;
		if (this.item.type === "Link") {
			if (this.item.link_type === "Report") {
				let args = {
					type: this.item.link_type,
					name: this.item.link_to,
				};

				if (this.item.report || !frappe.app.sidebar.edit_mode) {
					args.is_query_report =
						this.item.report.report_type === "Query Report" ||
						this.item.report.report_type == "Script Report";
					args.report_ref_doctype = this.item.report.ref_doctype;
				}

				path = frappe.utils.generate_route(args);
			} else if (this.item.link_type == "Workspace") {
				let workspaces = frappe.workspaces[frappe.router.slug(this.item.link_to)];
				if (workspaces.public) {
					path = "/desk/" + frappe.router.slug(this.item.link_to);
				} else {
					path = "/desk/private/" + frappe.router.slug(workspaces.title);
				}

				if (this.item.route) {
					path = this.item.route;
				}
			} else if (this.item.link_type === "URL") {
				path = this.item.url;
			} else if (this.item.link_type == "Page" && this.item.route_options) {
				path = frappe.utils.generate_route({
					type: this.item.link_type,
					name: this.item.link_to,
					route_options: JSON.parse(this.item.route_options),
				});
			} else {
				path = frappe.utils.generate_route({
					type: this.item.link_type,
					name: this.item.link_to,
				});
			}
		}
		return path;
	}
	prepare() {}
	make() {
		this.path = this.get_path();
		if (!this.item.icon && !(this.item.child && this.item.parent.indent)) {
			this.item.icon = "list-alt";
		}
		this.wrapper = $(
			frappe.render_template("sidebar_item", {
				item: this.item,
				path: this.path,
				edit_mode: frappe.app.sidebar.edit_mode,
			})
		);
		$(this.container).append(this.wrapper);
		this.setup_editing_controls();
	}
	setup_editing_controls() {
		this.menu_items = this.get_menu_items();
		this.$edit_menu = this.wrapper.find(".edit-menu");
		this.$sidebar_container = this.$edit_menu.parent();
		frappe.ui.create_menu(this.$edit_menu, this.menu_items);
	}
	get_menu_items() {
		let me = this;
		let menu_items = [
			{
				label: "Edit Item",
				icon: "pen",
				onClick: () => {
					frappe.app.sidebar.edit_item(me.item);
				},
			},
			{
				label: "Add Item Below",
				icon: "add",
				onClick: () => {
					frappe.app.sidebar.add_below(me.item);
				},
			},
			{
				label: "Duplicate",
				icon: "copy",
				onClick: () => {
					console.log("Start Deleting");
					frappe.app.sidebar.duplicate_item(me.item);
				},
			},
			{
				label: "Delete",
				icon: "trash-2",
				onClick: () => {
					console.log(me.item);
					frappe.app.sidebar.delete_item(me.item);
					console.log("Start Deleting");
				},
			},
		];
		return menu_items;
	}
	add_menu_items() {}
};

frappe.ui.sidebar_item.TypeSectionBreak = class SectionBreakSidebarItem extends (
	frappe.ui.sidebar_item.TypeLink
) {
	prepare(opts) {
		this.collapsed = false;
		this.nested_items = opts.item.nested_items || this.nested_items;
		this.items = [];
		this.$items = [];
		const storedState = localStorage.getItem("section-breaks-state");
		this.section_breaks_state = storedState ? JSON.parse(storedState) : {};
	}
	add_items() {
		this.$item_control = this.wrapper.find(".sidebar-item-control");
		this.$nested_items = this.wrapper.find(".nested-container").first();
		this.nested_items.forEach((f) => {
			this.items.push(
				frappe.app.sidebar.make_sidebar_item({
					container: this.$nested_items,
					item: f,
				})
			);
		});
		this.full_template = $(this.wrapper);
	}
	make() {
		if (this.item.nested_items.length == 0) return;
		super.make();
		this.add_items();
		this.toggle_on_collapse();
		this.enable_collapsible(this.item, this.full_template);
		$(this.container).append(this.full_template);
	}
	open() {
		this.collapsed = false;
		this.toggle();
	}
	close() {
		this.collapsed = true;
		this.toggle();
	}
	toggle() {
		if (this.collapsed) {
			this.$drop_icon
				.attr("data-state", "closed")
				.find("use")
				.attr("href", "#icon-chevron-right");
			$(this.$nested_items).addClass("hidden");
		} else {
			this.$drop_icon
				.attr("data-state", "opened")
				.find("use")
				.attr("href", "#icon-chevron-down");
			$(this.$nested_items).removeClass("hidden");
		}
	}
	toggle_on_collapse() {
		const me = this;
		this.old_state;
		$(document).on("sidebar-expand", function (event, expand) {
			if (expand.sidebar_expand) {
				$(me.wrapper.find(".section-break")).removeClass("hidden");
				$(me.wrapper.find(".divider")).addClass("hidden");
				if (me.old_state) {
					me.collapsed = me.old_state;
					me.toggle();
				}
			} else {
				$(me.wrapper.find(".section-break")).addClass("hidden");
				$(me.wrapper.find(".divider")).removeClass("hidden");
				me.old_state = me.collapsed;
				me.open();
				if (me.item.indent) {
					me.close();
				}
			}
		});
	}

	enable_collapsible(item, $item_container) {
		let sidebar_control = this.$item_control;
		let drop_icon = "chevron-down";
		if (item.collapsible) {
			let stroke_color = window
				.getComputedStyle(document.body)
				.getPropertyValue("--ink-gray-5");
			this.$drop_icon = $(`<button class="btn-reset drop-icon hidden">`)
				.html(frappe.utils.icon(drop_icon, "sm", "", "", "", "", stroke_color))
				.appendTo(sidebar_control);

			this.$drop_icon.removeClass("hidden");
		}

		if (item.keep_closed) {
			this.close();
		}
		if (
			Object.keys(this.section_breaks_state) &&
			this.section_breaks_state[this.workspace_title]
		) {
			this.apply_section_break_state();
		}
		if (item.show_arrow) {
			this.$drop_icon = this.wrapper.find('[item-icon="chevron-right"]');
		}
		if (item.collapsible || item.show_arrow) {
			this.setup_event_listner();
		}
	}
	apply_section_break_state() {
		const me = this;
		let current_sidebar_state = this.section_breaks_state[this.workspace_title];
		for (const [element_name, collapsed] of Object.entries(current_sidebar_state)) {
			if ($(this.wrapper).attr("item-name") == element_name) {
				me.collapsed = collapsed;
				me.toggle();
			}
		}
	}
	setup_event_listner() {
		const me = this;

		$(this.wrapper.find(".standard-sidebar-item")[0]).on("click", (e) => {
			me.collapsed = me.$drop_icon.find("use").attr("href") === "#icon-chevron-down";
			me.toggle();

			if (e.originalEvent.isTrusted) {
				me.save_section_break_state();
			}
		});
	}
	save_section_break_state() {
		if (!this.section_breaks_state[this.workspace_title]) {
			this.section_breaks_state[this.workspace_title] = {};
		}

		const title = this.$drop_icon.parent().parent().attr("title");
		this.section_breaks_state[this.workspace_title][title] = this.collapsed;

		localStorage.setItem("section-breaks-state", JSON.stringify(this.section_breaks_state));
	}

	get_menu_items() {
		let me = this;
		let menu_items = [
			{
				label: "Edit Item",
				icon: "pen",
				onClick: () => {
					console.log("Start ediitng");
					frappe.app.sidebar.edit_item(me.item);
				},
			},
			{
				label: "Add Nested Items",
				icon: "add",
				onClick: () => {
					frappe.app.sidebar.show_new_dialog({
						nested: true,
						parent_item: me.item,
					});
				},
			},
			{
				label: "Duplicate",
				icon: "copy",
				onClick: () => {
					console.log("Start Deleting");
					frappe.app.sidebar.duplicate_item(me.item);
				},
			},
			{
				label: "Delete",
				icon: "trash-2",
				onClick: () => {
					console.log(me.item);
					frappe.app.sidebar.delete_item(me.item);
					console.log("Start Deleting");
				},
			},
		];
		return menu_items;
	}
};

frappe.ui.sidebar_item.TypeSpacer = class SpacerItem extends frappe.ui.sidebar_item.TypeLink {
	constructor(item, items) {
		super(item);
	}
};

frappe.ui.sidebar_item.TypeSidebarItemGroup = class SpacerItem extends (
	frappe.ui.sidebar_item.TypeLink
) {
	constructor(item, items) {
		super(item);
		this.title = frappe.app.sidebar.workspace_title;
		this.setup_click();
	}

	setup_click() {
		const me = this;
		this.wrapper.on("click", function () {
			frappe.call({
				method: "frappe.desk.doctype.sidebar_item_group.sidebar_item_group.get_reports",
				args: { module_name: frappe.app.sidebar.workspace_title },
				callback: function (r) {
					if (r.message) {
						let links_html = "";

						r.message.forEach((report) => {
							let args = {
								type: "Report",
								name: report.title,
								is_query_report:
									report.report_type === "Query Report" ||
									report.report_type === "Script Report",
								report_ref_doctype: report.ref_doctype,
							};

							links_html += `<a href="${encodeURI(
								frappe.utils.generate_route(args)
							)}">${report.title}</a><br>`;
						});

						var d = new frappe.ui.Dialog({
							title: __(me.item.label),
							fields: [
								{
									fieldtype: "HTML",
									options: links_html,
								},
							],
						});
						d.show();
					}
				},
			});
		});
	}
};
