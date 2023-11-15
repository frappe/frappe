import EditorJS from "@editorjs/editorjs";
import Undo from "editorjs-undo";

frappe.standard_pages["Workspaces"] = function () {
	var wrapper = frappe.container.add_page("Workspaces");

	frappe.ui.make_app_page({
		parent: wrapper,
		name: "Workspaces",
		title: __("Workspace"),
	});

	frappe.workspace = new frappe.views.Workspace(wrapper);
	$(wrapper).bind("show", function () {
		frappe.workspace.show();
	});
};

frappe.views.Workspace = class Workspace {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.blocks = frappe.workspace_block.blocks;
		this.is_read_only = true;
		this.pages = {};
		this.sorted_public_items = [];
		this.sorted_private_items = [];
		this.current_page = {};
		this.sidebar_items = {
			public: {},
			private: {},
		};
		this.sidebar_categories = ["My Workspaces", "Public"];

		this.prepare_container();
		this.setup_pages();
		this.register_awesomebar_shortcut();
	}

	prepare_container() {
		let list_sidebar = $(`
			<div class="list-sidebar overlay-sidebar hidden-xs hidden-sm">
				<div class="desk-sidebar list-unstyled sidebar-menu"></div>
			</div>
		`).appendTo(this.wrapper.find(".layout-side-section"));
		this.sidebar = list_sidebar.find(".desk-sidebar");
		this.body = this.wrapper.find(".layout-main-section");
	}

	async setup_pages(reload) {
		!this.discard && this.create_page_skeleton();
		!this.discard && this.create_sidebar_skeleton();
		this.sidebar_pages = !this.discard ? await this.get_pages() : this.sidebar_pages;
		this.cached_pages = $.extend(true, {}, this.sidebar_pages);
		this.all_pages = this.sidebar_pages.pages;
		this.has_access = this.sidebar_pages.has_access;

		this.all_pages.forEach((page) => {
			page.is_editable = !page.public || this.has_access;
		});

		this.public_pages = this.all_pages.filter((page) => page.public);
		this.private_pages = this.all_pages.filter((page) => !page.public);

		if (this.all_pages) {
			frappe.workspaces = {};
			for (let page of this.all_pages) {
				frappe.workspaces[frappe.router.slug(page.name)] = {
					title: page.title,
					public: page.public,
				};
			}
			this.make_sidebar();
			reload && this.show();
		}
	}

	get_pages() {
		return frappe.xcall("frappe.desk.desktop.get_workspace_sidebar_items");
	}

	sidebar_item_container(item) {
		return $(`
			<div
				class="sidebar-item-container ${item.is_editable ? "is-draggable" : ""}"
				item-parent="${item.parent_page}"
				item-name="${item.title}"
				item-public="${item.public || 0}"
				item-is-hidden="${item.is_hidden || 0}"
			>
				<div class="desk-sidebar-item standard-sidebar-item ${item.selected ? "selected" : ""}">
					<a
						href="/app/${
							item.public
								? frappe.router.slug(item.title)
								: "private/" + frappe.router.slug(item.title)
						}"
						class="item-anchor ${item.is_editable ? "" : "block-click"}" title="${__(item.title)}"
					>
						<span class="sidebar-item-icon" item-icon=${item.icon || "folder-normal"}>${frappe.utils.icon(
			item.icon || "folder-normal",
			"md"
		)}</span>
						<span class="sidebar-item-label">${__(item.title)}<span>
					</a>
					<div class="sidebar-item-control"></div>
				</div>
				<div class="sidebar-child-item nested-container"></div>
			</div>
		`);
	}

	make_sidebar() {
		if (this.sidebar.find(".standard-sidebar-section")[0]) {
			this.sidebar.find(".standard-sidebar-section").remove();
		}

		this.sidebar_categories.forEach((category) => {
			let root_pages = this.public_pages.filter(
				(page) => page.parent_page == "" || page.parent_page == null
			);
			if (category != "Public") {
				root_pages = this.private_pages.filter(
					(page) => page.parent_page == "" || page.parent_page == null
				);
			}
			root_pages = root_pages.uniqBy((d) => d.title);
			this.build_sidebar_section(category, root_pages);
		});

		// Scroll sidebar to selected page if it is not in viewport.
		this.sidebar.find(".selected").length &&
			!frappe.dom.is_element_in_viewport(this.sidebar.find(".selected")) &&
			this.sidebar.find(".selected")[0].scrollIntoView();

		this.remove_sidebar_skeleton();
	}

	build_sidebar_section(title, root_pages) {
		let sidebar_section = $(
			`<div class="standard-sidebar-section nested-container" data-title="${title}"></div>`
		);

		let $title = $(`<div class="standard-sidebar-label">
			<span>${frappe.utils.icon("small-down", "xs")}</span>
			<span class="section-title">${__(title)}<span>
		</div>`).appendTo(sidebar_section);
		this.prepare_sidebar(root_pages, sidebar_section, this.sidebar);

		$title.on("click", (e) => {
			let icon =
				$(e.target).find("span use").attr("href") === "#icon-small-down"
					? "#icon-right"
					: "#icon-small-down";
			$(e.target).find("span use").attr("href", icon);
			$(e.target).parent().find(".sidebar-item-container").toggleClass("hidden");
		});

		if (Object.keys(root_pages).length === 0) {
			sidebar_section.addClass("hidden");
		}

		if (
			sidebar_section.find(".sidebar-item-container").length &&
			sidebar_section.find("> [item-is-hidden='0']").length == 0
		) {
			sidebar_section.addClass("hidden show-in-edit-mode");
		}
	}

	prepare_sidebar(items, child_container, item_container) {
		items.forEach((item) => this.append_item(item, child_container));
		child_container.appendTo(item_container);
	}

	append_item(item, container) {
		let is_current_page =
			frappe.router.slug(item.title) == frappe.router.slug(this.get_page_to_show().name) &&
			item.public == this.get_page_to_show().public;
		item.selected = is_current_page;
		if (is_current_page) {
			this.current_page = { name: item.title, public: item.public };
		}

		let $item_container = this.sidebar_item_container(item);
		let sidebar_control = $item_container.find(".sidebar-item-control");

		this.add_sidebar_actions(item, sidebar_control);
		let pages = item.public ? this.public_pages : this.private_pages;

		let child_items = pages.filter((page) => page.parent_page == item.title);
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

		this.add_drop_icon(item, sidebar_control, $item_container);

		if (child_items.length > 0) {
			$item_container.find(".drop-icon").first().addClass("show-in-edit-mode");
		}
	}

	add_drop_icon(item, sidebar_control, item_container) {
		let drop_icon = "small-down";
		if (item_container.find(`[item-name="${this.current_page.name}"]`).length) {
			drop_icon = "small-up";
		}

		let $child_item_section = item_container.find(".sidebar-child-item");
		let $drop_icon = $(
			`<span class="drop-icon hidden">${frappe.utils.icon(drop_icon, "sm")}</span>`
		).appendTo(sidebar_control);
		let pages = item.public ? this.public_pages : this.private_pages;
		if (
			pages.some(
				(e) => e.parent_page == item.title && (e.is_hidden == 0 || !this.is_read_only)
			)
		) {
			$drop_icon.removeClass("hidden");
		}
		$drop_icon.on("click", () => {
			let icon =
				$drop_icon.find("use").attr("href") === "#icon-small-down"
					? "#icon-small-up"
					: "#icon-small-down";
			$drop_icon.find("use").attr("href", icon);
			$child_item_section.toggleClass("hidden");
		});
	}

	show() {
		if (!this.all_pages) {
			// pages not yet loaded, call again after a bit
			setTimeout(() => this.show(), 100);
			return;
		}

		let page = this.get_page_to_show();
		this.page.set_title(__(page.name));

		this.update_selected_sidebar(this.current_page, false); //remove selected from old page
		this.update_selected_sidebar(page, true); //add selected on new page

		if (!frappe.router.current_route[0]) {
			frappe.router.current_route = !page.public
				? ["Workspaces", "private", page.name]
				: ["Workspaces", page.name];
		}

		this.show_page(page);
	}

	update_selected_sidebar(page, add) {
		let section = page.public ? "public" : "private";
		if (
			this.sidebar &&
			this.sidebar_items[section] &&
			this.sidebar_items[section][page.name]
		) {
			let $sidebar = this.sidebar_items[section][page.name];
			let pages = page.public ? this.public_pages : this.private_pages;
			let sidebar_page = pages.find((p) => p.title == page.name);

			if (add) {
				$sidebar[0].firstElementChild.classList.add("selected");
				if (sidebar_page) sidebar_page.selected = true;

				// open child sidebar section if closed
				$sidebar.parent().hasClass("sidebar-child-item") &&
					$sidebar.parent().hasClass("hidden") &&
					$sidebar.parent().removeClass("hidden");

				this.current_page = { name: page.name, public: page.public };
				localStorage.current_page = page.name;
				localStorage.is_current_page_public = page.public;
			} else {
				$sidebar[0].firstElementChild.classList.remove("selected");
				if (sidebar_page) sidebar_page.selected = false;
			}
		}
	}

	get_data(page) {
		return frappe
			.call("frappe.desk.desktop.get_desktop_page", {
				page: page,
			})
			.then((data) => {
				this.page_data = data.message;

				// caching page data
				this.pages[page.name] && delete this.pages[page.name];
				this.pages[page.name] = data.message;

				if (!this.page_data || Object.keys(this.page_data).length === 0) return;
				if (this.page_data.charts && this.page_data.charts.items.length === 0) return;

				return frappe.dashboard_utils.get_dashboard_settings().then((settings) => {
					if (settings) {
						let chart_config = settings.chart_config
							? JSON.parse(settings.chart_config)
							: {};
						this.page_data.charts.items.map((chart) => {
							chart.chart_settings = chart_config[chart.chart_name] || {};
						});
						this.pages[page.name] = this.page_data;
					}
				});
			});
	}

	get_page_to_show() {
		let default_page;

		if (
			localStorage.current_page &&
			this.all_pages.filter((page) => page.title == localStorage.current_page).length != 0
		) {
			default_page = {
				name: localStorage.current_page,
				public: localStorage.is_current_page_public != "false",
			};
		} else if (Object.keys(this.all_pages).length !== 0) {
			default_page = { name: this.all_pages[0].title, public: this.all_pages[0].public };
		} else {
			default_page = { name: "Build", public: true };
		}

		let page =
			(frappe.get_route()[1] == "private" ? frappe.get_route()[2] : frappe.get_route()[1]) ||
			default_page.name;
		let is_public = frappe.get_route()[1]
			? frappe.get_route()[1] != "private"
			: default_page.public;
		return { name: page, public: is_public };
	}

	async show_page(page) {
		if (!this.body.find("#editorjs")[0]) {
			this.$page = $(`
				<div id="editorjs" class="desk-page page-main-content"></div>
			`).appendTo(this.body);
		}

		if (this.all_pages.length) {
			this.create_page_skeleton();

			let pages =
				page.public && this.public_pages.length ? this.public_pages : this.private_pages;
			let current_page = pages.filter((p) => p.title == page.name)[0];
			this.content = current_page && JSON.parse(current_page.content);

			this.content && this.add_custom_cards_in_content();

			$(".item-anchor").addClass("disable-click");

			if (this.pages && this.pages[current_page.name]) {
				this.page_data = this.pages[current_page.name];
			} else {
				await frappe.after_ajax(() => this.get_data(current_page));
			}

			this.setup_actions(page);

			this.prepare_editorjs();
			$(".item-anchor").removeClass("disable-click");

			this.remove_page_skeleton();
		}
	}

	add_custom_cards_in_content() {
		let index = -1;
		this.content.find((item, i) => {
			if (item.type == "card") index = i;
		});
		if (index !== -1) {
			this.content.splice(index + 1, 0, {
				type: "card",
				data: { card_name: "Custom Documents", col: 4 },
			});
			this.content.splice(index + 2, 0, {
				type: "card",
				data: { card_name: "Custom Reports", col: 4 },
			});
		}
	}

	prepare_editorjs() {
		if (this.editor) {
			this.editor.isReady.then(() => {
				this.editor.configuration.tools.chart.config.page_data = this.page_data;
				this.editor.configuration.tools.shortcut.config.page_data = this.page_data;
				this.editor.configuration.tools.card.config.page_data = this.page_data;
				this.editor.configuration.tools.onboarding.config.page_data = this.page_data;
				this.editor.configuration.tools.quick_list.config.page_data = this.page_data;
				this.editor.configuration.tools.number_card.config.page_data = this.page_data;
				this.editor.configuration.tools.custom_block.config.page_data = this.page_data;
				this.editor.render({ blocks: this.content || [] });
			});
		} else {
			this.initialize_editorjs(this.content);
		}
	}

	setup_actions(page) {
		let pages = page.public ? this.public_pages : this.private_pages;
		let current_page = pages.filter((p) => p.title == page.name)[0];

		if (!this.is_read_only) {
			this.setup_customization_buttons(current_page);
			return;
		}

		this.clear_page_actions();

		this.page.set_secondary_action(__("Edit"), async () => {
			if (!this.editor || !this.editor.readOnly) return;
			this.is_read_only = false;
			this.toggle_hidden_workspaces(true);
			await this.editor.readOnly.toggle();
			this.editor.isReady.then(() => {
				this.initialize_editorjs_undo();
				this.setup_customization_buttons(current_page);
				this.show_sidebar_actions();
				this.make_blocks_sortable();
			});
		});

		this.page.add_inner_button(__("Create Workspace"), () => {
			this.initialize_new_page();
		});
	}

	initialize_editorjs_undo() {
		this.undo = new Undo({ editor: this.editor });
		this.undo.initialize({ blocks: this.content || [] });
		this.undo.readOnly = false;
	}

	clear_page_actions() {
		this.page.clear_primary_action();
		this.page.clear_secondary_action();
		this.page.clear_inner_toolbar();
	}

	setup_customization_buttons(page) {
		this.clear_page_actions();

		page.is_editable &&
			this.page.set_primary_action(
				__("Save"),
				() => {
					this.clear_page_actions();
					this.save_page(page).then((saved) => {
						if (!saved) return;
						this.undo.readOnly = true;
						this.editor.readOnly.toggle();
						this.is_read_only = true;
					});
				},
				null,
				__("Saving")
			);

		this.page.set_secondary_action(__("Discard"), async () => {
			this.discard = true;
			this.clear_page_actions();
			this.toggle_hidden_workspaces(false);
			await this.editor.readOnly.toggle();
			this.is_read_only = true;
			this.sidebar_pages = this.cached_pages;
			this.reload();
			frappe.show_alert({ message: __("Customizations Discarded"), indicator: "info" });
		});

		if (page.name && this.has_access) {
			this.page.add_inner_button(__("Settings"), () => {
				frappe.set_route(`workspace/${page.name}`);
			});
		}
	}

	toggle_hidden_workspaces(show) {
		$(".desk-sidebar").toggleClass("show-hidden-workspaces", show);
	}

	show_sidebar_actions() {
		this.sidebar.find(".standard-sidebar-section").addClass("show-control");
		this.make_sidebar_sortable();
	}

	add_sidebar_actions(item, sidebar_control, is_new) {
		if (!item.is_editable) {
			sidebar_control.parent().click(() => {
				!this.is_read_only &&
					frappe.show_alert(
						{
							message: __("Only Workspace Manager can sort or edit this page"),
							indicator: "info",
						},
						5
					);
			});

			frappe.utils.add_custom_button(
				frappe.utils.icon("duplicate", "sm"),
				() => this.duplicate_page(item),
				"duplicate-page",
				__("Duplicate Workspace"),
				null,
				sidebar_control
			);
		} else if (item.is_hidden) {
			frappe.utils.add_custom_button(
				frappe.utils.icon("unhide", "sm"),
				(e) => this.unhide_workspace(item, e),
				"unhide-workspace-btn",
				__("Unhide Workspace"),
				null,
				sidebar_control
			);
		} else {
			frappe.utils.add_custom_button(
				frappe.utils.icon("drag", "xs"),
				null,
				"drag-handle",
				__("Drag"),
				null,
				sidebar_control
			);

			!is_new && this.add_settings_button(item, sidebar_control);
		}
	}

	get_parent_pages(page) {
		this.public_parent_pages = [
			"",
			...this.public_pages.filter((p) => !p.parent_page).map((p) => p.title),
		];
		this.private_parent_pages = [
			"",
			...this.private_pages.filter((p) => !p.parent_page).map((p) => p.title),
		];

		if (page) {
			return page.public ? this.public_parent_pages : this.private_parent_pages;
		}
	}

	edit_page(item) {
		var me = this;
		let old_item = item;
		let parent_pages = this.get_parent_pages(item);
		let idx = parent_pages.findIndex((x) => x == item.title);
		if (idx !== -1) parent_pages.splice(idx, 1);
		const d = new frappe.ui.Dialog({
			title: __("Update Details"),
			fields: [
				{
					label: __("Title"),
					fieldtype: "Data",
					fieldname: "title",
					reqd: 1,
					default: item.title,
				},
				{
					label: __("Parent"),
					fieldtype: "Select",
					fieldname: "parent",
					options: parent_pages,
					default: item.parent_page,
				},
				{
					label: __("Public"),
					fieldtype: "Check",
					fieldname: "is_public",
					depends_on: `eval:${this.has_access}`,
					default: item.public,
					onchange: function () {
						d.set_df_property(
							"parent",
							"options",
							this.get_value() ? me.public_parent_pages : me.private_parent_pages
						);
					},
				},
				{
					fieldtype: "Column Break",
				},
				{
					label: __("Icon"),
					fieldtype: "Icon",
					fieldname: "icon",
					default: item.icon,
				},
			],
			primary_action_label: __("Update"),
			primary_action: (values) => {
				values.title = frappe.utils.escape_html(values.title);
				let is_title_changed = values.title != old_item.title;
				let is_section_changed = values.is_public != old_item.public;
				if (
					(is_title_changed || is_section_changed) &&
					!this.validate_page(values, old_item)
				)
					return;
				d.hide();

				frappe.call({
					method: "frappe.desk.doctype.workspace.workspace.update_page",
					args: {
						name: old_item.name,
						title: values.title,
						icon: values.icon || "",
						parent: values.parent || "",
						public: values.is_public || 0,
					},
					callback: function (res) {
						if (res.message) {
							let message = __("Workspace {0} Edited Successfully", [
								old_item.title.bold(),
							]);
							frappe.show_alert({ message: message, indicator: "green" });
						}
					},
				});

				this.update_sidebar(old_item, values);

				if (this.make_page_selected) {
					let pre_url = values.is_public ? "" : "private/";
					let route = pre_url + frappe.router.slug(values.title);
					frappe.set_route(route);

					this.make_page_selected = false;
				}

				this.make_sidebar();
				this.show_sidebar_actions();
			},
		});
		d.show();
	}

	update_sidebar(old_item, new_item) {
		let is_section_changed = old_item.public != (new_item.is_public || 0);
		let is_title_changed = old_item.title != new_item.title;
		let new_updated_item = { ...old_item };

		let pages = old_item.public ? this.public_pages : this.private_pages;

		let child_items = pages.filter((page) => page.parent_page == old_item.title);

		this.make_page_selected = old_item.selected;

		new_updated_item.title = new_item.title;
		new_updated_item.icon = new_item.icon;
		new_updated_item.parent_page = new_item.parent || "";
		new_updated_item.public = new_item.is_public;

		if (is_title_changed || is_section_changed) {
			if (new_item.is_public) {
				new_updated_item.name = new_item.title;
				new_updated_item.label = new_item.title;
				new_updated_item.for_user = "";
			} else {
				let user = frappe.session.user;
				new_updated_item.name = `${new_item.title}-${user}`;
				new_updated_item.label = `${new_item.title}-${user}`;
				new_updated_item.for_user = user;
			}
		}
		this.update_cached_values(old_item, new_updated_item);

		if (child_items.length) {
			child_items.forEach((child) => {
				child.parent_page = new_item.title;
				is_section_changed && this.update_child_sidebar(child, new_item);
			});
		}
	}

	update_child_sidebar(child, new_item) {
		let old_child = { ...child };
		this.make_page_selected = child.selected;

		child.public = new_item.is_public;
		if (new_item.is_public) {
			child.name = child.title;
			child.label = child.title;
			child.for_user = "";
		} else {
			let user = frappe.session.user;
			child.name = `${child.title}-${user}`;
			child.label = `${child.title}-${user}`;
			child.for_user = user;
		}

		this.update_cached_values(old_child, child);
	}

	update_cached_values(old_item, new_item, duplicate, new_page) {
		let [from_pages, to_pages] = old_item.public
			? [this.public_pages, this.private_pages]
			: [this.private_pages, this.public_pages];

		let old_item_index = from_pages.findIndex((page) => page.title == old_item.title);
		duplicate && old_item_index++;

		// update frappe.workspaces
		if (frappe.workspaces[frappe.router.slug(old_item.name)] || new_page) {
			!duplicate && delete frappe.workspaces[frappe.router.slug(old_item.name)];
			if (new_item) {
				frappe.workspaces[frappe.router.slug(new_item.name)] = { title: new_item.title };
			}
		}

		// update page block data
		if ((this.pages && this.pages[old_item.name]) || new_page) {
			if (new_item) {
				this.pages[new_item.name] = this.pages[old_item.name] || {};
			}
			!duplicate && delete this.pages[old_item.name];
		}

		// update public and private pages
		if (new_item) {
			let is_section_changed =
				old_item.public != (new_item.is_public || new_item.public || 0);

			if (is_section_changed) {
				!duplicate && from_pages.splice(old_item_index, 1);
				to_pages.push(new_item);
			} else if (new_page) {
				from_pages.push(new_item);
			} else {
				from_pages.splice(old_item_index, duplicate ? 0 : 1, new_item);
			}
		} else {
			from_pages.splice(old_item_index, 1);
		}

		this.sidebar_pages.pages = [...this.public_pages, ...this.private_pages];
		this.cached_pages = this.sidebar_pages;
	}

	add_settings_button(item, sidebar_control) {
		this.dropdown_list = [
			{
				label: __("Edit"),
				title: __("Edit Workspace"),
				icon: frappe.utils.icon("edit", "sm"),
				action: () => this.edit_page(item),
			},
			{
				label: __("Duplicate"),
				title: __("Duplicate Workspace"),
				icon: frappe.utils.icon("duplicate", "sm"),
				action: () => this.duplicate_page(item),
			},
			{
				label: __("Hide"),
				title: __("Hide Workspace"),
				icon: frappe.utils.icon("hide", "sm"),
				action: (e) => this.hide_workspace(item, e),
			},
		];

		if (this.is_item_deletable(item)) {
			this.dropdown_list.push({
				label: __("Delete"),
				title: __("Delete Workspace"),
				icon: frappe.utils.icon("delete-active", "sm"),
				action: () => this.delete_page(item),
			});
		}

		let $button = $(`
			<div class="btn btn-secondary btn-xs setting-btn dropdown-btn" title="${__("Setting")}">
				${frappe.utils.icon("dot-horizontal", "xs")}
			</div>
			<div class="dropdown-list hidden"></div>
		`);

		let dropdown_item = function (label, title, icon, action) {
			let html = $(`
				<div class="dropdown-item" title="${title}">
					<span class="dropdown-item-icon">${icon}</span>
					<span class="dropdown-item-label">${label}</span>
				</div>
			`);

			html.click((event) => {
				event.stopPropagation();
				action && action(event);
			});

			return html;
		};

		$button.filter(".dropdown-btn").click((event) => {
			event.stopPropagation();
			if ($button.filter(".dropdown-list.hidden").length) {
				$(".dropdown-list:not(.hidden)").addClass("hidden");
			}
			$button.filter(".dropdown-list").toggleClass("hidden");
		});

		sidebar_control.append($button);

		this.dropdown_list.forEach((i) => {
			$button
				.filter(".dropdown-list")
				.append(dropdown_item(i.label, i.title, i.icon, i.action));
		});
	}

	is_item_deletable(item) {
		// if item is private
		// if item is public but doesn't have module set
		// if item is public and has module set but developer mode is on
		// then item is deletable
		if (
			!item.public ||
			(item.public && (!item.module || (item.module && frappe.boot.developer_mode)))
		)
			return true;
		return false;
	}

	delete_page(page) {
		frappe.confirm(
			__("Are you sure you want to delete page {0}?", [page.title.bold()]),
			() => {
				frappe.call({
					method: "frappe.desk.doctype.workspace.workspace.delete_page",
					args: { page: page },
					callback: function (res) {
						if (res.message) {
							let page = res.message;
							let message = __("Workspace {0} Deleted Successfully", [
								page.title.bold(),
							]);
							frappe.show_alert({ message: message, indicator: "green" });
						}
					},
				});

				this.page.clear_primary_action();
				this.update_cached_values(page);

				if (
					this.current_page.name == page.title &&
					this.current_page.public == page.public
				) {
					frappe.set_route("/");
				}

				this.make_sidebar();
				this.show_sidebar_actions();
			}
		);
	}

	duplicate_page(page) {
		var me = this;
		let new_page = { ...page };
		if (!this.has_access && new_page.public) {
			new_page.public = 0;
		}
		let parent_pages = this.get_parent_pages({ public: new_page.public });
		const d = new frappe.ui.Dialog({
			title: __("Create Duplicate"),
			fields: [
				{
					label: __("Title"),
					fieldtype: "Data",
					fieldname: "title",
					reqd: 1,
				},
				{
					label: __("Parent"),
					fieldtype: "Select",
					fieldname: "parent",
					options: parent_pages,
					default: new_page.parent_page,
				},
				{
					label: __("Public"),
					fieldtype: "Check",
					fieldname: "is_public",
					depends_on: `eval:${this.has_access}`,
					default: new_page.public,
					onchange: function () {
						d.set_df_property(
							"parent",
							"options",
							this.get_value() ? me.public_parent_pages : me.private_parent_pages
						);
					},
				},
				{
					fieldtype: "Column Break",
				},
				{
					label: __("Icon"),
					fieldtype: "Icon",
					fieldname: "icon",
					default: new_page.icon,
				},
			],
			primary_action_label: __("Duplicate"),
			primary_action: (values) => {
				if (!this.validate_page(values)) return;
				d.hide();
				frappe.call({
					method: "frappe.desk.doctype.workspace.workspace.duplicate_page",
					args: {
						page_name: page.name,
						new_page: values,
					},
					callback: function (res) {
						if (res.message) {
							let new_page = res.message;
							let message = __(
								"Duplicate of {0} named as {1} is created successfully",
								[page.title.bold(), new_page.title.bold()]
							);
							frappe.show_alert({ message: message, indicator: "green" });
						}
					},
				});

				new_page.title = values.title;
				new_page.public = values.is_public || 0;
				new_page.name = values.title + (new_page.public ? "" : "-" + frappe.session.user);
				new_page.label = new_page.name;
				new_page.icon = values.icon;
				new_page.parent_page = values.parent || "";
				new_page.for_user = new_page.public ? "" : frappe.session.user;
				new_page.is_editable = !new_page.public;
				new_page.selected = true;

				this.update_cached_values(page, new_page, true);

				let pre_url = values.is_public ? "" : "private/";
				let route = pre_url + frappe.router.slug(values.title);
				frappe.set_route(route);

				me.make_sidebar();
				me.show_sidebar_actions();
			},
		});
		d.show();
	}

	hide_unhide_workspace(page, event, hide) {
		page.is_hidden = hide;

		let sidebar_control = event.target.closest(".sidebar-item-control");
		let sidebar_item_container = sidebar_control.closest(".sidebar-item-container");
		$(sidebar_item_container).attr("item-is-hidden", hide);

		$(sidebar_control).empty();
		this.add_sidebar_actions(page, $(sidebar_control));

		this.add_drop_icon(page, $(sidebar_control), $(sidebar_item_container));

		let cached_page = this.cached_pages.pages.findIndex((p) => p.name === page.name);
		if (cached_page !== -1) {
			this.cached_pages.pages[cached_page].is_hidden = hide;
		}

		let method = hide ? "hide_page" : "unhide_page";
		frappe.call({
			method: "frappe.desk.doctype.workspace.workspace." + method,
			args: {
				page_name: page.name,
			},
			callback: (r) => {
				if (!r.message) return;

				let message = hide ? "{0} is hidden successfully" : "{0} is unhidden successfully";
				message = __(message, [page.title.bold()]);
				frappe.show_alert({ message: message, indicator: "green" });
			},
		});
	}

	hide_workspace(page, event) {
		this.hide_unhide_workspace(page, event, 1);
	}

	unhide_workspace(page, event) {
		this.hide_unhide_workspace(page, event, 0);
	}

	make_sidebar_sortable() {
		let me = this;
		$(".nested-container").each(function () {
			new Sortable(this, {
				handle: ".drag-handle",
				draggable: ".sidebar-item-container.is-draggable",
				group: "nested",
				animation: 150,
				fallbackOnBody: true,
				swapThreshold: 0.65,
				onEnd: function (evt) {
					let is_public = $(evt.item).attr("item-public") == "1";
					me.prepare_sorted_sidebar(is_public);
					me.update_sorted_sidebar();
				},
			});
		});
	}

	prepare_sorted_sidebar(is_public) {
		let pages = is_public ? this.public_pages : this.private_pages;
		if (is_public) {
			this.sorted_public_items = this.sort_sidebar(
				this.sidebar.find(".standard-sidebar-section").last(),
				pages
			);
		} else {
			this.sorted_private_items = this.sort_sidebar(
				this.sidebar.find(".standard-sidebar-section").first(),
				pages
			);
		}

		this.sidebar_pages.pages = [...this.public_pages, ...this.private_pages];
		this.cached_pages = this.sidebar_pages;
	}

	sort_sidebar($sidebar_section, pages) {
		let sorted_items = [];
		Array.from($sidebar_section.find(".sidebar-item-container")).forEach((page, i) => {
			let parent_page = "";

			if (page.closest(".nested-container").classList.contains("sidebar-child-item")) {
				parent_page = page.parentElement.parentElement.attributes["item-name"].value;
			}

			sorted_items.push({
				title: page.attributes["item-name"].value,
				parent_page: parent_page,
				public: page.attributes["item-public"].value,
			});

			let $drop_icon = $(page).find(".sidebar-item-control .drop-icon").first();
			if ($(page).find(".sidebar-child-item > *").length != 0) {
				$drop_icon.removeClass("hidden");
			} else {
				$drop_icon.addClass("hidden");
			}

			let from_index = pages.findIndex((p) => p.title == page.attributes["item-name"].value);
			let element = pages[from_index];
			element.parent_page = parent_page;
			if (from_index != i) {
				pages.splice(from_index, 1);
				pages.splice(i, 0, element);
			}
		});
		return sorted_items;
	}

	update_sorted_sidebar() {
		if (this.sorted_public_items || this.sorted_private_items) {
			frappe.call({
				method: "frappe.desk.doctype.workspace.workspace.sort_pages",
				args: {
					sb_public_items: this.sorted_public_items,
					sb_private_items: this.sorted_private_items,
				},
				callback: function (res) {
					if (res.message) {
						let message = `Sidebar Updated Successfully`;
						frappe.show_alert({ message: __(message), indicator: "green" });
					}
				},
			});
		}
	}

	make_blocks_sortable() {
		let me = this;
		this.page_sortable = Sortable.create(
			this.page.main.find(".codex-editor__redactor").get(0),
			{
				handle: ".drag-handle",
				draggable: ".ce-block",
				animation: 150,
				onEnd: function (evt) {
					me.editor.blocks.move(evt.newIndex, evt.oldIndex);
				},
				setData: function () {
					//Do Nothing
				},
			}
		);
	}

	initialize_new_page() {
		var me = this;
		this.get_parent_pages();
		const d = new frappe.ui.Dialog({
			title: __("New Workspace"),
			fields: [
				{
					label: __("Title"),
					fieldtype: "Data",
					fieldname: "title",
					reqd: 1,
				},
				{
					label: __("Parent"),
					fieldtype: "Select",
					fieldname: "parent",
					options: this.private_parent_pages,
				},
				{
					label: __("Public"),
					fieldtype: "Check",
					fieldname: "is_public",
					depends_on: `eval:${this.has_access}`,
					onchange: function () {
						d.set_df_property(
							"parent",
							"options",
							this.get_value() ? me.public_parent_pages : me.private_parent_pages
						);
					},
				},
				{
					fieldtype: "Column Break",
				},
				{
					label: __("Icon"),
					fieldtype: "Icon",
					fieldname: "icon",
				},
			],
			primary_action_label: __("Create"),
			primary_action: (values) => {
				values.title = frappe.utils.escape_html(values.title);
				if (!this.validate_page(values)) return;
				d.hide();
				this.initialize_editorjs_undo();
				this.setup_customization_buttons({ is_editable: true });

				let name = values.title + (values.is_public ? "" : "-" + frappe.session.user);
				let blocks = [
					{
						type: "header",
						data: { text: values.title },
					},
				];

				let new_page = {
					content: JSON.stringify(blocks),
					name: name,
					label: name,
					title: values.title,
					public: values.is_public || 0,
					for_user: values.is_public ? "" : frappe.session.user,
					icon: values.icon,
					parent_page: values.parent || "",
					is_editable: true,
					selected: true,
				};

				this.editor
					.render({
						blocks: blocks,
					})
					.then(async () => {
						if (this.editor.configuration.readOnly) {
							this.is_read_only = false;
							await this.editor.readOnly.toggle();
						}

						frappe.call({
							method: "frappe.desk.doctype.workspace.workspace.new_page",
							args: {
								new_page: new_page,
							},
							callback: function (res) {
								if (res.message) {
									let message = __("Workspace {0} Created Successfully", [
										new_page.title.bold(),
									]);
									frappe.show_alert({
										message: message,
										indicator: "green",
									});
								}
							},
						});

						this.update_cached_values(new_page, new_page, true, true);

						let pre_url = new_page.public ? "" : "private/";
						let route = pre_url + frappe.router.slug(new_page.title);
						frappe.set_route(route);

						this.make_sidebar();
						this.show_sidebar_actions();
						localStorage.setItem("new_workspace", JSON.stringify(new_page));
					});
			},
		});
		d.show();
	}

	validate_page(new_page, old_page) {
		let message = "";
		let [from_pages, to_pages] = new_page.is_public
			? [this.private_pages, this.public_pages]
			: [this.public_pages, this.private_pages];

		let section = this.sidebar_categories[new_page.is_public];

		if (to_pages && to_pages.filter((p) => p.title == new_page.title)[0]) {
			message = __("Page with title {0} already exist.", [new_page.title.bold()]);
		}

		if (frappe.router.doctype_route_exist(frappe.router.slug(new_page.title))) {
			message = __("Doctype with same route already exist. Please choose different title.");
		}

		let child_pages = old_page && from_pages.filter((p) => p.parent_page == old_page.title);
		if (child_pages) {
			child_pages.every((child_page) => {
				if (to_pages && to_pages.find((p) => p.title == child_page.title)) {
					message = __(
						"One of the child page with name {0} already exist in {1} Section. Please update the name of the child page first before moving",
						[child_page.title.bold(), section.bold()]
					);
					cur_dialog.hide();
					return false;
				}
				return true;
			});
		}

		if (message) {
			frappe.throw(__(message));
			return false;
		}
		return true;
	}

	add_page_to_sidebar(page) {
		let $sidebar = $(".standard-sidebar-section");
		let item = { ...page };

		item.selected = true;
		item.is_editable = true;

		let $sidebar_item = this.sidebar_item_container(item);

		this.add_sidebar_actions(item, $sidebar_item.find(".sidebar-item-control"), true);

		$sidebar_item.find(".sidebar-item-control .drag-handle").css("margin-right", "8px");

		let sidebar_section = item.is_public ? $sidebar[1] : $sidebar[0];

		if (!item.parent) {
			!item.is_public && $sidebar.first().removeClass("hidden");
			$sidebar_item.appendTo(sidebar_section);
		} else {
			let $item_container = $(sidebar_section).find(`[item-name="${item.parent}"]`);
			let $child_section = $item_container.find(".sidebar-child-item");
			let $drop_icon = $item_container.find(".drop-icon");
			if (!$child_section[0]) {
				$child_section = $(
					`<div class="sidebar-child-item hidden nested-container"></div>`
				).appendTo($item_container);
				$drop_icon.toggleClass("hidden");
			}
			$sidebar_item.appendTo($child_section);
			$child_section.removeClass("hidden");
			$item_container.find(".drop-icon.hidden").removeClass("hidden");
			$item_container.find(".drop-icon use").attr("href", "#icon-small-up");
		}

		let section = item.is_public ? "public" : "private";
		if (
			this.sidebar_items &&
			this.sidebar_items[section] &&
			!this.sidebar_items[section][item.title]
		) {
			this.sidebar_items[section][item.title] = $sidebar_item;
		}
	}

	initialize_editorjs(blocks) {
		this.tools = {
			header: {
				class: this.blocks["header"],
				inlineToolbar: ["HeaderSize", "bold", "italic", "link"],
				config: {
					default_size: 4,
				},
			},
			paragraph: {
				class: this.blocks["paragraph"],
				inlineToolbar: ["HeaderSize", "bold", "italic", "link"],
				config: {
					placeholder: __("Choose a block or continue typing"),
				},
			},
			chart: {
				class: this.blocks["chart"],
				config: {
					page_data: this.page_data || [],
				},
			},
			card: {
				class: this.blocks["card"],
				config: {
					page_data: this.page_data || [],
				},
			},
			shortcut: {
				class: this.blocks["shortcut"],
				config: {
					page_data: this.page_data || [],
				},
			},
			onboarding: {
				class: this.blocks["onboarding"],
				config: {
					page_data: this.page_data || [],
				},
			},
			quick_list: {
				class: this.blocks["quick_list"],
				config: {
					page_data: this.page_data || [],
				},
			},
			number_card: {
				class: this.blocks["number_card"],
				config: {
					page_data: this.page_data || [],
				},
			},
			custom_block: {
				class: this.blocks["custom_block"],
				config: {
					page_data: this.page_data || [],
				},
			},
			spacer: this.blocks["spacer"],
			HeaderSize: frappe.workspace_block.tunes["header_size"],
		};

		this.editor = new EditorJS({
			data: {
				blocks: blocks || [],
			},
			tools: this.tools,
			autofocus: false,
			readOnly: true,
			logLevel: "ERROR",
		});
	}

	save_page(page) {
		let me = this;
		this.current_page = { name: page.title, public: page.public };

		return this.editor
			.save()
			.then((outputData) => {
				let new_widgets = {};

				outputData.blocks.forEach((item) => {
					if (item.data.new) {
						if (!new_widgets[item.type]) {
							new_widgets[item.type] = [];
						}
						new_widgets[item.type].push(item.data.new);
						delete item.data["new"];
					}
				});

				let blocks = outputData.blocks.filter(
					(item) =>
						item.type != "card" ||
						(item.data.card_name !== "Custom Documents" &&
							item.data.card_name !== "Custom Reports")
				);

				if (
					page.content == JSON.stringify(blocks) &&
					Object.keys(new_widgets).length === 0
				) {
					this.setup_customization_buttons(page);
					frappe.show_alert({
						message: __("No changes made on the page"),
						indicator: "warning",
					});
					return false;
				}

				this.create_page_skeleton();
				page.content = JSON.stringify(blocks);
				frappe.call({
					method: "frappe.desk.doctype.workspace.workspace.save_page",
					args: {
						title: page.title,
						public: page.public || 0,
						new_widgets: new_widgets,
						blocks: JSON.stringify(blocks),
					},
					callback: function (res) {
						if (res.message) {
							me.discard = true;
							me.update_cached_values(page, page);
							me.reload();
							frappe.show_alert({
								message: __("Page Saved Successfully"),
								indicator: "green",
							});
						}
					},
				});
				return true;
			})
			.catch((error) => {
				error;
				// console.log('Saving failed: ', error);
			});
	}

	reload() {
		this.sorted_public_items = [];
		this.sorted_private_items = [];
		this.setup_pages(true);
		this.discard = false;
		this.undo.readOnly = true;
	}

	create_page_skeleton() {
		if (this.body.find(".workspace-skeleton").length) return;

		this.body.prepend(frappe.render_template("workspace_loading_skeleton"));
		this.body.find(".codex-editor").addClass("hidden");
	}

	remove_page_skeleton() {
		this.body.find(".codex-editor").removeClass("hidden");
		this.body.find(".workspace-skeleton").remove();
	}

	create_sidebar_skeleton() {
		if ($(".workspace-sidebar-skeleton").length) return;

		$(frappe.render_template("workspace_sidebar_loading_skeleton")).insertBefore(this.sidebar);
		this.sidebar.addClass("hidden");
	}

	remove_sidebar_skeleton() {
		this.sidebar.removeClass("hidden");
		$(".workspace-sidebar-skeleton").remove();
	}

	register_awesomebar_shortcut() {
		"abcdefghijklmnopqrstuvwxyz".split("").forEach((letter) => {
			const default_shortcut = {
				action: (e) => {
					$("#navbar-search").focus();
					return false; // don't prevent default = type the letter in awesomebar
				},
				page: this.page,
			};
			frappe.ui.keys.add_shortcut({ shortcut: letter, ...default_shortcut });
			frappe.ui.keys.add_shortcut({ shortcut: `shift+${letter}`, ...default_shortcut });
		});
	}
};
