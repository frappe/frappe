import EditorJS from "@editorjs/editorjs";
import Undo from "editorjs-undo";

// sentinel class on the injected "this workspace is hidden" notice block, so it can be
// rendered for Workspace Managers but stripped before the content is saved.
const HIDDEN_NOTICE_MARKER = "workspace-hidden-notice";

// "Access" options in the New Workspace dialog -- a virtual field that maps to the
// underlying `public` / `for_user` / `roles` fields:
//   private -> personal (public=0, for_user=current user)
//   group   -> public but role-gated (public=1, roles=[...])
//   public  -> visible to everyone (public=1, no roles)
const ACCESS_PRIVATE = __("Only to you");
const ACCESS_GROUP = __("To a group of users");
const ACCESS_PUBLIC = __("To everyone");

frappe.standard_pages["Workspaces"] = function () {
	var wrapper = frappe.container.add_page("Workspaces");

	frappe.ui.make_app_page({
		parent: wrapper,
		name: "Workspaces",
		title: __("Workspace"),
		single_column: true,
		hide_sidebar: false,
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
		this.workspaces = frappe.boot.workspaces.pages;

		this.blocks = frappe.workspace_block.blocks;
		this.is_read_only = true;
		this.pages = {};
		this.current_page = {};
		this.sidebar_items = {
			public: {},
			private: {},
		};
		this.prepare_container();
		this.sidebar = frappe.app.sidebar;
		this.cached_pages = $.extend(true, {}, frappe.boot.workspaces);
		this.has_access = frappe.boot.workspaces.has_access;
		this.has_create_access = frappe.boot.workspaces.has_create_access;
		this.setup();
		this.show();
		this.register_awesomebar_shortcut();
	}
	setup() {
		const me = this;
		this.workspaces.map((workspace) => {
			workspace.is_editable = !workspace.public || me.has_access;
			if (typeof workspace.content == "string") {
				workspace.content = JSON.parse(workspace.content);
			}
		});
	}

	setup_sidebar() {
		if (this._page) {
			this.sidebar.setup(this._page.name);
		}
	}
	prepare_container() {
		this.body = this.wrapper.find(".layout-main-section");
		this.$page = $(`<div class="editor-js-container"></div>`).appendTo(this.body);
	}

	show() {
		if (!this.workspaces) {
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

		if (
			localStorage.current_page &&
			this.workspaces.filter((page) => page.name == localStorage.current_page).length != 0
		) {
			default_page = {
				name: localStorage.current_page,
				public: localStorage.is_current_page_public != "false",
			};
		} else if (Object.keys(this.workspaces).length !== 0) {
			default_page = {
				name: this.workspaces[0].name,
				public: this.workspaces[0].public,
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

		if (this.workspaces.length) {
			this.create_page_skeleton();

			let current_page = this.workspaces.find((p) => p.name == page.name);
			this._page = current_page;
			const me = this;
			// private workspaces are stored as `${title}-${for_user}`; show just the title
			let header_dropdown = `${__(this._page.title)}`;
			frappe.breadcrumbs.add({
				type: "Custom",
				label: header_dropdown,
				route: "#",
			});
			if (!this.add_workspace_controls) {
				this.workspace_actions_button = this.page.add_action_icon("ellipsis", "", "");

				$(this.workspace_actions_button).removeAttr("data-original-title");
				$(this.workspace_actions_button).removeClass("btn-default");
				frappe.ui.create_menu({
					parent: $(this.workspace_actions_button),
					open_on_left: true,
					size: "fit-content",
					menu_items: [
						{
							label: "Edit",
							icon: "pencil",
							onClick: async () => {
								if (!this.editor || !this.editor.readOnly) return;
								this.is_read_only = false;
								await this.editor.readOnly.toggle();
								this.editor.isReady.then(() => {
									this.setup_customization_buttons(this._page);
									this.make_blocks_sortable();
								});
							},
							condition: () => {
								return current_page.is_editable;
							},
						},
						{
							label: "New",
							icon: "plus",
							onClick: () => this.initialize_new_page(),
							condition: () => {
								return this.has_create_access;
							},
						},
						{
							label: "Manage",
							icon: "settings",
							onClick: () => this.open_workspace_manager(current_page),
							condition: () => {
								// available whenever the user can manage at least one workspace
								// (a Workspace Manager, or anyone with their own private pages)
								return this.workspaces.some((p) => p.is_editable);
							},
						},
						{
							label: "Reset to Standard",
							icon: "rotate-ccw",
							onClick: () => this.reset_workspace_customization(current_page),
							condition: () => {
								return current_page.is_customized && this.has_access;
							},
						},
					],
				});
				this.add_workspace_controls = true;
			}

			this.wrapper.find(".workspace-header").hide();
			this.wrapper
				.find(".editor-js-container")
				.get(0)
				.style.setProperty("margin-top", "var(--margin-sm)");

			// set app
			let app;
			if (!this._page.public) {
				app = "private";
			} else {
				app = this._page.app;
				if (!app && this._page.module) {
					app = frappe.boot.module_app[frappe.router.slug(this._page.module)];
				}
				// this._page.module && this.sidebar.show_sidebar_for_module(this._page.module);
				if (!app) app = "frappe";
			}

			if (typeof current_page.content == "string") {
				current_page.content = JSON.parse(current_page.content);
			}

			this.content = current_page.content;
			this.content && this.add_custom_cards_in_content();
			this.content && this.add_hidden_notice_in_content(current_page);

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
			this.wrapper.find(".workspace-title").html(__(this._page.title));
			this.wrapper
				.find(".workspace-icon")
				.html(frappe.utils.icon(this._page.icon || "folder", "md"));

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
		let current_page = this.workspaces.filter((p) => p.name == page.name)[0];

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

	add_hidden_notice_in_content(page) {
		// A hidden workspace is dropped from everyone else's sidebar; a Workspace Manager
		// still sees it. Prepend a display-only text block explaining why. The sentinel
		// span lets save_page() strip it so it is never persisted into the workspace.
		if (!page.is_hidden || !this.has_access) return;
		if (
			this.content.some(
				(b) => b.type == "paragraph" && b.data?.text?.includes(HIDDEN_NOTICE_MARKER)
			)
		) {
			return;
		}
		this.content.unshift({
			type: "paragraph",
			data: {
				text: `<span class="${HIDDEN_NOTICE_MARKER}">${__(
					"This workspace is hidden from other users. You can see it because you're a Workspace Manager."
				)}</span>`,
				col: "12",
			},
		});
	}

	open_workspace_manager(current_page) {
		// Two-pane manager: the list of workspaces the user can manage on the left, the
		// selected workspace's access / appearance settings on the right. Replaces the
		// old "route to the Workspace / Workspace Customization form" flow.
		//
		// The list comes from the server, not `frappe.boot.workspaces`: the bootinfo only
		// carries the user's *own* private workspaces, but a Workspace Manager manages every
		// workspace (including other users' private ones).
		frappe
			.call({
				method: "frappe.desk.doctype.workspace.workspace.get_manageable_workspaces",
			})
			.then((r) => {
				const manageable = r.message || [];
				if (!manageable.length) return;

				// Standard = public app-shipped, Custom = public but user-created,
				// Private = per-user workspaces.
				const groups = [
					{ label: __("Standard"), filter: (p) => p.public && p.standard },
					{ label: __("Custom"), filter: (p) => p.public && !p.standard },
					{ label: __("Private"), filter: (p) => !p.public },
				];
				const tabs = [];
				groups.forEach(({ label, filter }) => {
					const pages = manageable.filter(filter);
					if (pages.length) {
						tabs.push({
							group: label,
							items: pages.map((p) => this.workspace_manager_item(p)),
						});
					}
				});

				const has_current =
					current_page && manageable.some((p) => p.name === current_page.name);
				this.workspace_manager = new frappe.ui.SettingsDialog({
					title: __("Manage Workspaces"),
					tabs,
					default_tab: has_current ? current_page.name : undefined,
				});
				this.workspace_manager.show();
			});
	}

	workspace_manager_item(page) {
		// a manager may see private workspaces owned by other users -- label whose they are
		const owned_by_other =
			!page.public && page.for_user && page.for_user !== frappe.session.user;
		const label = owned_by_other ? `${__(page.title)} (${page.for_user})` : __(page.title);
		return {
			id: page.name,
			label,
			icon: page.icon || "layout-grid",
			render: (panel) => this.render_workspace_manager_panel(panel, page),
		};
	}

	render_workspace_manager_panel(panel, page) {
		panel.set_header({ title: __(page.title) });
		panel.body.html(`<div class="text-muted">${__("Loading...")}</div>`);

		frappe
			.call({
				method: "frappe.desk.doctype.workspace.workspace.get_workspace_settings",
				args: { name: page.name },
			})
			.then((r) => {
				const settings = r.message;
				if (!settings) return;

				const actions = [];
				if (!settings.standard) {
					actions.push({
						label: __("Delete"),
						class: "btn-danger",
						click: () => this.delete_workspace_from_manager(page),
					});
				}
				actions.push({
					label: __("Save"),
					primary: true,
					click: (p) => this.save_workspace_from_manager(p, settings),
				});

				panel.set_view({
					title: __(settings.title),
					description: settings.standard
						? __(
								"A standard workspace is shipped by the app; changes are saved as customizations."
						  )
						: __("Control who can see this workspace and how it appears."),
					actions,
					fields: this.workspace_manager_fields(settings),
				});
			});
	}

	workspace_manager_fields(settings) {
		const access_to_label = {
			private: ACCESS_PRIVATE,
			group: ACCESS_GROUP,
			public: ACCESS_PUBLIC,
		};
		// A standard workspace's `public` flag is app-owned, so it can only ever be shared
		// (open to everyone or gated to a group). Custom workspaces get the full range, but
		// only a Workspace Manager may make one public.
		let access_options;
		if (settings.standard) {
			access_options = [ACCESS_GROUP, ACCESS_PUBLIC];
		} else if (this.has_access) {
			access_options = [ACCESS_PRIVATE, ACCESS_GROUP, ACCESS_PUBLIC];
		} else {
			access_options = [ACCESS_PRIVATE];
		}

		const role_rows = (settings.roles || []).map((role) => ({ role }));

		return [
			{
				label: __("Title"),
				fieldname: "title",
				fieldtype: "Data",
				default: settings.title,
				reqd: 1,
				read_only: settings.standard ? 1 : 0,
				description: settings.standard
					? __("The title of a standard workspace is managed by the app.")
					: "",
			},
			{
				label: __("Icon"),
				fieldname: "icon",
				fieldtype: "Icon",
				default: settings.icon,
			},
			{
				label: __("Access"),
				fieldname: "access",
				fieldtype: "Select",
				options: access_options,
				default: access_to_label[settings.access] || access_options[0],
				reqd: 1,
				description: __("Who can see this workspace"),
			},
			{
				label: __("Roles"),
				fieldname: "roles",
				fieldtype: "Table",
				depends_on: `eval:doc.access=='${ACCESS_GROUP}'`,
				description: __("Users with any of these roles can see this workspace"),
				data: role_rows,
				get_data: () => role_rows,
				fields: [
					{
						label: __("Role"),
						fieldname: "role",
						fieldtype: "Link",
						options: "Role",
						in_list_view: 1,
						reqd: 1,
					},
				],
			},
		];
	}

	save_workspace_from_manager(panel, settings) {
		const values = panel.get_values();
		if (!values) return;

		const label_to_access = {
			[ACCESS_PRIVATE]: "private",
			[ACCESS_GROUP]: "group",
			[ACCESS_PUBLIC]: "public",
		};
		const access = label_to_access[values.access];
		const roles =
			access === "group" ? (values.roles || []).map((r) => r.role).filter(Boolean) : [];

		frappe.call({
			method: "frappe.desk.doctype.workspace.workspace.update_workspace_settings",
			args: {
				name: settings.name,
				title: values.title,
				icon: values.icon,
				access,
				roles,
			},
			freeze: true,
			callback: (r) => {
				if (!r.message) return;
				this.apply_manager_changes(r.message);
				frappe.show_alert({ message: __("Workspace updated"), indicator: "green" });
				this.workspace_manager && this.workspace_manager.hide();
			},
		});
	}

	delete_workspace_from_manager(page) {
		frappe.confirm(
			__("Delete the <b>{0}</b> workspace? This cannot be undone.", [__(page.title)]),
			() => {
				frappe.call({
					method: "frappe.desk.doctype.workspace.workspace.delete_page",
					args: { name: page.name },
					freeze: true,
					callback: (r) => {
						if (!r.message) return;
						this.apply_manager_changes(r.message);
						frappe.show_alert({
							message: __("Workspace {0} deleted", [__(page.title)]),
							indicator: "green",
						});
						this.workspace_manager && this.workspace_manager.hide();
					},
				});
			}
		);
	}

	apply_manager_changes(message) {
		// Refresh the cached workspace + sidebar payloads and re-render, mirroring create_page.
		frappe.boot.workspaces = message.workspace_pages;
		this.workspaces = frappe.boot.workspaces.pages;
		this.setup_pages(frappe.boot.workspaces.pages);
		frappe.boot.workspace_sidebar_item = message.sidebar_items;
		this.reload();
		// reload() re-derives the current page synchronously; re-render its sidebar so a rename
		// or visibility change is reflected in the shell.
		if (frappe.app.sidebar && this._page) {
			frappe.app.sidebar.setup(this._page.name);
		}
	}

	reset_workspace_customization(page) {
		frappe.confirm(
			__(
				"Reset <b>{0}</b> to the standard, app-shipped version? This removes all site customizations.",
				[__(page.title)]
			),
			() => {
				frappe.call({
					method: "frappe.desk.doctype.workspace_customization.workspace_customization.reset_workspace_customization",
					args: { workspace: page.name },
					freeze: true,
					callback: () => {
						frappe.show_alert({
							message: __("Workspace reset to standard"),
							indicator: "green",
						});
						this.reload();
					},
				});
			}
		);
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
			this.wrapper.find(".workspace-header").removeClass("hidden");
		}
	}

	setup_customization_buttons(page) {
		this.body.addClass("edit-mode");
		this.initialize_editorjs_undo();
		this.clear_page_actions();
		$("#full-search-button").addClass("hidden");

		// switch headers
		this.wrapper.find(".page-head").removeClass("hidden");
		this.wrapper.find(".workspace-header").addClass("hidden");

		page.is_editable &&
			this.page.set_primary_action(
				__("Save"),
				() => {
					this.clear_page_actions();
					this.body.removeClass("edit-mode");
					$("#full-search-button").removeClass("hidden");
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
			this.body.removeClass("edit-mode");
			this.clear_page_actions();
			$("#full-search-button").removeClass("hidden");
			await this.editor.readOnly.toggle();
			this.is_read_only = true;
			frappe.boot.workspaces = this.cached_pages;
			this.reload();
			frappe.show_alert({ message: __("Customizations Discarded"), indicator: "info" });
		});

		if (page.name && this.has_access) {
			this.page.add_inner_button(__("Settings"), () => {
				frappe.set_route(`workspace/${page.name}`);
			});
		}
		$(this.workspace_actions_button).remove();
		this.add_workspace_controls = false;
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
					default: "Workspace",
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
					label: __("Access"),
					fieldtype: "Select",
					fieldname: "access",
					reqd: 1,
					default: ACCESS_PRIVATE,
					options: this.access_options(),
					description: __("Who can see this workspace"),
					onchange: function () {
						let is_private = this.get_value() === ACCESS_PRIVATE;
						d.set_df_property(
							"parent",
							"options",
							is_private ? me.private_parent_pages : me.public_parent_pages
						);
						d.set_df_property(
							"roles",
							"hidden",
							this.get_value() !== ACCESS_GROUP ? 1 : 0
						);
					},
				},
				{
					label: __("Icon"),
					fieldtype: "Icon",
					fieldname: "icon",
				},
				{
					label: __("Roles"),
					fieldtype: "Table",
					fieldname: "roles",
					hidden: 1,
					description: __("Users with any of these roles can see this workspace"),
					fields: [
						{
							label: __("Role"),
							fieldtype: "Link",
							fieldname: "role",
							options: "Role",
							in_list_view: 1,
							reqd: 1,
						},
					],
				},
				{
					label: __("Parent"),
					fieldtype: "Select",
					fieldname: "parent",
					options: this.private_parent_pages,
					hidden: 1,
				},
			],
			primary_action_label: __("Create"),
			primary_action: (values) => {
				values.title = strip_html(values.title);
				d.hide();

				let is_public = values.access !== ACCESS_PRIVATE;
				let name = values.title + (is_public ? "" : "-" + frappe.session.user);
				// seed the new workspace with the welcome blocks (header + edit hint) so it opens
				// with guidance instead of a bare title
				let blocks = [
					{
						type: "header",
						data: { text: __("Welcome to the {0} workspace", [values.title]) },
					},
				];
				if (this.has_access) {
					blocks.push({
						type: "paragraph",
						data: {
							text: __("Click on {0} to edit", [frappe.utils.icon("ellipsis")]),
						},
					});
				}

				let new_page = {
					content: JSON.stringify(blocks),
					name: name,
					label: name,
					title: values.title,
					public: is_public ? 1 : 0,
					for_user: is_public ? "" : frappe.session.user,
					icon: values.icon,
					roles: values.access === ACCESS_GROUP ? values.roles || [] : [],
					parent_page: values.parent || "",
					is_editable: true,
					selected: true,
					type: values.type,
					link_type: values.link_type,
					link_to: values.link_to,
					external_link: values.external_link,
				};

				if (new_page.type !== "Workspace") {
					this.create_page(new_page);
				} else {
					// Create then navigate to the new workspace in view (read-only) mode. We don't
					// set up the edit-mode customization buttons or toggle the editor here -- the
					// route change re-renders the workspace read-only.
					this.create_page(new_page).then(() => {
						let route = frappe.router.slug(
							new_page.public ? new_page.name : "private/" + new_page.name
						);
						frappe.set_route(route);
					});
				}
			},
		});
		d.show();
	}

	create_page(new_page) {
		const me = this;
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
						if (r.message) {
							frappe.boot.workspaces = r.message.workspace_pages;
							me.workspaces = frappe.boot.workspaces.pages;
							me.setup_pages(frappe.boot.workspaces.pages);
							frappe.boot.workspace_sidebar_item = r.message.sidebar_items;
						}

						// Surface the new workspace in the selector right away (the boot.py fix
						// makes it durable across reloads). Public ones are listed via their app's
						// workspace list; private ones are auto-listed from frappe.workspaces.
						if (new_page.public && new_page.app) {
							let app = (frappe.boot.app_data || []).find(
								(a) => a.app_name === new_page.app
							);
							if (app && !app.workspaces.includes(new_page.name)) {
								app.workspaces.push(new_page.name);
							}
						}

						// A new Workspace seeds a sidebar item linking to itself (see new_page),
						// so it now has its own entry in the sidebar payload -- switch the sidebar
						// to it so the shell reflects the just-created workspace.
						if (frappe.boot.workspace_sidebar_item[new_page.name.toLowerCase()]) {
							frappe.app.sidebar.setup(new_page.name);
						} else if (new_page.public === 0) {
							frappe.app.sidebar.setup("private");
						}

						resolve();
					}
				},
			});
		});
	}

	setup_pages(all_pages) {
		all_pages.forEach((page) => {
			page.is_editable = !page.public || this.has_access;
			if (typeof page.content == "string") {
				page.content = JSON.parse(page.content);
			}
		});

		if (all_pages) {
			frappe.workspaces = {};
			frappe.workspace_list = [];
			frappe.workspace_map = {};
			for (let page of all_pages) {
				if (!page.app && page.module) {
					page.app = frappe.boot.module_app[frappe.slug(page.module)];
				}
				// store the full page (matching desk.js setup_workspaces) so consumers like the
				// sidebar header have title/icon/for_user, not just name/public
				frappe.workspaces[frappe.router.slug(page.name)] = page;
				frappe.workspace_map[page.name] = page;
				frappe.workspace_list.push(page);
			}
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
		if (blocks.length == 0) {
			let message = __("Welcome to the {0} workspace", [this.page.title]);
			let default_block = [
				{
					type: "header",
					data: { text: message },
				},
			];
			if (this.has_access) {
				default_block.push({
					type: "paragraph",
					data: {
						text: __("Click on {0} to edit", [frappe.utils.icon("ellipsis")]),
					},
				});
			}
			this.editor.isReady.then(() => {
				this.editor.render({ blocks: default_block });
			});
		}
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

				// never persist the display-only "workspace is hidden" notice
				blocks = blocks.filter(
					(item) =>
						!(
							item.type == "paragraph" &&
							item.data?.text?.includes(HIDDEN_NOTICE_MARKER)
						)
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
							if (page.public) {
								frappe.set_route("desk", frappe.router.slug(page.name));
							} else {
								frappe.set_route("desk", "private", frappe.router.slug(page.name));
							}
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
		this.setup_pages(frappe.boot.workspaces.pages);
		this.show();
		if (this.undo) this.undo.readOnly = true;
	}

	get_parent_pages(page) {
		this.public_parent_pages = [
			"",
			...this.workspaces
				.filter((p) => p.public && !p.parent_page)
				.map((p) => {
					return { label: p.title, value: p.name };
				}),
		];
		this.private_parent_pages = [
			"",
			...this.workspaces
				.filter((p) => !p.public && !p.parent_page)
				.map((p) => {
					return { label: p.title, value: p.name };
				}),
		];

		if (page) {
			return page.public ? this.public_parent_pages : this.private_parent_pages;
		}
	}

	// "Access" choices for the New Workspace dialog. Creating a public workspace (whether
	// role-gated or open to everyone) requires the Workspace Manager role, so users without
	// it can only ever create a private "Only to you" workspace.
	access_options() {
		let options = [ACCESS_PRIVATE];
		if (this.has_access) {
			options.push(ACCESS_GROUP, ACCESS_PUBLIC);
		}
		return options;
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
					$("#navbar-modal-search").click();
					return false; // don't prevent default = type the letter in awesomebar
				},
				page: this.page,
			};
			frappe.ui.keys.add_shortcut({ shortcut: letter, ...default_shortcut });
			frappe.ui.keys.add_shortcut({ shortcut: `shift+${letter}`, ...default_shortcut });
		});
	}
};
