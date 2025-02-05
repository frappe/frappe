import EditorJS from "@editorjs/editorjs";
import Undo from "editorjs-undo";

frappe.standard_pages["Workspaces"] = function () {
	var wrapper = frappe.container.add_page("Workspaces");

	frappe.ui.make_app_page({
		parent: wrapper,
		name: "Workspaces",
		title: __("Workspace"),
		single_column: true,
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
		this.current_page = {};
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

		this.prepare_container();
		this.sidebar = frappe.app.sidebar;
		this.app_switcher_menu = frappe.app.app_switcher_menu;
		this.sidebar.setup_pages();
		this.cached_pages = $.extend(true, {}, frappe.boot.sidebar_pages);
		this.has_access = frappe.boot.sidebar_pages.has_access;
		this.has_create_access = frappe.boot.sidebar_pages.has_create_access;
		this.show();
		this.register_awesomebar_shortcut();
	}

	prepare_container() {
		this.body = this.wrapper.find(".layout-main-section");
		this.prepare_new_and_edit();
	}

	prepare_new_and_edit() {
		this.$page = $(`
		<div class="workspace-header" style="display: flex; gap: 7px; margin-top: var(--margin-sm);">
			<div class="workspace-icon"></div>
			<h4 class="workspace-title"></h4>
		</div>
		<div class="editor-js-container"></div>
		<div class="workspace-footer">
			<button data-label="New" class="btn btn-default ellipsis btn-new-workspace">
				<svg class="es-icon es-line icon-xs" style="" aria-hidden="true">
					<use class="" href="#es-line-add"></use>
				</svg>
				<span class="hidden-xs" data-label="New">${__("New")}</span>
			</button>
			<button class="btn btn-default btn-sm mr-2 btn-edit-workspace" data-label="Edit">
				<svg class="es-icon es-line  icon-xs" style="" aria-hidden="true">
					<use class="" href="#es-line-edit"></use>
				</svg>
				<span class="hidden-xs" data-label="Edit">${__("Edit")}</span>
			</button>
		</div>
	`).appendTo(this.body);

		this.body.find(".btn-new-workspace").on("click", () => {
			this.initialize_new_page(true);
		});

		this.body.find(".btn-edit-workspace").on("click", async () => {
			if (!this.editor || !this.editor.readOnly) return;
			this.is_read_only = false;
			await this.editor.readOnly.toggle();
			this.editor.isReady.then(() => {
				this.setup_customization_buttons(this._page);
				this.make_blocks_sortable();
				frappe.app.sidebar.toggle_sorting();
			});
		});
	}

	get_pages() {
		return frappe.xcall("frappe.desk.desktop.get_workspace_sidebar_items", null, "GET");
	}

	show() {
		if (!this.sidebar.all_pages) {
			// pages not yet loaded, call again after a bit
			setTimeout(() => this.show(), 100);
			return;
		}

		let page = this.get_page_to_show();
		if (this._page?.name === page.name) return; // already shown

		if (!frappe.router.current_route[0]) {
			frappe.route_flags.replace_route = true;
			frappe.set_route(frappe.router.slug(page.public ? page.name : "private/" + page.name));
			return;
		}

		this.page.set_title(__(page.name));
		this.show_page(page);
	}

	get_data(page) {
		return frappe
			.call({
				method: "frappe.desk.desktop.get_desktop_page",
				args: {
					// send sorted min requirements to increase chance of cache hit
					page: { name: page.name, title: page.title, public: page.public },
				},
				type: "GET",
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

		if (frappe.boot.user.default_workspace) {
			default_page = {
				name: frappe.boot.user.default_workspace.name,
				public: frappe.boot.user.default_workspace.public,
			};
		} else if (
			localStorage.current_page &&
			this.sidebar.all_pages.filter((page) => page.name == localStorage.current_page)
				.length != 0
		) {
			default_page = {
				name: localStorage.current_page,
				public: localStorage.is_current_page_public != "false",
			};
		} else if (Object.keys(this.sidebar.all_pages).length !== 0) {
			default_page = {
				name: this.sidebar.all_pages[0].name,
				public: this.sidebar.all_pages[0].public,
			};
		} else {
			default_page = { name: "Build", public: true };
		}

		const route = frappe.get_route();
		const page = (route[1] == "private" ? route[2] : route[1]) || default_page.name;
		const is_public = route[1] ? route[1] != "private" : default_page.public;

		return { name: page, public: is_public };
	}

	async show_page(page) {
		if (!this.body.find("#editorjs")[0]) {
			$(`
				<div id="editorjs" class="desk-page page-main-content"></div>
			`).appendTo(this.body.find(".editor-js-container"));
		}

		if (this.sidebar.all_pages.length) {
			this.create_page_skeleton();

			let current_page = this.sidebar.all_pages.find((p) => p.name == page.name);
			this._page = current_page;

			// set app
			let app;
			if (!this._page.public) {
				app = "private";
			} else {
				app = this._page.app;
				if (!app && this._page.module) {
					app = frappe.boot.module_app[frappe.router.slug(this._page.module)];
				}
				if (!app) app = "frappe";
			}

			if (typeof current_page.content == "string") {
				current_page.content = JSON.parse(current_page.content);
			}

			this.content = current_page.content;
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
			frappe.app.sidebar.apps_switcher.set_current_app(app);
			this.wrapper.find(".workspace-title").html(__(this._page.title));
			this.wrapper
				.find(".workspace-icon")
				.html(frappe.utils.icon(this._page.icon || "folder-normal", "md"));

			localStorage.current_page = current_page.name;
			localStorage.is_current_page_public = current_page.public ? "true" : "false";
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
				// this.editor.configuration.tools.onboarding.config.page_data = this.page_data;
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
		let current_page = this.sidebar.all_pages.filter((p) => p.name == page.name)[0];

		if (!this.is_read_only) {
			this.setup_customization_buttons(current_page);
			return;
		}

		this.clear_page_actions();
		if (current_page.is_editable) {
			this.body.find(".btn-edit-workspace").removeClass("hide");
		} else {
			this.body.find(".btn-edit-workspace").addClass("hide");
		}
		// need to add option for icons in inner buttons as well
		if (this.has_create_access) {
			this.body.find(".btn-new-workspace").removeClass("hide");
		} else {
			this.body.find(".btn-new-workspace").addClass("hide");
		}
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

		// switch headers
		if (!this.body.hasClass("edit-mode")) {
			this.wrapper.find(".page-head").addClass("hidden");
			this.wrapper.find(".workspace-header").removeClass("hidden");
		}
	}

	setup_customization_buttons(page) {
		this.body.addClass("edit-mode");
		this.initialize_editorjs_undo();
		this.clear_page_actions();

		// switch headers
		this.wrapper.find(".page-head").removeClass("hidden");
		this.wrapper.find(".workspace-header").addClass("hidden");

		page.is_editable &&
			this.page.set_primary_action(
				__("Save"),
				() => {
					this.clear_page_actions();
					this.body.removeClass("edit-mode");
					this.save_page(page).then((saved) => {
						if (!saved) return;
						this.undo.readOnly = true;
						this.editor.readOnly.toggle();
						this.is_read_only = true;
					});
					frappe.app.sidebar.toggle_sorting();
				},
				null,
				__("Saving")
			);

		this.page.set_secondary_action(__("Discard"), async () => {
			this.body.removeClass("edit-mode");
			this.clear_page_actions();
			await this.editor.readOnly.toggle();
			this.is_read_only = true;
			frappe.boot.sidebar_pages = this.cached_pages;
			this.reload();
			frappe.show_alert({ message: __("Customizations Discarded"), indicator: "info" });
		});

		if (page.name && this.has_access) {
			this.page.add_inner_button(__("Settings"), () => {
				frappe.set_route(`workspace/${page.name}`);
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
					label: __("Type"),
					fieldtype: "Select",
					fieldname: "type",
					options: ["Workspace", "Link", "URL"],
					reqd: 1,
					onchange: function () {
						d.set_df_property("link_type", "hidden", this.get_value() != "Link");
						d.set_df_property("link_to", "hidden", this.get_value() != "Link");
					},
				},
				{
					label: __("Link Type"),
					depends_on: `eval:doc.type=='Link'`,
					mandatory_depends_on: `eval:doc.type=='Link'`,
					fieldtype: "Select",
					fieldname: "link_type",
					options: ["DocType", "Page", "Report"],
				},
				{
					label: __("Link To"),
					depends_on: `eval:doc.type=='Link'`,
					mandatory_depends_on: `eval:doc.type=='Link'`,
					fieldtype: "Dynamic Link",
					fieldname: "link_to",
					options: "link_type",
				},
				{
					label: __("External Link"),
					depends_on: `eval:doc.type=='URL'`,
					mandatory_depends_on: `eval:doc.type=='URL'`,
					fieldtype: "Data",
					fieldname: "external_link",
					options: "URL",
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
						d.set_df_property("icon", "hidden", this.get_value() ? 0 : 1);
						d.set_df_property("indicator_color", "hidden", this.get_value() ? 1 : 0);
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
				{
					label: __("Indicator color"),
					fieldtype: "Select",
					fieldname: "indicator_color",
					options: this.indicator_colors,
				},
			],
			primary_action_label: __("Create"),
			primary_action: (values) => {
				values.title = strip_html(values.title);
				d.hide();
				if (values.type === "Workspace") {
					this.setup_customization_buttons({ is_editable: true });
				}

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
					indicator_color: values.indicator_color,
					parent_page: values.parent || "",
					is_editable: true,
					selected: true,
					app: frappe.current_app,
					type: values.type,
					link_type: values.link_type,
					link_to: values.link_to,
					external_link: values.external_link,
				};

				if (new_page.type !== "Workspace") {
					this.create_page(new_page);
				} else {
					this.editor
						.render({
							blocks: blocks,
						})
						.then(async () => {
							if (this.editor.configuration.readOnly) {
								this.is_read_only = false;
								await this.editor.readOnly.toggle();
							}

							this.create_page(new_page).then(() => {
								let pre_url = new_page.public ? "" : "private/";
								let route = pre_url + frappe.router.slug(new_page.title);
								frappe.set_route(route);
							});
						});
				}
			},
		});
		d.show();
	}

	create_page(new_page) {
		return new Promise((resolve) => {
			frappe.call({
				method: "frappe.desk.doctype.workspace.workspace.new_page",
				args: {
					new_page: new_page,
				},
				callback: (r) => {
					if (r.message) {
						let message = __("Workspace {0} created", [new_page.title.bold()]);
						if (!window.Cypress) {
							frappe.show_alert({
								message: message,
								indicator: "green",
							});
						}
						frappe.boot.sidebar_pages = r.message;
						this.sidebar.setup_pages();

						if (!frappe.boot.app_data_map["private"] && new_page.public === 0) {
							this.sidebar.apps_switcher.add_private_app();
						}
						resolve();
					}
				},
			});
		});
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
		this.current_page = { name: page.name, public: page.public };

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
					frappe.show_alert({
						message: __("No changes made"),
						indicator: "warning",
					});
					return false;
				}

				this.create_page_skeleton();
				page.content = JSON.stringify(blocks);
				frappe.call({
					method: "frappe.desk.doctype.workspace.workspace.save_page",
					args: {
						name: page.name,
						public: page.public || 0,
						new_widgets: new_widgets,
						blocks: JSON.stringify(blocks),
					},
					callback: function (res) {
						if (res.message) {
							me.discard = true;
							me.reload();
							if (window.Cypress) return;
							frappe.show_alert({
								message: __("Saved"),
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
		delete this.pages[this._page.name];
		this._page = null;
		return this.get_pages().then((r) => {
			frappe.boot.sidebar_pages = r;
			this.sidebar.setup_pages();
			this.show();
			if (this.undo) this.undo.readOnly = true;
		});
	}

	get_parent_pages(page) {
		this.public_parent_pages = [
			"",
			...this.sidebar.all_pages
				.filter((p) => p.public && !p.parent_page)
				.map((p) => {
					return { label: p.title, value: p.name };
				}),
		];
		this.private_parent_pages = [
			"",
			...this.sidebar.all_pages
				.filter((p) => !p.public && !p.parent_page)
				.map((p) => {
					return { label: p.title, value: p.name };
				}),
		];

		if (page) {
			return page.public ? this.public_parent_pages : this.private_parent_pages;
		}
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
